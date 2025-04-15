import os
import subprocess
import json
from typing import List, Dict
import openai
from jarvis.assembly.base import client

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
        raw_output = model_client.ask(prompt_with_error).strip()
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
    return skill_preconds, skill_custom_rules, skill_effect_items

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

def generate_problem_pddl(
        task: str,
        inventory: Dict[str, int],
        equipment: List[str],
        current_height: List[int],
        folder: str
) -> str:
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
    class RealLLMClient:
        def ask(self, prompt_text: str) -> str:
            response = client.chat.completions.create(
                model="qwen-max",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt_text}
                ],
                temperature=0.7,
                max_tokens=1024
            )
            return response.choices[0].message.content
    model_client = RealLLMClient()
    skill_preconds, skill_custom_rules, skill_effect_items = get_skill_definitions(
        TASK_SKILLS_MAP, model_client
    )
    folder_name = "action_pddl"
    domain_file = generate_domain_pddl_all_skills(
        folder_name,
        skill_preconds,
        skill_custom_rules,
        skill_effect_items
    )
    test_task = "cobblestone"
    test_inventory = {
        'wooden_pickaxe': 1,
        'oak_planks': 3,
        'dirt': 4,
        'stick': 2,
        'oak_log': 1,
        'iron_axe': 1
    }
    test_equipment = ["wooden_pickaxe"]
    test_height = [59]
    problem_file = generate_problem_pddl(
        test_task,
        test_inventory,
        test_equipment,
        test_height,
        folder_name
    )
    plan = solve_pddl(domain_file, problem_file)
    print("=== Final Plan ===")
    if plan:
        for step in plan:
            print(step)
    else:
        print("No plan found or solver failed.")
