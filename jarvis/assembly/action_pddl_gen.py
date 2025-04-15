import os
import subprocess
from typing import List, Dict

# ------------------------------------------
# 任务到技能映射
# ------------------------------------------
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

# ------------------------------------------
# 基础前置条件：检查背包或装备
# ------------------------------------------
SKILL_PRECONDS = {
    "chop down the tree": "",
    "equip iron axe to chop down the tree": "(<= 1 (count minecraft_iron_axe))",
    "equip wooden_pickaxe": "(<= 1 (count minecraft_wooden_pickaxe))",
    # dig down 需要已装备木镐 或 石镐
    "dig down": "(or (equipped minecraft_wooden_pickaxe) (equipped minecraft_stone_pickaxe))",
    # 装备石镐需要背包里有 stone_pickaxe
    "equip stone pickaxe": "(<= 1 (count minecraft_stone_pickaxe))",
    # 挖铁矿 / 破铁块 / 等都需要装备了石镐
    "break iron_ore blocks": "(equipped minecraft_stone_pickaxe)",
    "break iron blocks": "(equipped minecraft_stone_pickaxe)",
    "break the stone blocks and mine iron ore": "(equipped minecraft_stone_pickaxe)"
}

# ------------------------------------------
# 自定义规则(额外前提/效果)：如高度要求、下降
# ------------------------------------------
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

# ------------------------------------------
# 技能 -> 产出物品, 或装备动作 -> 设置 (equipped)
# ------------------------------------------
SKILL_EFFECT_ITEMS = {
    "chop down the tree": "minecraft_logs",

    # 装备铁斧后可砍树, 前置条件: 背包有 iron_axe; 效果: 装备 iron_axe
    "equip iron axe to chop down the tree": "(equipped minecraft_iron_axe)",

    # 装备木镐
    "equip wooden_pickaxe": "(equipped minecraft_wooden_pickaxe)",

    # dig down: 同时挖到 cobblestone, iron_ore, 并在 SKILL_CUSTOM_RULES 中让 agent_height -5
    "dig down": ["minecraft_cobblestone", "minecraft_iron_ore"],

    # 装备石镐
    "equip stone pickaxe": "(equipped minecraft_stone_pickaxe)",

    # 挖铁矿石、破铁块等产出 iron_ore
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

def generate_domain_pddl_all_skills(folder: str) -> str:
    os.makedirs(folder, exist_ok=True)
    all_skills = set()
    for skill_list in TASK_SKILLS_MAP.values():
        all_skills.update(skill_list)
    all_skills.update(SKILL_PRECONDS.keys())
    all_skills.update(SKILL_CUSTOM_RULES.keys())

    action_blocks = []
    for skill_name in sorted(all_skills):
        base_pre = SKILL_PRECONDS.get(skill_name, "").strip()
        custom_rule = SKILL_CUSTOM_RULES.get(skill_name, {})
        extra_pre = custom_rule.get("extra_pre", "").strip()
        pre_list = []
        if base_pre:
            pre_list.append(base_pre)
        if extra_pre:
            pre_list.append(extra_pre)
        if pre_list:
            pre_str = "(and " + " ".join(pre_list) + ")"
        else:
            pre_str = "(and)"

        item_to_increase = SKILL_EFFECT_ITEMS.get(skill_name, "")
        eff_list = []
        if isinstance(item_to_increase, str):
            # 如果是字符串, 可能是 "(equipped minecraft_iron_axe)" 或 "minecraft_logs"
            if item_to_increase.startswith("(equipped"):
                eff_list.append(item_to_increase)
            elif item_to_increase:
                eff_list.append(f"(increase (count {item_to_increase}) 1)")
        elif isinstance(item_to_increase, list):
            # 若是列表, 表示要同时产出多种物品
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

if __name__ == "__main__":
    folder_name = "action pddl"
    test_task = "cobblestone"
    test_inventory = {'wooden_pickaxe': 1, 'oak_planks': 3, 'dirt': 4, 'stick': 2, 'oak_log': 1, 'iron_axe': 1}
    test_equipment = ["wooden_pickaxe"]
    test_height = [59]
    domain_file = generate_domain_pddl_all_skills(folder_name)
    problem_file = generate_problem_pddl(test_task, test_inventory, test_equipment, test_height, folder_name)
    plan = solve_pddl(domain_file, problem_file)
    print("=== Final Plan ===")
    if plan:
        for step in plan:
            print(step)
    else:
        print("No plan found or solver failed.")