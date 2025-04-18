from jarvis.assembly.base import client
from jarvis.assembly.base import skills
import random 
import time
import openai
import json
import os
import subprocess
from typing import List, Dict
from .strip_word import parse_three_logs

def translate_task(task):
    return f"Obtain {task}"

def translate_inventory(info):
    inventory = {}
    for i in range(36):
        if info['inventory'][i]['type'] == 'none':
            continue
        
        if info['inventory'][i]['type'] in inventory.keys():
            inventory[info['inventory'][i]['type']] += info['inventory'][i]['quantity']
        else:
            inventory[info['inventory'][i]['type']] = info['inventory'][i]['quantity']
    if not len(inventory.keys()):
        return "Now my inventory has nothing."
    else:
        content = []
        for k, v in inventory.items():
            content.append(f"{v} {k}")
        return f"Now my inventory has {', '.join(content)}."

def translate_equipment(info):
    # return info['equipped_items']['mainhand']['type']
    return f"Now I equip the {info['equipped_items']['mainhand']['type']} in mainhand."

def translate_height(info):
    # return int(info['location_stats']['ypos'])
    return f"Now I locate in height of {int(info['player_pos']['y'])}."

def parse_action_index(text):
    # Split the text into lines
    lines = text.split('\n')
    # Loop through each line to find the line starting with "Action:"
    for line in lines:
        if line.startswith("Action:"):
            # Extract the number following "Action:"
            action_index = line.split("Action:")[1].strip()
            try:
                return int(action_index)
            except:
                return None # Return None if "Action: xxx" is not action index
    # Return None if "Action:" is not found
    return None

def gen_problem_pddl(task,info):
    print({translate_inventory(info)})
    print({translate_equipment(info)})
    print({translate_height(info)})
    test_inventory, test_equipment, test_height = parse_three_logs(str({translate_inventory(info)}), str({translate_equipment(info)}), str({translate_height(info)}))
    print(test_inventory)
    print(test_equipment)
    print(test_height)
    problem_file = generate_problem_pddl(task, test_inventory, test_equipment, test_height, 'action pddl')

def parse_plan_actions(plan: List[str], task: str):
    if not plan:
        return {
            "text": f"dig_down",
            "type": "mine",
            "object_item": None
        }
    actions = []
    for line in plan:
        line = line.strip()
        if line.lower().startswith("plan-length"):
            break
        if line.startswith("0."):
            start_idx = line.index("(") + 1
            end_idx = line.index(")")
            action = line[start_idx:end_idx]
            actions.append(action)
    if not actions:
        return {
            "text": f"dig_down",
            "type": "mine",
            "object_item": None
        }
    if 'equip' in actions[0]:
        if 'stone' in actions[0]:
            return {
            "text": f"{actions[0]}",
            "type": "equip",
            "object_item": "stone_pickaxe"
            }
        elif 'wooden' in actions[0]:
            return {
            "text": f"{actions[0]}",
            "type": "equip",
            "object_item": "wooden_pickaxe"
            }
        else:
            x = random.choice(skills[task])
            x["text"] = actions[0]
            return x
    return {
            "text": f"{actions[0]}",
            "type": "mine",
            "object_item": None
            }


def get_skill(task, info, llm_model="gpt-3.5-turbo", max_retries=5):
    skill_content = ""
    if task not in skills.keys():
        return {
            "text": f"get {task}",
            "type": "mine",
            "object_item": None
        }
    if len(skills[task]) == 1:
        return skills[task][0]
    for i, skill in enumerate(skills[task]):
        skill_content += f"{i+1}. {skill['text']}, "
    print("+++++++++++++++++++++++++++Before LLM++++++++++++++++++++++++++++++++++")
    print("skill_content:",skill_content)
    query = f"Task: {translate_task(task)}.\nSkills: {skill_content}\nAgent State: {translate_inventory(info)} {translate_equipment(info)} {translate_height(info)}"
    # print({translate_inventory(info)})
    # print({translate_equipment(info)})
    # print({translate_height(info)})
    print("query: ", query)
    
    retries = 0
    for _ in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant in Minecraft. I will give you a task in Minecraft and a set of skills to finish such task. And you need to choose a suitable skill for the agent to finish the task object.  Only choose one skill once. Output reasoning thought and the number of the skill as action. You can follow the history dialogues to make a decision."
                    },
                    {
                        "role": "user",
                        "content": "Task: Obtain iron_ore.\nSkills: 1. dig down, 2. equip stone pickaxe, 3. break stone blocks, obtain iron ore,\nAgent State: Now I have 1 stone pickaxe, 1 crafting_table, 4 stick, 6 planks in inventory. Now I equip the crafting_table in hand. Now I locate in height of 50."
                    },
                    {
                        "role": "assistant",
                        "content": "Thought: Mine iron ore should use the tool stone pickaxe. I have stone pickaxe in inventory. But I do not equip it now. So I should equip the stone pickaxe. \nAction: 2"
                    },
                    {
                        "role": "user",
                        "content": "Task: Obtain logs.\nSkills: 1. chop down the tree, 2. equip iron axe to chop down the tree, \nAgent State: Now I have 1 iron_axe in inventory. Now I equip the air in hand. Now I locate in height of 60."
                    },
                    {
                        "role": "assistant",
                        "content": "Thought: Equip the iron axe will accelerate the speed to chop trees. I have an iron axe in the inventory. So I should equip the iron axe first.\nAction: 2"
                    },
                    {
                        "role": "user",
                        "content": "Task: Obtain diamond.\nSkills: 1. dig down, 2. equip iron pickaxe, 3. break stone blocks, obtain diamond\nAgent State: Now I have 1 iron pickaxe, 1 crafting_table, 4 stick, 6 planks in inventory. Now I equip the iron_pickaxe in hand. Now I locate in height of 30."
                    },
                    {
                        "role": "assistant",
                        "content": "Thought: Diamond in Minecraft only exists in layers under height 15 and above height 5. Now my height is 30, which does not exist diamonds. So I should dig down to lower layers.\nAction: 1"
                    },
                    {
                        "role": "user",
                        "content": query
                    }
                ],
                temperature=1,
                max_tokens=256,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0
            )
            break
        except openai.APIConnectionError:
            print(f"Connection error. Retrying {retries+1}/{max_retries}...")
            retries += 1
            time.sleep(5)  # Wait before retrying
    print("++++++++++++++++++++++++++++++++After LLM+++++++++++++++++++++++++++++++++++++++++")
    print("LLM output:",response.choices[0].message.content)
    action_index = parse_action_index(response.choices[0].message.content)
    if not action_index or action_index > len( skills[task]): # if no action or action beyond task skills
        return random.choice(skills[task]), response.usage
    print("lll",skills[task][action_index-1])
    return skills[task][action_index-1], response.usage

