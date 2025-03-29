import json
import argparse
from collections import defaultdict, deque
from unified_planning.shortcuts import *
from unified_planning.model.types import *
from unified_planning.io import PDDLWriter
import subprocess
import os

PDDL_DATA_PATH = "/home/marmot/Boyang/JARVIS-1/lby/json_for_pddl"
PDDL_RESULT_PATH = "/home/marmot/Boyang/JARVIS-1/lby/json_for_pddl/generated_pddl"

# === 配置和加载 ===
with open(os.path.join(PDDL_DATA_PATH,"cared_recipies.json")) as f:
    recipes_raw = json.load(f)
with open(os.path.join(PDDL_DATA_PATH,"cared_ingredients.json")) as f:
    cared_ingredients = json.load(f)

def normalize(name):
    return name if name.startswith("minecraft:") else f"minecraft:{name}"

def get_result_item(recipe):
    r = recipe.get("result")
    return r if isinstance(r, str) else r.get("item")

def get_result_count(recipe):
    r = recipe.get("result")
    return 1 if isinstance(r, str) else r.get("count", 1)

USED_RECIPE = {normalize(k): v for k, v in recipes_raw.items() if get_result_item(v)}

tag_map = {
    "minecraft:planks": ["minecraft:planks"],
    "minecraft:logs": ["minecraft:logs"]
}

# === 合成路径提取（精细级别） ===
def extract_primitive_steps(target, recipes=USED_RECIPE):
    queue = deque()
    steps = []
    visited = defaultdict(int)
    queue.append((target, 1))

    while queue:
        current, qty = queue.popleft()

        if visited[current] > 0:
            continue
        visited[current] += qty

        recipe = recipes.get(current)
        if not recipe:
            for _ in range(qty):
                steps.append(("collect", current))
            continue

        ing_list = []
        if recipe["type"] == "minecraft:smelting":
            ing = recipe["ingredient"]
            item = normalize(ing.get("item") or tag_map.get(ing.get("tag"), ["minecraft:dirt"])[0])
            ing_list.append((item, qty))
            if current != "minecraft:furnace":
                ing_list.append(("minecraft:furnace", 1))
        elif recipe["type"] == "minecraft:crafting_shaped":
            pattern = recipe.get("pattern", [])
            key = recipe.get("key", {})
            ing_counter = defaultdict(int)
            for row in pattern:
                for c in row:
                    if c != " " and c in key:
                        ing = key[c]
                        item = normalize(ing.get("item") or tag_map.get(ing.get("tag"), ["minecraft:dirt"])[0])
                        ing_counter[item] += 1
            for ing, count in ing_counter.items():
                ing_list.append((ing, qty * count))
            if current != "minecraft:crafting_table" and current != "minecraft:planks":
                ing_list.append(("minecraft:crafting_table", 1))
        elif recipe["type"] == "minecraft:crafting_shapeless":
            for ing in recipe.get("ingredients", []):
                item = normalize(ing.get("item") or tag_map.get(ing.get("tag"), ["minecraft:dirt"])[0])
                ing_list.append((item, qty))
            if current != "minecraft:crafting_table" and current != "minecraft:planks":
                ing_list.append(("minecraft:crafting_table", 1))

        for ing, need_qty in ing_list:
            queue.append((ing, need_qty))

        label = "smelt" if recipe["type"] == "minecraft:smelting" else "make"
        for _ in range(qty):
            steps.append((label, current))

    return steps[::-1]

