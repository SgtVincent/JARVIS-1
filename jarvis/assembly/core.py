from jarvis.assembly.base import client
from jarvis.assembly.base import skills
import random 
import time
import openai
import json

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
    query = f"Task: {translate_task(task)}.\nSkills: {skill_content}\nAgent State: {translate_inventory(info)} {translate_equipment(info)} {translate_height(info)}"
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
    print(response.choices[0].message.content)
    action_index = parse_action_index(response.choices[0].message.content)
    if not action_index or action_index > len( skills[task]): # if no action or action beyond task skills
        return random.choice(skills[task])
    return skills[task][action_index-1]

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

# def get_plan(final_goal, info, recipes_data, max_retries=2):
#     def build_prompt(final_goal_text, recipe_summary, inventory_text, equipment_text, height_text, error_reason=None):
#         base_query = (
#             f"My current inventory state: {inventory_text}\n"
#             f"{equipment_text}\n"
#             f"{height_text}\n"
#             f"I want to obtain {final_goal_text} in Minecraft step by step.\n\n"
#             f"Here is relevant crafting info derived from the JSON:\n"
#             f"{recipe_summary}\n"
#             "Now please generate a plan as a Python list of subgoals.\n"
#             "Each subgoal is a dict with keys: goal, type, text.\n"
#             "Valid 'type' must be one of [mine, craft, smelt].\n"
#             "For example: [{\"goal\": {\"oak_log\": 4}, \"type\": \"mine\", \"text\": \"oak_log\"}, ... ]\n"
#             "Do not include extra explanation. Only output the JSON list.\n"
#             "The example is just a format you need follow, don't replicate it exactly.\n"
#             "For crafting planks, you can use any type of logs (oak_log, spruce_log, birch_log, etc.) to get the same result. Please do not limit yourself to oak_log if other logs are available. Just use logs\n"
#             "Pay attention word should be exact like 'logs' is valid but 'log' not.\n"
#
#         )
#         if error_reason:
#             base_query += f"\n[WARNING] Your last output was invalid: {error_reason}\n"
#             base_query += "Please correct and return a valid JSON plan.\n"
#         return base_query
#
#     inventory_text = translate_inventory(info)
#     equipment_text = translate_equipment(info)
#     height_text = translate_height(info)
#
#     if isinstance(final_goal, dict):
#         final_goal_text = ", ".join([f"{v} {k}" for k, v in final_goal.items()])
#         main_item = list(final_goal.keys())[0]
#     else:
#         final_goal_text = f"1 {final_goal}"
#         main_item = final_goal
#
#     recipe_summary = summarize_recipe(main_item, recipes_data)
#     print("recipe_summary:",recipe_summary)
#
#     plan = None
#     error_reason = None
#
#     for attempt in range(max_retries):
#         query = build_prompt(final_goal_text, recipe_summary, inventory_text, equipment_text, height_text, error_reason)
#
#         response = client.chat.completions.create(
#             model="qwen-max",
#             messages=[
#                 {
#                     "role": "system",
#                     "content": "You are a helpful assistant in Minecraft. Please produce a multi-step plan in JSON format. No additional text."
#                 },
#                 {
#                     "role": "user",
#                     "content": query
#                 }
#             ],
#             temperature=0.7,
#             max_tokens=512,
#             top_p=1,
#             frequency_penalty=0,
#             presence_penalty=0
#         )
#
#         raw_output = response.choices[0].message.content.strip()
#         print(f"LLM raw output for plan (attempt {attempt+1}):", raw_output)
#
#         try:
#             candidate_plan = json.loads(raw_output)
#         except json.JSONDecodeError:
#             error_reason = "JSON parse error"
#             continue
#         valid, reason = validate_plan(candidate_plan)
#         if valid:
#             plan = candidate_plan
#             break
#         else:
#             error_reason = reason
#
#     if plan is None:
#         plan = [{"goal": {str(final_goal): 1}, "type": "mine", "text": f"{final_goal}"}]
#
#     return plan

def get_plan(final_goal_list, info, recipes_data, max_retries=2):
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
            "IMportant requirement : planks number always add additional 2, logs always add additional 1\n"
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
            model="qwen-max",
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

        # 尝试解析 JSON
        try:
            candidate_plan = json.loads(raw_output)
        except json.JSONDecodeError:
            error_reason = "JSON parse error"
            continue

        # type in [mine, craft, smelt]
        valid, reason = validate_plan(candidate_plan)
        if valid:
            plan = candidate_plan
            break
        else:
            error_reason = reason

    # 如果最终还是不行，fallback 到一个最简单的plan
    if plan is None:
        # 简单地拿 final_goal_list 的第一个当成 fallback
        fallback_item = final_goal_list[0]
        plan = [{"goal": {fallback_item: 1}, "type": "mine", "text": f"{fallback_item}"}]

    return plan


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

class JARVIS:
    def __init__(self, model = 'gpt-3.5-turbo'):
        self.model = model

    # TODO: add online generating plans function 
    # zhwang4ai: release online planning agent in the next version 