# evaluate plan
def translate_plan(current_plan):
    plan_txt = ""
    n = len(current_plan)
    for i in range(n):
        plan_txt += f"{current_plan[i]['type']} {current_plan[i]['text']}"
        if i != n -1:
            plan_txt += ", "
    return plan_txt

def parse_evaluation_text(text):
    # Split the text into lines
    lines = text.split('\n')
    # Loop through each line to find the line starting with "Action:"
    for line in lines:
        if line.startswith("Evaluation:"):
            try:
                eval_txt, eval_type = line.split("Evaluation:")[1].strip().split(", ")
                return eval_txt.strip(), eval_type.replace(".", "")
            except:
                return "", "retry"
    return None, "retry"

def evaluate_plan(plan, addition_info="", llm_model="gpt-3.5-turbo"):
    query = f"""Task: {translate_task(plan[-1]['text'])}.\nCurrent plan: {translate_plan(plan)}."""
    if len(addition_info):
        query+=addition_info
    print(query)
    response = client.chat.completions.create(
        model=llm_model,
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant in Minecraft. I will give you a task in Minecraft and agent's current plan for the task. You need to evaluate the plan and provide your insights. Here are some hints for you: (1) If the plan is reasonable enough, proceed it. (2) If you think adding additional plan can benefit the task, refine it. (3) Only focus on high level and specific objects in microcraft world, do not propose basic or abstract objects. (4) Do not propose objects that are already in the plan. (5) If refine, only add one object. (6) Do not make up non-existent object, describe the item in microcraft style. (7) Do not propose object even harder than current task. (8) You MUST have a pickaxe to collect minerals such as cobblestone, iron_ore. Output your thought and your evaluation result."
            },
            {
                "role": "user",
                "content": "Task: Obtain crafting_table.\nCurrent plan: mine logs, craft planks, craft crafting_table."
            },
            {
                "role": "assistant",
                "content": "Thought: Necessay ingredients are collected before making crafting_table, no need to change the plan.\nEvaluation: reasonable plan, proceed."
            },
            {
                "role": "user",
                "content": "Task: Obtain stone_pickaxe.\nCurrent plan: mine logs, craft planks, mine cobblestone, craft crafting_table, craft stick, craft stone_pickaxe."
            },
            {
                "role": "assistant",
                "content": "Thought: I can not mine minerals like cobblestone without a pickaxe, I must craft a pickaxe ahead of mine cobblestone.\nEvaluation: wooden_pickaxe, refine."
            },
            {
                "role": "user",
                "content": "Task: Obtain wooden_pickaxe.\nCurrent plan: mine logs, craft planks, craft crafting_table, craft stick, craft wooden_pickaxe."
            },
            {
                "role": "assistant",
                "content": "Thought: Necessay ingredients are collected before making wooden_pickaxe, no need to change the plan.\nEvaluation: reasonable plan, proceed."
            },
            {
                "role": "user",
                "content": "Task: Obtain wooden_pickaxe.\nCurrent plan: mine logs, craft planks, craft stick, craft wooden_pickaxe."
            },
            {
                "role": "assistant",
                "content": "Thought: Making wooden_pickaxe requires crafting_table, need to craft crafting_table.\nEvaluation: crafting_table, refine."
            },
            {
                "role": "user",
                "content": "Task: Obtain stone_pickaxe\nCurrent plan: mine logs, craft planks, craft crafting_table, craft stick, craft wooden_pickaxe, mine cobblestone, craft stone_pickaxe."
            },
            {
                "role": "assistant",
                "content": "Thought: Mine cobblestone needs pickaxe, wooden_pickaxe is the easiest pickaxe to make.\nEvaluation: reasonable plan, proceed."
            },
            {
                "role": "user",
                "content": "Task: Obtain iron_pickaxe.\nCurrent plan: mine logs, craft planks, mine cobblestone, craft crafting_table, craft stick, craft stone_pickaxe, craft furnace, mine iron_ore, smelt iron_ingot, craft iron_pickaxe."
            },
            {
                "role": "assistant",
                "content": "Thought: The problem in current plan is that cobblestone is a mineral, which can not be collected directly, I need a wooden_pickaxe to collect cobblestone.\nEvaluation: wooden_pickaxe, refine."
            },
            {
                "role": "user",
                "content": "Task: Obtain iron_pickaxe.\nCurrent plan: mine logs, craft planks, craft crafting_table, craft stick, craft wooden_pickaxe, mine cobblestone, craft furnace, mine iron_ore, smelt iron_ingot, craft iron_pickaxe."
            },
            {
                "role": "assistant",
                "content": "Thought: Mine iron_ore is laborous even with wooden_pickaxe, it's beneficial to also craft a stone_pickaxe ahead to facilicate mining.\nEvaluation: stone_pickaxe, refine."
            },
            {
                "role": "user",
                "content": "Task: Obtain stone_pickaxe.\nCurrent plan: mine logs, craft planks, mine cobblestone, craft crafting_table, craft stick, craft stone_pickaxe."
            },
            {
                "role": "assistant",
                "content": "Thought: Minerals can only be collected with pickaxe, current plan does not have pickaxe before mine cobblestone.\nEvaluation: wooden_pickaxe, craft."
            },
            {
                "role": "user",
                "content": query
            }
        ],
        temperature=1,
        max_tokens=256,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0
    )

    print(response.choices[0].message.content)
    insights, eval_type = parse_evaluation_text(response.choices[0].message.content)
    return insights, eval_type