# === domain.pddl 和 problem.pddl 生成 ===
def write_domain_and_problem(target, steps):
    Item = UserType("item")
    count = Fluent("count", IntType(0, 9999), item=Item)
    problem = Problem("minecraft-domain")
    problem.add_fluent(count)
    all_items = set(normalize(s[1]) for s in steps)
    obj_map = {i: Object(i.replace(":", "_"), Item) for i in all_items}
    for o in obj_map.values():
        problem.add_object(o)

    # 只为没有配方的物品定义 collect
    for i in all_items:
        if i not in USED_RECIPE and not i.endswith(":planks"):
            action = InstantaneousAction(f"collect__{i.replace('minecraft:', '')}")
            itm = obj_map[i]
            action.add_increase_effect(count(itm), 1)
            problem.add_action(action)

    for name, recipe in USED_RECIPE.items():
        if name not in all_items:
            continue
        result = obj_map[name]
        label = "smelt" if recipe["type"] == "minecraft:smelting" else "make"
        action = InstantaneousAction(f"{label}__{name.replace('minecraft:', '')}")
        if recipe["type"] == "minecraft:smelting":
            ing = normalize(recipe["ingredient"].get("item") or tag_map.get(recipe["ingredient"].get("tag"), ["minecraft:dirt"])[0])
            ing_obj = obj_map[ing]
            action.add_precondition(GE(count(ing_obj), 1))
            action.add_decrease_effect(count(ing_obj), 1)
            action.add_increase_effect(count(result), 1)
            if name != "minecraft:furnace":
                furnace = obj_map.get("minecraft:furnace")
                if furnace:
                    action.add_precondition(GE(count(furnace), 1))
        elif recipe["type"] in ["minecraft:crafting_shaped", "minecraft:crafting_shapeless"]:
            ingredients = defaultdict(int)
            if recipe["type"] == "minecraft:crafting_shaped":
                for row in recipe.get("pattern", []):
                    for c in row:
                        if c != " ":
                            v = recipe["key"].get(c)
                            if v:
                                ing = normalize(v.get("item") or tag_map.get(v.get("tag"), ["minecraft:dirt"])[0])
                                ingredients[ing] += 1
            else:
                for ing in recipe.get("ingredients", []):
                    item = normalize(ing.get("item") or tag_map.get(ing.get("tag"), ["minecraft:dirt"])[0])
                    ingredients[item] += 1

            for ing, qty in ingredients.items():
                ing_obj = obj_map[ing]
                action.add_precondition(GE(count(ing_obj), qty))
                action.add_decrease_effect(count(ing_obj), qty)
            action.add_increase_effect(count(result), get_result_count(recipe))
            if name != "minecraft:crafting_table" and name != "minecraft:planks":
                table = obj_map.get("minecraft:crafting_table")
                if table:
                    action.add_precondition(GE(count(table), 1))

        problem.add_action(action)

    for item in obj_map:
        init_val = 0
        problem.set_initial_value(count(obj_map[item]), init_val)
    goal = obj_map[target]
    problem.add_goal(GE(count(goal), 1))


    writer = PDDLWriter(problem)
    domain_file = os.path.join(PDDL_RESULT_PATH, "domain.pddl")
    problem_file = os.path.join(PDDL_RESULT_PATH,f"problem_{target.replace('minecraft:', '')}.pddl")
    writer.write_domain(domain_file)
    writer.write_problem(problem_file)
    print("domain.pddl, problem generated")

    # === 自动调用 ENHSP 获取 plan ===
    try:
        JAVA17 = "/usr/lib/jvm/java-1.17.0-openjdk-amd64/bin/java"
        result = subprocess.run([
            JAVA17, "-jar", os.path.join(PDDL_DATA_PATH, "enhsp.jar"), "-o", domain_file, "-f", problem_file
        ], capture_output=True, text=True, timeout=30)
        txt_output = result.stdout
        try:
            start = txt_output.index("0.0:")
            end   = txt_output.index("Plan-Length")
            extracted_steps = txt_output[start:end].strip()
        except:
            extracted_steps = None
            
        lines = result.stdout.splitlines()
        plan_started = False
        plan_lines = []
        for line in lines:
            if plan_started:
                if line.strip():
                    plan_lines.append(line.strip())
            if line.strip().startswith("0."):
                plan_started = True
                plan_lines.append(line.strip())
        print("Generate Plan:")
        for line in plan_lines:
            print(line)
        
        return extracted_steps
    except Exception as e:
        print(" ENHSP failed:", e)

