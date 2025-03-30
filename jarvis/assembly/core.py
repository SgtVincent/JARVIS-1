from jarvis.assembly.base import client
from jarvis.assembly.base import skills
import random 
import time
import openai

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

def summarize_recipe(item_key, recipes_data, depth=0, visited=None):
    if visited is None:
        visited = set()
    if item_key in visited:
        return ""
    visited.add(item_key)

    if item_key not in recipes_data:
        return f"{item_key} can be obtained by mining or other means.\n"

    recipe_info = recipes_data[item_key]
    summary = f"Item {item_key} => type: {recipe_info['type']}\n"

    if recipe_info['type'] == 'minecraft:crafting_shaped':
        pattern = recipe_info['pattern']
        mat_count = {}
        for row in pattern:
            for c in row:
                if c != ' ':
                    mat_count[c] = mat_count.get(c, 0) + 1
        for symbol, detail in recipe_info['key'].items():
            mat_item = detail['item'].replace("minecraft:", "")
            needed = mat_count.get(symbol, 0)
            summary += f"- Needs {needed} x {mat_item}\n"
            summary += summarize_recipe(mat_item, recipes_data, depth+1, visited)

    elif recipe_info['type'] == 'minecraft:smelting':
        ingredient = recipe_info['ingredient'].replace("minecraft:", "")
        summary += f"- Smelt from {ingredient}\n"
        summary += summarize_recipe(ingredient, recipes_data, depth+1, visited)


    return summary

def get_plan(final_goal, info, recipes_data):

    inventory_text = translate_inventory(info)
    equipment_text = translate_equipment(info)
    height_text = translate_height(info)

    if isinstance(final_goal, dict):
        final_goal_text = ", ".join([f"{v} {k}" for k,v in final_goal.items()])
        main_item = list(final_goal.keys())[0]
    else:
        final_goal_text = f"1 {final_goal}"
        main_item = final_goal

    recipe_summary = summarize_recipe(main_item, recipes_data)

    query = (
        f"My current inventory state: {inventory_text}\n"
        f"{equipment_text}\n"
        f"{height_text}\n"
        f"I want to obtain {final_goal_text} in Minecraft step by step.\n\n"
        f"Here is relevant crafting info derived from the JSON:\n"
        f"{recipe_summary}\n"
        "Now please generate a plan as a Python list of subgoals.\n"
        "Each subgoal is a dict with keys: goal, type, text.\n"
        "For example: [{\"goal\": {\"oak_log\": 4}, \"type\": \"mine\", \"text\": \"oak_log\"}, ... ]\n"
        "Do not include extra explanation. Only output the JSON list.\n"
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
    print("LLM raw output for plan:", raw_output)

    try:
        plan = json.loads(raw_output)
    except json.JSONDecodeError:
        plan = [
            {"goal": {str(final_goal): 1}, "type": "mine", "text": f"{final_goal}"}
        ]

    return plan
import json

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