# choosing actions
def parse_action_text(text):
    # Split the text into lines
    lines = text.split('\n')
    # Loop through each line to find the line starting with "Action:"
    for line in lines:
        if line.startswith("Action:"):
            try:
                action_txt, action_type = line.split("Action:")[1].strip().split(", ")
                return action_txt.strip(), action_type.replace(".", "")
            except:
                return None, "mine"
    return None, "mine"

def get_skill_pddl(task, info, llm_model="gpt-3.5-turbo"):
    query = f"""Task: {translate_task(task)}\nAgent State: {translate_inventory(info)} {translate_equipment(info)} {translate_height(info)}"""

    print("query: ", query)

    response = client.chat.completions.create(
        model=llm_model,
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant in Minecraft. I will give you a task in Minecraft and the agent's current state information. And you need to decide what action to take. Here are some hints for you: (1) You can only equip a tool when you already have it in your inventory, if you don't have any, just do the task directly. (2) NEVER give craft related skill. (3) Decribe things in microcraft style. (4) Focus on current inventory information, do not make things up. (5) You DO NOT stop even if you already have the item in the inventory, we may need more of the item. Output reasoning thought and your final action with its type, the action types are only 'mine', 'equip'."
            },
            {
                "role": "user",
                "content": "Task: Obtain planks\nAgent State: Now my inventory has nothing. Now I equip the air in mainhand. Now I locate in height of 63."
            },
            {
                "role": "assistant",
                "content": "Thought: planks are from logs. I should find tree and chop it down to obtain logs.\nAction: chop down trees and get logs, mine."
            },
            {
                "role": "user",
                "content": "Task: Obtain iron_ore.\nAgent State: Now I have 1 stone_pickaxe, 1 crafting_table, 4 stick, 6 planks in inventory. Now I equip the crafting_table in hand. Now I locate in height of 50."
            },
            {
                "role": "assistant",
                "content": "Thought: Mine iron_ore should use the tool stone pickaxe. I have stone pickaxe in inventory. But I do not equip it now. So I should equip the stone pickaxe. \nAction: equip stone_pickaxe, equip."
            },
            {
                "role": "user",
                "content": "Task: Obtain cobblestone.\nAgent State: Now I have 1 iron_axe in inventory. Now I equip the air in hand. Now I locate in height of 60."
            },
            {
                "role": "assistant",
                "content": "Thought: Equip the iron_axe will accelerate the speed to mine stones. I have an iron_axe in the inventory. So I should equip the iron_axe first.\nAction: equip iron_axe, equip."
            },
            {
                "role": "user",
                "content": "Task: Obtain logs.\nAgent State: Now my inventory has 1 birch_log. Now I equip the birch_log in mainhand. Now I locate in height of 53."
            },
            {
                "role": "assistant",
                "content": "Thought: Though I have birch_log in inventory, the task is still obtain logs. This indicates current logs is not enough, so I should keep getting logs.\nAction: chop down trees and collect logs, mine."
            },
            {
                "role": "user",
                "content": "Task: Obtain logs.\nAgent State: Now I have 1 iron_axe, 1 stone_pickaxe in inventory. Now I equip the air in hand. Now I locate in height of 60."
            },
            {
                "role": "assistant",
                "content": "Thought: Equip a tool will accelerate the speed to chop trees. I have an iron_axe and a stone axe in the inventory. iron_pickaxe is a better tool, so I should equip the iron_axe first.\nAction: equip iron_axe, equip."
            },
            {
                "role": "user",
                "content": "Task: Obtain cobblestone.\nAgent State: Now my inventory has 1 iron_axe, 1 wooden_pickaxe. Now I equip the iron_axe in mainhand. Now I locate in height of 65."
            },
            {
                "role": "assistant",
                "content": "Thought: Minerals like cobblestone can only be obtained using pickaxe. Therefore I need to equip right tool before collecting cobblestone\nAction: equip wooden_pickaxe, equip."
            },
            {
                "role": "user",
                "content": "Task: Obtain cobblestone.\nAgent State: Now my inventory has 1 wooden_pickaxe, 8 oak_planks, 3 dirt. Now I equip the wooden_axe in mainhand. Now I locate in height of 55."
            },
            {
                "role": "assistant",
                "content": "Thought: Cobblestone is common material under earth. Given that I have no cobblestone in inventory, keep digging down should lead me to it.\nAction: dig down, mine."
            },
            {
                "role": "user",
                "content": "Task: Obtain iron_ore.\nAgent State: Now my inventory has 1 iron_axe, 1 wooden_pickaxe, 1 oak_log, 8 oak_planks, 3 cobblestone, 4 dirt. Now I equip the iron_axe in mainhand. Now I locate in height of 52."
            },
            {
                "role": "assistant",
                "content": "Thought: iron_ore is commonly found in large quantities under the ground. But I am using the wrong tools, I need to switch the tool and then mine deeper.\nAction: equip wooden_pickaxe and break stone to obtain iron_ore, mine."
            },
            {
                "role": "user",
                "content": "Task: Obtain diamond.\nAgent State: Now I have 1 iron_pickaxe, 1 crafting_table, 4 stick, 6 planks in inventory. Now I equip the iron_pickaxe in hand. Now I locate in height of 30."
            },
            {
                "role": "assistant",
                "content": "Thought: Diamond in Minecraft only exists in layers under height 15 and above height 5. Now my height is 30, which does not exist diamonds. So I should dig down to lower layers.\nAction: dig down, mine."
            },
            {
                "role": "user",
                "content": query
            }
        ],
        temperature=1,
        max_tokens=256,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0
    )

    print(response.choices[0].message.content)
    action_txt, action_type = parse_action_text(response.choices[0].message.content)
    action_txt = f"get {task}" if action_txt is None else action_txt
    if action_type == "equip":
        object_item = action_txt.split(" ")[-1]
    else:
        object_item = None
    return {
            "text": action_txt,
            "type": action_type,
            "object_item": object_item
        }

