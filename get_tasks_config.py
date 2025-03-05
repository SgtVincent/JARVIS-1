from jarvis.assembly.env import build_env_yaml
from jarvis.assembly.base import get_task_config

import random
import json
import os

# Ensure reproducibility
random.seed(42)


if __name__ == "__main__":
    tasks_list = [
        ("crafting_table", 68), 
        ("wooden_pickaxe", 62),
        ("stone_pickaxe", 68),
        ("iron_pickaxe", 68)
    ]
    appointed_biome = ["plains", "forest"]
    
    for task_name, eval_times in tasks_list:
        
        for i in range(eval_times):
            task_config_dict = get_task_config(task_name)
            
            ### modify original config to fit paper setting ###
            task_config_dict['env']['biome'] = random.choice(appointed_biome)

            if task_name in ["stone_pickaxe", "iron_pickaxe", "diamond"]:
                task_config_dict['env']['init_inventory']={
                    0: {
                        "type": "iron_axe",
                        "quantity": 1
                    }
                }
            else:
                task_config_dict['env']['init_inventory']= {}
            ###################################################
            config_yaml_name = f"{task_name}_{i}"
            task_env_setting = task_config_dict['env']
            task_env_yaml = build_env_yaml(task_env_setting, config_yaml_name)