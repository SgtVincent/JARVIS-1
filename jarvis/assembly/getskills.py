#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from jarvis.assembly.base import skills

def get_tasks_data(task_list):
    l = []
    results = []
    for task in task_list:
        if task not in skills:
            results.append({
                "task": task,
                "skill_content": [f"get {task}"]
            })
            l.append(f"get {task}")
            continue

        skill_group = skills[task]
        if len(skill_group) == 1:
            single_skill = skill_group[0]
            results.append({
                "task": task,
                "skill_content": [single_skill["text"]]
            })
            l.append(single_skill["text"])
        else:
            skill_content = [skill_item["text"] for skill_item in skill_group]
            results.append({
                "task": task,
                "skill_content": skill_content
            })
            l+=skill_content
    return results,l

def remove_duplicates(lst):
    unique_items = []
    for item in lst:
        if item not in unique_items:
            unique_items.append(item)
    return unique_items

if __name__ == "__main__":
    my_tasks = [
        "logs",
        "planks",
        "crafting_table",
        "stick",
        "wooden_pickaxe",
        "cobblestone",
        "stone_pickaxe",
        "furnace",
        "iron_ore",
        "iron_ingot",
        "iron_pickaxe"
    ]
    data,l = get_tasks_data(my_tasks)
    l = remove_duplicates(l)
    print(json.dumps(data, indent=4, ensure_ascii=False))
    print(l)