import random


def summarize_recipe(item_key, recipes_data, depth=0, stack=None):
    if stack is None:
        stack = set()

    indent = "  " * depth

    if item_key in stack:
        return f"{indent}(Detected cycle for {item_key}, skip)\n"

    stack.add(item_key)

    if item_key not in recipes_data:
        stack.remove(item_key)
        return f"{indent}{item_key} can be obtained by mining or other means.\n"

    recipe_info = recipes_data[item_key]
    recipe_type = recipe_info['type']

    if recipe_type == 'minecraft:crafting_shaped':
        pattern = recipe_info['pattern']
        mat_count = {}
        for row in pattern:
            for c in row:
                if c != ' ':
                    mat_count[c] = mat_count.get(c, 0) + 1

        steps = []
        for symbol, detail in recipe_info['key'].items():
            if "item" in detail:
                mat_item = detail["item"].replace("minecraft:", "")
            elif "tag" in detail:
                mat_item = detail["tag"].replace("minecraft:", "")
            else:
                mat_item = "unknown_material"

            needed = mat_count.get(symbol, 0)
            steps.append((needed, mat_item))

        summary = ""
        for needed, mat_item in steps:
            summary += f"{indent}Item {item_key} => type: {recipe_type}\n"
            summary += f"{indent}- Needs {needed} x {mat_item}\n"
            sub_summary = summarize_recipe(mat_item, recipes_data, depth + 1, stack)
            summary += sub_summary

        stack.remove(item_key)
        return summary

    elif recipe_type == 'minecraft:smelting':
        summary = f"{indent}Item {item_key} => type: {recipe_type}\n"
        ingredient_info = recipe_info['ingredient']
        if "item" in ingredient_info:
            ingredient = ingredient_info["item"].replace("minecraft:", "")
        elif "tag" in ingredient_info:
            ingredient = ingredient_info["tag"].replace("minecraft:", "")
        else:
            ingredient = "unknown_material"

        summary += f"{indent}- Smelt from {ingredient}\n"
        sub_summary = summarize_recipe(ingredient, recipes_data, depth + 1, stack)
        summary += sub_summary

        stack.remove(item_key)
        return summary

    elif recipe_type == 'minecraft:crafting_shapeless':
        summary = f"{indent}Item {item_key} => type: {recipe_type}\n"
        for ingredient in recipe_info["ingredients"]:
            if "item" in ingredient:
                needed_item = ingredient["item"].replace("minecraft:", "")
            elif "tag" in ingredient:
                needed_item = ingredient["tag"].replace("minecraft:", "")
            else:
                needed_item = "unknown_material"

            summary += f"{indent}- Needs {needed_item}\n"
            sub_summary = summarize_recipe(needed_item, recipes_data, depth + 1, stack)
            summary += sub_summary

        stack.remove(item_key)
        return summary

    else:
        summary = f"{indent}Item {item_key} => type: {recipe_type} (unsupported type)\n"
        stack.remove(item_key)
        return summary


def validate_plan(plan):
    if not isinstance(plan, list):
        return False, "Plan is not a list."

    for idx, subgoal in enumerate(plan):
        if not isinstance(subgoal, dict):
            return False, f"Subgoal {idx} is not a dict."
        if "goal" not in subgoal or "type" not in subgoal or "text" not in subgoal:
            return False, f"Subgoal {idx} missing keys among [goal, type, text]."
        if subgoal["type"] not in ["mine", "craft", "smelt"]:
            return False, f"Subgoal {idx} has invalid type: {subgoal['type']} (only mine/craft/smelt allowed)."

    return True, "ok"







def detect_item_dependencies(target_item: str, llm_model="qwen-max") -> list:

    system_prompt = (
        "You are a Minecraft rule expert. Some known constraints:\n"
        "- A wooden pickaxe can gather stone, coal.\n"
        "- A stone pickaxe can gather stone, coal, iron_ore.\n"
        "- An iron pickaxe can gather stone, coal, iron_ore, gold_ore, redstone, diamond.\n"
        "- A crafting_table is needed to craft most tools (like pickaxes) or a furnace.\n"
        "- A furnace is crafted from 8 cobblestone at a crafting_table.\n"
        "- If you want iron_ingots, you must smelt iron_ore in the furnace.\n"
        "- If you want an iron pickaxe, you need iron_ingots, which means iron_ore + furnace.\n"
        "- Stone_pickaxe requires a crafting_table to craft. Wooden_pickaxe also requires a crafting_table.\n"
        "- Typically, you get some wood logs -> craft planks/sticks -> craft a wooden_pickaxe at crafting_table.\n"
        "- Then use wooden_pickaxe to get cobblestone -> craft stone_pickaxe at crafting_table.\n"
        "- Then stone_pickaxe can gather iron_ore -> craft furnace -> smelt iron_ore => iron_ingots -> craft iron_pickaxe.\n\n"

        "If the user wants to obtain any item that involves these resources, ensure the correct pickaxe tier in the correct order.\n"
        "Additionally, consider that to craft or smelt, you also need the prerequisites like a crafting_table, furnace, etc. in a sensible sequence.\n\n"
        "If the target item is crafting_table, just output crafting_table because no previous items required"
        "When the user states an item, you must list ALL required items in an ordered JSON array, from earliest to final.\n"
        "For example, if the user wants an iron pickaxe, the sequence might be:\n"
        "   [\"crafting_table\",\"wooden_pickaxe\",\"stone_pickaxe\",\"furnace\",\"iron_pickaxe\"].\n"
        "No extra items—only the crafting_table, wooden_pickaxe, stone_pickaxe, furnace and iron_pickaxe could be inside the output.\n"
        "No extra explanations—only the JSON array.\n"
    )

    user_prompt = f"I want to get {target_item} in Minecraft. Which items do I need in sequence?"

    response = client.chat.completions.create(
        model=llm_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.7,
        max_tokens=256,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0
    )

    raw_output = response.choices[0].message.content.strip()
    print("Dependency raw LLM output:", raw_output)

    try:
        dep_list = json.loads(raw_output)
        if not isinstance(dep_list, list):
            dep_list = [target_item]
    except:
        dep_list = [target_item]

    return dep_list