# === CLI 入口 ===
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("target", type=str)
    args = parser.parse_args()
    plan_steps = extract_primitive_steps(args.target, USED_RECIPE)

    write_domain_and_problem(args.target, plan_steps)


# # === domain.pddl 和 problem.pddl 生成 ===
# def write_domain_and_problem(target, steps):
#     Item = UserType("item")
#     count = Fluent("count", IntType(0, 9999), item=Item)
#     problem = Problem("minecraft-domain")
#     problem.add_fluent(count)
#     all_items = set(normalize(s[1]) for s in steps)
#     obj_map = {i: Object(i.replace(":", "_"), Item) for i in all_items}
#     for o in obj_map.values():
#         problem.add_object(o)

#     # 只为没有配方的物品定义 collect
#     for i in all_items:
#         if i not in recipes:
#             action = InstantaneousAction(f"collect__{i.replace('minecraft:', '')}")
#             itm = obj_map[i]
#             action.add_increase_effect(count(itm), 1)
#             problem.add_action(action)

#     for name, recipe in recipes.items():
#         if name not in all_items:
#             continue
#         result = obj_map[name]
#         action = InstantaneousAction(f"make__{name.replace('minecraft:', '')}")
#         if recipe["type"] == "minecraft:smelting":
#             ing = normalize(recipe["ingredient"].get("item") or tag_map.get(recipe["ingredient"].get("tag"), ["minecraft:dirt"])[0])
#             ing_obj = obj_map[ing]
#             action.add_precondition(GE(count(ing_obj), 1))
#             action.add_decrease_effect(count(ing_obj), 1)
#             action.add_increase_effect(count(result), 1)
#             if name != "minecraft:furnace":
#                 furnace = obj_map.get("minecraft:furnace")
#                 if furnace:
#                     action.add_precondition(GE(count(furnace), 1))
#         elif recipe["type"] in ["minecraft:crafting_shaped", "minecraft:crafting_shapeless"]:
#             ingredients = defaultdict(int)
#             if recipe["type"] == "minecraft:crafting_shaped":
#                 for row in recipe.get("pattern", []):
#                     for c in row:
#                         if c != " ":
#                             v = recipe["key"].get(c)
#                             if v:
#                                 ing = normalize(v.get("item") or tag_map.get(v.get("tag"), ["minecraft:dirt"])[0])
#                                 ingredients[ing] += 1
#             else:
#                 for ing in recipe.get("ingredients", []):
#                     item = normalize(ing.get("item") or tag_map.get(ing.get("tag"), ["minecraft:dirt"])[0])
#                     ingredients[item] += 1

#             for ing, qty in ingredients.items():
#                 ing_obj = obj_map[ing]
#                 action.add_precondition(GE(count(ing_obj), qty))
#                 action.add_decrease_effect(count(ing_obj), qty)
#             action.add_increase_effect(count(result), get_result_count(recipe))
#             if name != "minecraft:crafting_table":
#                 table = obj_map.get("minecraft:crafting_table")
#                 if table:
#                     action.add_precondition(GE(count(table), 1))

#         problem.add_action(action)

#     for item in obj_map:
#         init_val = 0
#         problem.set_initial_value(count(obj_map[item]), init_val)
#     goal = obj_map[target]
#     problem.add_goal(GE(count(goal), 1))

#     writer = PDDLWriter(problem)
#     writer.write_domain("domain.pddl")
#     writer.write_problem(f"problem_{target.replace('minecraft:', '')}.pddl")
#     print("domain.pddl, problem generated")

#     # === 自动调用 ENHSP 获取 plan ===
#     try:
#         result = subprocess.run([
#             "java", "-jar", "enhsp.jar", "-o", "domain.pddl", "-f", f"problem_{target.replace('minecraft:', '')}.pddl"
#         ], capture_output=True, text=True, timeout=30)
#         lines = result.stdout.splitlines()
#         plan_started = False
#         plan_lines = []
#         for line in lines:
#             if plan_started:
#                 if line.strip():
#                     plan_lines.append(line.strip())
#             if line.strip().startswith("0."):
#                 plan_started = True
#                 plan_lines.append(line.strip())
#         print("Generate Plan:")
#         for line in plan_lines:
#             print(line)
#     except Exception as e:
#         print(" ENHSP failed:", e)

