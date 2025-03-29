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
                return "", "proceed"
    return None, "proceed"

def evaluate_plan(plan, llm_model="gpt-3.5-turbo"):
    query = f"""Task: {translate_task(plan[-1]['text'])}.\nCurrent plan: {translate_plan(plan)}."""
    response = client.chat.completions.create(
        model=llm_model,
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant in Minecraft. I will give you a task in Minecraft and agent's current plan for the task. You need to evaluate the plan and provide your insights. Here are some hints for you: (1) If the plan is reasonable enough, proceed it. (2) If you think adding additional plan can benefit the task, refine it. (3) Only focus on high level and specific objects, do not propose basic items or abstract objects. (4) Do not propose objects that are already in the plan. (5) If refine, only add one object. Output your thought and your evaluation result."
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
                "content": "Task: Obtain wooden_pickaxe\nCurrent plan: mine logs, craft planks, craft crafting_table, craft stick, craft wooden_pickaxe."
            },
            {
                "role": "assistant",
                "content": "Thought: Necessay ingredients are collected before making wooden_pickaxe, no need to change the plan.\nEvaluation: reasonable plan, proceed."
            },
            {
                "role": "user",
                "content": "Task: Obtain wooden_pickaxe\nCurrent plan: mine logs, craft planks, craft stick, craft wooden_pickaxe."
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
                "content": "Thought: Mine cobblestone is laborous with hand, crafting wooden_pickaxe ahead can make it eaiser.\nEvaluation: reasonable plan, proceed."
            },            
            {
                "role": "user",
                "content": "Task: Obtain iron_pickaxe\nCurrent plan: mine logs, craft planks, craft crafting_table, craft stick, craft wooden_pickaxe, mine cobblestone, craft furnace, mine iron_ore, smelt iron_ingot, craft iron_pickaxe."
            },
            {
                "role": "assistant",
                "content": "Thought: Mine iron_ore is laborous even with wooden_pickaxe, it's beneficial to craft stone_pickaxe ahead to facilicate mining.\nEvaluation: stone_pickaxe, refine."
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
                "content": "You are a helpful assistant in Minecraft. I will give you a task in Minecraft and the agent's current state information. And you need to decide what action to take. Here are some hints for you: (1) You can only equip tool when you already have it in your inventory. (2) Do not consider any crafting acitons (3) Decribe things with microcraft terms. Output reasoning thought and your final action with type, the action types are only 'mine', 'equip'."
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
                "content": "Task: Obtain iron_ore.\nAgent State: Now I have 1 stone pickaxe, 1 crafting_table, 4 stick, 6 planks in inventory. Now I equip the crafting_table in hand. Now I locate in height of 50."
            },
            {
                "role": "assistant",
                "content": "Thought: Mine iron ore should use the tool stone pickaxe. I have stone pickaxe in inventory. But I do not equip it now. So I should equip the stone pickaxe. \nAction: equip stone pickaxe, equip."
            },
            {
                "role": "user",
                "content": "Task: Obtain logs.\nAgent State: Now I have 1 iron_axe in inventory. Now I equip the air in hand. Now I locate in height of 60."
            },
            {
                "role": "assistant",
                "content": "Thought: Equip the iron axe will accelerate the speed to chop trees. I have an iron axe in the inventory. So I should equip the iron axe first.\nAction: equip iron axe, equip."
            },
            {
                "role": "user",
                "content": "Task: Obtain logs.\nAgent State: Now I have 1 iron_axe, 1 stone pickaxe in inventory. Now I equip the air in hand. Now I locate in height of 60."
            },
            {
                "role": "assistant",
                "content": "Thought: Equip the axe will accelerate the speed to chop trees. I have an iron axe and a stone axe in the inventory. Iron pickaxe is a better tool, so I should equip the iron axe first.\nAction: equip iron axe, equip."
            },
            {
                "role": "user",
                "content": "Task: Obtain diamond.\nAgent State: Now I have 1 iron pickaxe, 1 crafting_table, 4 stick, 6 planks in inventory. Now I equip the iron_pickaxe in hand. Now I locate in height of 30."
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
    return {
            "text": action_txt,
            "type": action_type,
            "object_item": None
        }

class JARVIS:
    def __init__(self, model = 'gpt-3.5-turbo'):
        self.model = model

    # TODO: add online generating plans function 
    # zhwang4ai: release online planning agent in the next version 