def check_items(item_list):
    valid_items = ["crafting_table", "wooden_pickaxe", "stone_pickaxe", "furnace", "iron_pickaxe"]

    for item in item_list:
        if item not in valid_items:
            print(f"Invalid item detected: {item}")
            print("One or more items are invalid.")
            return False
    print("All items are valid.")
    return True



def get_plan(final_goal_list, info, recipes_data, llm_model="qwen-max", max_retries=2):
    if isinstance(final_goal_list, str):
        final_goal_list = [final_goal_list]

    def build_prompt(final_goal_text, merged_recipe_summary,
                     inventory_text, equipment_text, height_text, error_reason=None):
        base_query = (
            f"My current inventory state: {inventory_text}\n"
            f"{equipment_text}\n"
            f"{height_text}\n"
            f"I want to obtain {final_goal_text} in Minecraft step by step.\n\n"
            f"Here is relevant crafting info derived from the JSON:\n"
            f"{merged_recipe_summary}\n"
            "Now please generate a plan as a Python list of subgoals.\n"
            "Each subgoal is a dict with keys: goal, type, text.\n"
            "Valid 'type' must be one of [mine, craft, smelt].\n"
            "For example: [{\"goal\": {\"oak_log\": 4}, \"type\": \"mine\", \"text\": \"oak_log\"}, ... ]\n"
            "Do not include extra explanation. Only output the JSON list.\n"
            "The example is just a format you need follow, don't replicate it exactly.\n"
            "For crafting planks, you can use any type of logs (oak_log, spruce_log, birch_log, etc.) to get the same result.\n"
            "Please do not limit yourself to oak_log if other logs are available. Just use logs.\n"
            "Pay attention word should be exact like 'logs' is valid but 'log' not.\n"
            "Important requirement : planks number always add additional 4, logs always add additional 2, stick number always add additional 2 if needed.\n"
        )
        if error_reason:
            base_query += f"\n[WARNING] Your last output was invalid: {error_reason}\n"
            base_query += "Please correct and return a valid JSON plan.\n"
        return base_query

    inventory_text = translate_inventory(info)
    equipment_text = translate_equipment(info)
    height_text = translate_height(info)

    final_goal_text = ", ".join([f"1 {item}" for item in final_goal_list])


    merged_recipe_summary = ""
    for item in final_goal_list:
        merged_recipe_summary += summarize_recipe(item, recipes_data)
    print("wooden_pickaxe" in recipes_data)  # True/False?
    print("stone_pickaxe" in recipes_data)

    print("==== Merged recipe summary ====")
    print(merged_recipe_summary)

    plan = None
    error_reason = None

    for attempt in range(max_retries):
        query = build_prompt(
            final_goal_text,
            merged_recipe_summary,
            inventory_text,
            equipment_text,
            height_text,
            error_reason
        )

        response = client.chat.completions.create(
            model= llm_model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant in Minecraft. Please produce a multi-step plan in JSON format. No additional text."
                },
                {
                    "role": "user",
                    "content": query
                }
            ],
            temperature=0.7,
            max_tokens=512,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )

        raw_output = response.choices[0].message.content.strip()
        print(f"LLM raw output for plan (attempt {attempt + 1}):", raw_output)

        try:
            candidate_plan = json.loads(raw_output)
        except json.JSONDecodeError:
            error_reason = "JSON parse error"
            continue

        valid, reason = validate_plan(candidate_plan)
        if valid:
            plan = candidate_plan
            break
        else:
            error_reason = reason

    if plan is None:
        fallback_item = final_goal_list[0]
        plan = [{"goal": {fallback_item: 1}, "type": "mine", "text": f"{fallback_item}"}]

    return plan, response.usage


def get_task_and_text_llm(user_input: str):

    options_msg = (
      "We only support these tasks: wooden_pickaxe, stone_pickaxe, iron_pickaxe, diamond.\n"
      "Output your choice in JSON format: {\"task\": \"...\", \"text\": \"...\"}.\n"
      "Where text is the recipe steps for that chosen item."
    )

    possible_texts = {
       "wooden_pickaxe": "To obtain a wooden pickaxe, you need to ...",
       "stone_pickaxe": "To obtain a stone pickaxe, you need to ...",
       "iron_pickaxe": "To obtain an iron pickaxe, you need to ...",
       "diamond": "To obtain a diamond, you need to ..."
    }
    instructions = "Here are possible texts for each task:\n"
    for k, v in possible_texts.items():
        instructions += f"{k}: {v}\n"

    messages = [
        {"role": "system", "content": "You are a helpful assistant in Minecraft."},
        {"role": "user", "content": f"{user_input}\n{options_msg}\n{instructions}"}
    ]

    response = client.chat.completions.create(
        model="qwen-max",
        messages=messages,
        temperature=0.7,
        max_tokens=256
    )

    raw_answer = response.choices[0].message.content.strip()
    print("LLM raw answer:", raw_answer)

    try:
        parsed = json.loads(raw_answer)
        return parsed
    except:
        return {"task": "unknown", "text": "Could not parse LLM output."}

TASK_SKILLS_MAP = {
    "logs": [
        "chop down the tree",
        "equip iron axe to chop down the tree"
    ],
    "cobblestone": [
        "equip wooden_pickaxe",
        "dig down"
    ],
    "iron_ore": [
        "dig down",
        "equip stone pickaxe",
        "break iron_ore blocks",
        "break iron blocks",
        "break the stone blocks and mine iron ore"
    ]
}

SKILL_PRECONDS = {
    "chop down the tree": "",
    "equip iron axe to chop down the tree": "(<= 1 (count minecraft_iron_axe))",
    "equip wooden_pickaxe": "(<= 1 (count minecraft_wooden_pickaxe))",
    "dig down": "(or (equipped minecraft_wooden_pickaxe) (equipped minecraft_stone_pickaxe))",
    "equip stone pickaxe": "(<= 1 (count minecraft_stone_pickaxe))",
    "break iron_ore blocks": "(equipped minecraft_stone_pickaxe)",
    "break iron blocks": "(equipped minecraft_stone_pickaxe)",
    "break the stone blocks and mine iron ore": "(equipped minecraft_stone_pickaxe)"
}

