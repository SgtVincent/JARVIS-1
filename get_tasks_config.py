from jarvis.assembly.base import get_task_config

import random
import json
import os
from collections import defaultdict
import yaml
# Ensure reproducibility
random.seed(42)

ENV_CONFIG_DIR = "/home/marmot/Boyang/JARVIS-1/lby/global_configs/envs"

def build_env_yaml(env_config, biome_seed,save_config_name="tmp"):
    with open(os.path.join(ENV_CONFIG_DIR, "jarvis.yaml"), 'r') as f:
        env_yaml = yaml.load(f, Loader=yaml.FullLoader)
    # biome -> seed: 12345, close_ended: True
    if env_config["biome"]:
        env_yaml['candidate_preferred_spawn_biome'] = [env_config["biome"]]
        env_yaml['close_ended'] = True
        env_yaml['seed'] = biome_seed

    # mobs -> summon_mobs
    if env_config["mobs"]:
        env_yaml['summon_mobs'] = env_config["mobs"]

    # init_inventory -> init_inventory
    env_yaml['init_inventory'] = {}
    if env_config["init_inventory"]:
        for k,v in env_config["init_inventory"].items():
            env_yaml['init_inventory'][k] = v

    with open(os.path.join(ENV_CONFIG_DIR, f"{save_config_name}.yaml"), 'w') as f:
        yaml.dump(env_yaml, f, sort_keys=False)
    
    return env_yaml

if __name__ == "__main__":
    biome_json ="/home/marmot/Boyang/JARVIS-1/jarvis/assets/spawn.json"
    with open(biome_json, 'r') as f:
        biome_configs = json.load(f)

    biome_configs_dict = defaultdict(list)
    for config_item in biome_configs:
        biome_configs_dict[config_item["biome"]].append(config_item)

    appointed_biome = ["plains", "forest"]
    biome_candidates = []
    for biome in appointed_biome:
        biome_candidates.extend(biome_configs_dict[biome])
    random.shuffle(biome_candidates)


    tasks_list = [
        ("crafting_table", 68), 
        ("wooden_pickaxe", 62),
        ("stone_pickaxe", 68),
        ("iron_pickaxe", 68)
    ]
    
    t = 0
    n_biome = len(biome_candidates)

    for task_name, eval_times in tasks_list:
        
        for i in range(eval_times):
            task_config_dict = get_task_config(task_name)
            
            t %= n_biome
            task_config_dict['env']['biome'] = biome_candidates[t]['biome']

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
            task_env_yaml = build_env_yaml(task_env_setting,biome_candidates[t]['seed'], config_yaml_name)
            t += 1