# # === 合成动作提取 ===
# def extract_all_actions(recipes):
#     Item = UserType("item")
#     count = Fluent("count", IntType(0, 9999), item=Item)
#     actions = []
#     all_items = set()

#     for result_name, recipe in recipes.items():
#         result = normalize(get_result_item(recipe))
#         all_items.add(result)
#         if recipe["type"] == "minecraft:smelting":
#             ing = normalize(recipe["ingredient"]["item"])
#             all_items.add(ing)
#             all_items.add("minecraft:furnace")
#         elif recipe["type"] == "minecraft:crafting_shaped":
#             key = recipe.get("key", {})
#             pattern = recipe.get("pattern", [])
#             for row in pattern:
#                 for c in row:
#                     if c != " " and c in key:
#                         if "item" in key[c]:
#                             all_items.add(normalize(key[c]["item"]))
#                         elif "tag" in key[c]:
#                             all_items.add(normalize(tag_map[key[c]["tag"]][0]))
#             if get_result_item(recipe) != "minecraft:crafting_table":
#                 all_items.add("minecraft:crafting_table")

#     objects = {item: Object(item.replace(":", "_"), Item) for item in all_items}

#     for result_name, recipe in recipes.items():
#         result = normalize(get_result_item(recipe))
#         result_obj = objects[result]
#         action = InstantaneousAction(f"make__{result.replace('minecraft:', '')}")

#         if recipe["type"] == "minecraft:smelting":
#             ing = normalize(recipe["ingredient"]["item"])
#             ing_obj = objects[ing]
#             action.add_precondition(GE(count(ing_obj), 1))
#             action.add_decrease_effect(count(ing_obj), 1)
#             action.add_increase_effect(count(result_obj), 1)
#             if result != "minecraft:furnace":
#                 action.add_precondition(GE(count(objects["minecraft:furnace"]), 1))

#         elif recipe["type"] == "minecraft:crafting_shaped":
#             key = recipe.get("key", {})
#             pattern = recipe.get("pattern", [])
#             ing_counter = defaultdict(int)
#             for row in pattern:
#                 for c in row:
#                     if c != " " and c in key:
#                         if "item" in key[c]:
#                             ing = normalize(key[c]["item"])
#                         elif "tag" in key[c]:
#                             ing = normalize(tag_map[key[c]["tag"]][0])
#                         ing_counter[ing] += 1
#             for ing, qty in ing_counter.items():
#                 ing_obj = objects[ing]
#                 action.add_precondition(GE(count(ing_obj), qty))
#                 action.add_decrease_effect(count(ing_obj), qty)
#             action.add_increase_effect(count(result_obj), get_result_count(recipe))
#             if result != "minecraft:crafting_table":
#                 action.add_precondition(GE(count(objects["minecraft:crafting_table"]), 1))

#         actions.append((result, action))

#     return Item, count, actions, all_items, objects

# # === 动态推理原材料 ===
# def get_raw_materials_auto(recipes):
#     produced = set(normalize(get_result_item(r)) for r in recipes.values())
#     used = set()
#     for r in recipes.values():
#         if r["type"] == "minecraft:smelting":
#             used.add(normalize(r["ingredient"]["item"]))
#         elif r["type"] == "minecraft:crafting_shaped":
#             for v in r.get("key", {}).values():
#                 if "item" in v:
#                     used.add(normalize(v["item"]))
#                 elif "tag" in v:
#                     used.add(normalize(tag_map[v["tag"]][0]))
#     return used - produced