SKILL_CUSTOM_RULES = {
    "dig down": {
        "extra_pre": "(> (agent_height) 15)",
        "extra_eff": "(decrease (agent_height) 5)"
    },
    "break iron_ore blocks": {
        "extra_pre": "(<= (agent_height) 15)",
        "extra_eff": ""
    },
    "break iron blocks": {
        "extra_pre": "(<= (agent_height) 15)",
        "extra_eff": ""
    },
    "break the stone blocks and mine iron ore": {
        "extra_pre": "(<= (agent_height) 15)",
        "extra_eff": ""
    }
}

SKILL_EFFECT_ITEMS = {
    "chop down the tree": "minecraft_logs",
    "equip iron axe to chop down the tree": "(equipped minecraft_iron_axe)",
    "equip wooden_pickaxe": "(equipped minecraft_wooden_pickaxe)",
    "dig down": ["minecraft_cobblestone", "minecraft_iron_ore"],
    "equip stone pickaxe": "(equipped minecraft_stone_pickaxe)",
    "break iron_ore blocks": "minecraft_iron_ore",
    "break iron blocks": "minecraft_iron_ore",
    "break the stone blocks and mine iron ore": "minecraft_iron_ore"
}

def solve_pddl(domain_file: str, problem_file: str) -> List[str]:
    JAVA17_PATH = "/usr/lib/jvm/java-17-openjdk-amd64/bin/java"
    ENHSP_JAR = "lby/json_for_pddl/enhsp.jar"
    try:
        result = subprocess.run(
            [
                JAVA17_PATH,
                "-jar",
                ENHSP_JAR,
                "-o", domain_file,
                "-f", problem_file
            ],
            capture_output=True,
            text=True,
            timeout=30
        )
        print("=== Return code ===")
        print(result.returncode)
        print("=== STDOUT ===")
        print(result.stdout)
        print("=== STDERR ===")
        print(result.stderr)
        if result.returncode != 0:
            print("Solver failed. Stderr:")
            print(result.stderr)
            return []
        lines = result.stdout.splitlines()
        plan_lines = []
        plan_started = False
        for line in lines:
            if plan_started:
                if line.strip():
                    plan_lines.append(line.strip())
            if line.strip().startswith("0."):
                plan_started = True
                plan_lines.append(line.strip())
        return plan_lines
    except Exception as e:
        print("ENHSP failed:", e)
        return []

def generate_domain_pddl_all_skills(
        folder: str,
        skill_preconds: Dict[str, str],
        skill_custom_rules: Dict[str, Dict[str, str]],
        skill_effect_items: Dict[str, str]
) -> str:
    os.makedirs(folder, exist_ok=True)
    all_skills = set(skill_preconds.keys()) | set(skill_custom_rules.keys()) | set(skill_effect_items.keys())
    action_blocks = []
    for skill_name in sorted(all_skills):
        base_pre = skill_preconds.get(skill_name, "").strip()
        custom_rule = skill_custom_rules.get(skill_name, {})
        extra_pre = custom_rule.get("extra_pre", "").strip()
        pre_list = [p for p in [base_pre, extra_pre] if p]
        if pre_list:
            pre_str = "(and " + " ".join(pre_list) + ")"
        else:
            pre_str = "(and)"
        item_to_increase = skill_effect_items.get(skill_name, "")
        eff_list = []
        if isinstance(item_to_increase, str):
            if item_to_increase.startswith("(equipped"):
                eff_list.append(item_to_increase)
            elif item_to_increase.startswith("[") and item_to_increase.endswith("]"):
                try:
                    items_list = json.loads(item_to_increase)
                    for single_item in items_list:
                        eff_list.append(f"(increase (count {single_item}) 1)")
                except:
                    pass
            elif item_to_increase:
                eff_list.append(f"(increase (count {item_to_increase}) 1)")
        elif isinstance(item_to_increase, list):
            for single_item in item_to_increase:
                eff_list.append(f"(increase (count {single_item}) 1)")
        extra_eff = custom_rule.get("extra_eff", "").strip()
        if extra_eff:
            eff_list.append(extra_eff)
        if eff_list:
            eff_str = "(and " + " ".join(eff_list) + ")"
        else:
            eff_str = "(and)"
        action_name = skill_name.replace(" ", "_").replace(",", "")
        action_pddl = f"""
 (:action {action_name}
  :parameters ()
  :precondition {pre_str}
  :effect {eff_str}
 )
"""
        action_blocks.append(action_pddl)
    actions_str = "\n".join(action_blocks)
    domain_template = f"""(define (domain minecraft-domain)
 (:requirements :strips :typing :numeric-fluents)
 (:types item)
 (:predicates (equipped ?tool - item))
 (:functions (count ?item - item) (agent_height))

 {actions_str}
)
"""
    domain_file_path = os.path.join(folder, "domain.pddl")
    with open(domain_file_path, "w") as f:
        f.write(domain_template)
    return domain_file_path

def generate_problem_pddl(task: str, inventory: Dict[str, int], equipment: List[str], current_height: List[int], folder: str) -> str:
    os.makedirs(folder, exist_ok=True)
    object_list = set()
    for item_name in inventory.keys():
        mc_item = f"minecraft_{item_name}"
        object_list.add(mc_item)
    goal_item = f"minecraft_{task}"
    object_list.add(goal_item)
    object_str = " ".join(sorted(object_list)) + " - item"
    init_lines = []
    for item_name, count_val in inventory.items():
        mc_item = f"minecraft_{item_name}"
        init_lines.append(f"(= (count {mc_item}) {count_val})")
    if task not in inventory:
        init_lines.append(f"(= (count minecraft_{task}) 0)")
    h_val = current_height[0] if current_height else 64
    init_lines.append(f"(= (agent_height) {h_val})")
    for eqp in equipment:
        init_lines.append(f"(equipped minecraft_{eqp})")
    init_str = "\n    ".join(init_lines)
    goal_str = f"(<= 1 (count {goal_item}))"
    problem_template = f"""(define (problem minecraft-problem)
 (:domain minecraft-domain)
 (:objects
    {object_str}
 )
 (:init
    {init_str}
 )
 (:goal (and
    {goal_str}
 ))
)
"""
    problem_file_path = os.path.join(folder, "problem.pddl")
    with open(problem_file_path, "w") as f:
        f.write(problem_template)
    return problem_file_path


