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

# === 提取所有相关 item ===
def extract_primitive_steps(target, recipes=USED_RECIPE):
    visited = set()
    queue = deque()
    queue.append(normalize(target))

    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)

        recipe = recipes.get(current)
        if not recipe:
            continue

        if recipe["type"] == "minecraft:smelting":
            ing = recipe["ingredient"]
            item = normalize(ing.get("item") or tag_map.get(ing.get("tag"), ["minecraft:dirt"])[0])
            queue.append(item)
            if current != "minecraft:furnace":
                queue.append("minecraft:furnace")

        elif recipe["type"] in ["minecraft:crafting_shaped", "minecraft:crafting_shapeless"]:
            if recipe["type"] == "minecraft:crafting_shaped":
                key = recipe.get("key", {})
                for row in recipe.get("pattern", []):
                    for c in row:
                        if c != " " and c in key:
                            v = key[c]
                            item = normalize(v.get("item") or tag_map.get(v.get("tag"), ["minecraft:dirt"])[0])
                            queue.append(item)
            else:
                for ing in recipe.get("ingredients", []):
                    item = normalize(ing.get("item") or tag_map.get(ing.get("tag"), ["minecraft:dirt"])[0])
                    queue.append(item)

            if current != "minecraft:crafting_table" and current != "minecraft:planks":
                queue.append("minecraft:crafting_table")

    return visited

# === domain.pddl 和 problem.pddl 生成 ===
def write_domain_and_problem(target, steps=0):
    Item = UserType("item")
    count = Fluent("count", IntType(0, 9999), item=Item)
    problem = Problem("minecraft-domain")
    problem.add_fluent(count)

    related_items = extract_primitive_steps(target, USED_RECIPE)
    related_items.add(normalize(target))

    obj_map = {i: Object(i.replace(":", "_"), Item) for i in related_items}
    for o in obj_map.values():
        problem.add_object(o)

    for i in related_items:
        if i not in USED_RECIPE:
            action = InstantaneousAction(f"collect__{i.replace('minecraft:', '')}")
            itm = obj_map[i]
            action.add_increase_effect(count(itm), 1)
            problem.add_action(action)

    for name, recipe in USED_RECIPE.items():
        if name not in related_items:
            continue
        result = obj_map[name]
        label = "smelt" if recipe["type"] == "minecraft:smelting" else "make"
        action = InstantaneousAction(f"{label}__{name.replace('minecraft:', '')}")

        try:
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
        except KeyError as e:
            print(f"WARNING: Missing ingredient object for {e} in recipe {name}, skipping action.")
            continue

        problem.add_action(action)

    for item in obj_map:
        problem.set_initial_value(count(obj_map[item]), 0)
    goal = obj_map[normalize(target)]
    problem.add_goal(GE(count(goal), 1))

    writer = PDDLWriter(problem)
    domain_file = os.path.join(PDDL_RESULT_PATH, "domain.pddl")
    problem_file = os.path.join(PDDL_RESULT_PATH,f"problem_{target.replace('minecraft:', '')}.pddl")
    writer.write_domain(domain_file)
    writer.write_problem(problem_file)
    print("domain.pddl, problem generated")

    try:
        JAVA17 = "/usr/lib/jvm/java-1.17.0-openjdk-amd64/bin/java"
        result = subprocess.run([
            JAVA17, "-jar", os.path.join(PDDL_DATA_PATH, "enhsp.jar"), "-o", domain_file, "-f", problem_file
        ], capture_output=True, text=True, timeout=30)

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
    except Exception as e:
        print(" ENHSP failed:", e)

# === CLI 入口 ===
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("target", type=str)
    args = parser.parse_args()
    write_domain_and_problem(args.target)