# # === 合成路径分析 ===
# def analyze_crafting_path(target):
#     required = defaultdict(int)
#     queue = deque()
#     queue.append((target, 1))
#     visited = set()
#     while queue:
#         item, qty = queue.popleft()
#         required[item] += qty
#         if (item, qty) in visited:
#             continue
#         visited.add((item, qty))
#         recipe = recipes.get(item)
#         if not recipe:
#             continue
#         if recipe["type"] == "minecraft:smelting":
#             ing = normalize(recipe["ingredient"]["item"])
#             queue.append((ing, qty))
#             if item != "minecraft:furnace":
#                 queue.append(("minecraft:furnace", 1))
#         elif recipe["type"] == "minecraft:crafting_shaped":
#             key = recipe["key"]
#             pattern = recipe["pattern"]
#             ing_counter = defaultdict(int)
#             for row in pattern:
#                 for c in row:
#                     if c != " " and c in key:
#                         if "item" in key[c]:
#                             ing = normalize(key[c]["item"])
#                         elif "tag" in key[c]:
#                             ing = normalize(tag_map[key[c]["tag"]][0])
#                         ing_counter[ing] += 1
#             for ing, count in ing_counter.items():
#                 queue.append((ing, qty * count))
#             if item != "minecraft:crafting_table":
#                 queue.append(("minecraft:crafting_table", 1))
#     return required

# # === 写入 domain.pddl ===
# def write_domain():
#     Item, count, actions, all_items, _ = extract_all_actions(recipes)
#     problem = Problem("minecraft-domain")
#     problem.add_fluent(count)
#     for item in all_items:
#         problem.add_object(Object(item.replace(":", "_"), Item))
#     for _, a in actions:
#         problem.add_action(a)
#     writer = PDDLWriter(problem)
#     writer.write_domain(os.path.join(PDDL_RESULT_PATH, "domain.pddl"))
#     print("domain.pddl Generated")

# # === 写入 problem_*.pddl ===
# def write_problem(target_item, raw_materials):
#     required = analyze_crafting_path(target_item)
#     Item = UserType("item")
#     count = Fluent("count", IntType(0, 9999), item=Item)
#     problem = Problem(f"make_{target_item.replace('minecraft:', '')}")
#     problem.add_fluent(count)
#     all_items = set(required.keys()) | raw_materials | {target_item}
#     objects = {item: Object(item.replace(":", "_"), Item) for item in all_items}
#     for obj in objects.values():
#         problem.add_object(obj)
#     for item in objects:
#         init_val = 999 if item in raw_materials else 0
#         problem.set_initial_value(count(objects[item]), init_val)
#     problem.add_goal(GE(count(objects[target_item]), 1))
#     writer = PDDLWriter(problem)
#     fname = f"problem_{target_item.replace('minecraft:', '')}.pddl"
#     writer.write_problem(os.path.join(PDDL_RESULT_PATH, fname))
#     print(f"{fname} Generated")

# # === 自动运行 ENHSP 并返回计划 ===
# def plan_for(target_item: str):
#     write_domain()
#     raw_materials = get_raw_materials_auto(recipes)
#     write_problem(target_item, raw_materials)
#     domain_path = os.path.join(PDDL_RESULT_PATH, "domain.pddl")
#     problem_path = os.path.join(PDDL_RESULT_PATH, f"problem_{target_item.replace('minecraft:', '')}.pddl")
#     try:
#         JAVA17 = "/usr/lib/jvm/java-1.17.0-openjdk-amd64/bin/java"
#         result = subprocess.run([
#             JAVA17, "-jar", os.path.join(PDDL_DATA_PATH, "enhsp.jar"), "-o", domain_path, "-f", problem_path
#         ], capture_output=True, text=True, timeout=30)
#         print("NHSP 原始输出:")
#         print(result.stdout)
#         output = result.stdout.splitlines()

#         plan_lines = [l.strip() for l in output if "(make__" in l and ")" in l]

#         print("Plan:")
#         for line in plan_lines:
#             print(line)
#         return plan_lines
    
        

#     except Exception as e:
#         print("Failed:", e)

# if __name__ == "__main__":
#     parser = argparse.ArgumentParser()
#     parser.add_argument("target", type=str, help="Target Item,format:minecraft:wooden_pickaxe")
#     args = parser.parse_args()
#     plan_for(args.target)