def get_skill_definitions(
        task_skills_map: Dict[str, List[str]],
        model_client,
        max_retries=3
) -> (Dict[str, str], Dict[str, Dict[str, str]], Dict[str, str]):
    all_skills = set()
    for skill_list in task_skills_map.values():
        all_skills.update(skill_list)
    all_skills = sorted(all_skills)
    base_prompt = f"""
You have a set of possible Minecraft actions (skills). You must produce 3 JSON objects:
1) "SKILL_PRECONDS"    : Each skill => a single PDDL precondition string or "" if none
2) "SKILL_CUSTOM_RULES": Each skill => an object with "extra_pre" and "extra_eff"
3) "SKILL_EFFECT_ITEMS": Each skill => either a single string or a JSON list of item strings, or ""

**CRITICAL**: 
- You must define *all* skills exactly matching the list below, or the answer is invalid.
- All item/tool references must begin with "minecraft_". 
- If an action requires agent y <= 15, use (<= (agent_height) 15). 
- If an action needs a stone pickaxe, use (equipped minecraft_stone_pickaxe).
- If the action can accept wooden or stone pickaxe, use (or (equipped minecraft_wooden_pickaxe) (equipped minecraft_stone_pickaxe)).
- For "dig down", typically do (or (equipped minecraft_wooden_pickaxe) (equipped minecraft_stone_pickaxe)) and (> (agent_height) 15) and effect has (decrease (agent_height) 5) plus producing "minecraft_cobblestone" or "minecraft_iron_ore".
- If you equip something, precond => (<= 1 (count minecraft_xxx)), effect => (equipped minecraft_xxx).
- If you want logs, use "minecraft_logs". If you want iron_ore, use "minecraft_iron_ore".
- Return strictly valid JSON. No code fences, no extra text. 
- The JSON must have keys "SKILL_PRECONDS", "SKILL_CUSTOM_RULES", "SKILL_EFFECT_ITEMS". 
- Each of those 3 must define *every* skill in the list.

Your skill list is:
{json.dumps(all_skills, indent=2, ensure_ascii=False)}

Example minimal structure (not real answers):
{{
  "SKILL_PRECONDS": {{
    "chop down the tree": ""
  }},
  "SKILL_CUSTOM_RULES": {{
    "chop down the tree": {{
      "extra_pre": "",
      "extra_eff": ""
    }}
  }},
  "SKILL_EFFECT_ITEMS": {{
    "chop down the tree": "minecraft_logs"
  }}
}}
Return only that JSON. 
"""
    skill_preconds = {}
    skill_custom_rules = {}
    skill_effect_items = {}
    error_reason = None
    for attempt in range(max_retries):
        if error_reason:
            prompt_with_error = base_prompt + f"\n[Error in prior attempt: {error_reason}]\n"
            prompt_with_error += "Please output valid JSON with the keys SKILL_PRECONDS, SKILL_CUSTOM_RULES, SKILL_EFFECT_ITEMS, covering all skills. No extra text."
        else:
            prompt_with_error = base_prompt
        raw_output, TOKEN_USAGE = model_client.ask(prompt_with_error)
        raw_output = raw_output.strip()
        try:
            data = json.loads(raw_output)
        except json.JSONDecodeError:
            error_reason = "JSON parse error"
            continue
        if not isinstance(data, dict):
            error_reason = "JSON must be a top-level dict"
            continue
        required_keys = ["SKILL_PRECONDS", "SKILL_CUSTOM_RULES", "SKILL_EFFECT_ITEMS"]
        if not all(k in data for k in required_keys):
            error_reason = "Missing required top-level keys"
            continue
        skill_preconds = data["SKILL_PRECONDS"]
        skill_custom_rules = data["SKILL_CUSTOM_RULES"]
        skill_effect_items = data["SKILL_EFFECT_ITEMS"]
        for sk in all_skills:
            if sk not in skill_preconds or sk not in skill_custom_rules or sk not in skill_effect_items:
                error_reason = f"Missing definitions for skill '{sk}'"
                break
        else:
            error_reason = None
        if not error_reason:
            break
    if error_reason:
        print(f"[WARNING] Could not parse valid LLM definitions: {error_reason}")
        skill_preconds = {sk: "" for sk in all_skills}
        skill_custom_rules = {sk: {"extra_pre": "", "extra_eff": ""} for sk in all_skills}
        skill_effect_items = {sk: "" for sk in all_skills}
    return skill_preconds, skill_custom_rules, skill_effect_items, TOKEN_USAGE

class RealLLMClient:
    def __init__(self, llm_type="qwen-max"):
        self.llm_type = llm_type
    def ask(self, prompt_text: str) -> str:
        response = client.chat.completions.create(
            model=self.llm_type,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt_text}
            ],
            temperature=0.7,
            max_tokens=1024
        )
        return response.choices[0].message.content, response.usage


def solve_plan_with_fallback(task: str) -> dict:
    # 第一次尝试：action pddl/domain.pddl
    actioon_plan = solve_pddl('action pddl 2/domain.pddl', 'action pddl/problem.pddl')

    if not actioon_plan:
        # 如果没有解，尝试第二个
        print("try second")
        actioon_plan = solve_pddl('jarvis/assembly/action pddl/domain.pddl',
                                  'action pddl/problem.pddl')

    # 如果依旧没有解，则直接返回默认
    if not actioon_plan:
        print("try default")
        return {
            "text": f"dig_down",
            "type": "mine",
            "object_item": None
        }

    # 如果有解，交给 parse_plan_actions 来进一步解析
    return parse_plan_actions(actioon_plan, task)

def map_action_name(action_name: str) -> str:
    name_map = {
        "break_iron_blocks": "break iron blocks",
        "break_iron_ore_blocks": "break iron_ore blocks",
        "break_the_stone_blocks_and_mine_iron_ore": "break the stone blocks and mine iron ore",
        "chop_down_the_tree": "chop down the tree",
        "dig_down": "dig down",
        "equip_iron_axe_to_chop_down_the_tree": "equip iron axe to chop down the tree",
        "equip_stone_pickaxe": "equip stone pickaxe",
        "equip_wooden_pickaxe": "equip wooden pickaxe"
    }
    return name_map.get(action_name, action_name)

def get_domain_from_llm(folder: str, model_client, max_retries: int = 3) -> str:
    os.makedirs(folder, exist_ok=True)
    domain_file_path = os.path.join(folder, "domain.pddl")

    # Short example snippet (avoid providing the entire domain to prevent verbatim copying)
    example_snippet = """(:action chop_down_the_tree
  :parameters ()
  :precondition (and)
  :effect (and (increase (count minecraft_logs) 1))
)"""

    partial_domain_example = f"""
(define (domain minecraft-domain)
 (:requirements :strips :typing :numeric-fluents)
 (:types item)
 (:predicates (equipped ?tool - item))
 (:functions (count ?item - item) (agent_height))

 ;; Example snippet (not the full domain):
 {example_snippet}
 ...
)""".strip()

    # Skill mapping as JSON (for reference)
    skill_list_json = json.dumps(TASK_SKILLS_MAP, indent=2)

    # --- Updated prompt in English ---
    prompt = f"""
Your task is to produce a complete and valid PDDL domain for Minecraft-like actions. 
Follow these strict rules:

1. **File structure**: It must start with 
   (define (domain minecraft-domain)
   and contain:
   - (:requirements :strips :typing :numeric-fluents)
   - (:types item)
   - (:predicates (equipped ?tool - item))
   - (:functions (count ?item - item) (agent_height))

2. **Action definitions**: 
   You must define 8 actions, logically matching these skill names:
      - break iron blocks
      - break iron_ore blocks
      - break the stone blocks and mine iron ore
      - chop down the tree
      - dig down
      - equip iron axe to chop down the tree
      - equip stone pickaxe
      - equip wooden_pickaxe

   The action names can differ slightly (e.g. break_iron_blocks vs. break-iron-blocks), 
   but they must clearly correspond to the above skills in logic.

3. **Preconditions and effects**:
   - *break iron blocks* and *break iron_ore blocks*: Must require having a stone pickaxe, 
     must also require agent_height <= 30, and must produce minecraft_iron_ore.
   - *break the stone blocks and mine iron ore*: Similar to breaking iron ore, 
     requires a stone pickaxe, agent_height <= 30, and produces minecraft_iron_ore.
   - *chop down the tree*: Has no special precondition (just (and)) or optionally 
     any axe, and produces minecraft_logs.
   - *dig down*: Must have either a wooden or stone pickaxe, must have agent_height > 30, 
     and effects should include producing minecraft_cobblestone, producing minecraft_iron_ore, 
     and reducing agent_height by some numeric (e.g. (decrease (agent_height) 5)).
   - *equip iron axe to chop down the tree*: Must have a precondition indicating 
     you have at least one iron axe in your count, e.g. (<= 1 (count minecraft_iron_axe)), 
     and effect should equip minecraft_iron_axe.
   - *equip stone pickaxe* and *equip wooden_pickaxe*: Similar logic; 
     if you want to equip stone pickaxe, you must have (<= 1 (count minecraft_stone_pickaxe)) 
     in precondition, and effect is (equipped minecraft_stone_pickaxe), etc.

4. **Naming**:
   - Every item in preconditions or effects should begin with 'minecraft_', e.g. 
     (equipped minecraft_stone_pickaxe).
   - The final domain must be syntactically valid. 
   - Avoid extra commentary, code fences, or any format other than the PDDL text.

For reference, here is a small partial example (NOT the full domain):
{partial_domain_example}

Skill mapping information:
{skill_list_json}

Now, please return **only** the complete domain.pddl text (no code blocks, no explanations). 
Make sure it meets the numeric preconditions (<= or > for agent_height), 
produces the right items (minecraft_logs, minecraft_iron_ore, minecraft_cobblestone), 
and uses the correct structure for equipping items.

If you cannot satisfy the above requirements on the first try, try to correct your domain 
until it meets all points. Remember: do not copy verbatim from the example; 
the domain must be original but logically equivalent.
"""

    domain_text = ""
    error_reason = None

    for attempt in range(max_retries):
        if error_reason:
            full_prompt = (
                    prompt
                    + f"\n[Error in attempt {attempt}: {error_reason}]\nPlease fix any issues and try again."
            )
        else:
            full_prompt = prompt

        raw_output, TOKEN_USAGE = model_client.ask(full_prompt)
        raw_output = raw_output.strip()

        # Quick checks: must start with (define (domain...) and contain "(:action"
        if not raw_output.startswith("(define (domain"):
            error_reason = "Domain must start with (define (domain..."
            continue
        if "(:action " not in raw_output:
            error_reason = "No (:action) definitions found"
            continue

        # Passed checks
        domain_text = raw_output
        break

    # If no valid domain after retries, write an empty template.
    if not domain_text:
        domain_text = """(define (domain minecraft-domain)
 (:requirements :strips :typing :numeric-fluents)
 (:types item)
 (:predicates (equipped ?tool - item))
 (:functions (count ?item - item) (agent_height))
)
"""

    with open(domain_file_path, "w", encoding="utf-8") as f:
        f.write(domain_text)

    return domain_file_path, TOKEN_USAGE

class JARVIS:
    def __init__(self, model = 'gpt-3.5-turbo'):
        self.model = model

    # TODO: add online generating plans function 
    # zhwang4ai: release online planning agent in the next version 
