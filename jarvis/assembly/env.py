import cv2
import gymnasium as gym

class RenderWrapper(gym.Wrapper):
    
    def __init__(self, env, window_name="minecraft"):
        super().__init__(env)
        self.window_name = window_name
    
    def step(self, action):
        obs, reward, terminated, truncated, info = self.env.step(action)
        bgr_pov = cv2.cvtColor(info['pov'], cv2.COLOR_RGB2BGR)
        cv2.imshow(self.window_name, bgr_pov)
        cv2.waitKey(1)
        return obs, reward, terminated, truncated, info

    def reset(self):
        obs, info = self.env.reset()
        bgr_pov = cv2.cvtColor(info['pov'], cv2.COLOR_RGB2BGR)
        cv2.imshow(self.window_name, bgr_pov)
        cv2.waitKey(1)
        return obs, info
    
class RecordWrapper(gym.Wrapper):
    def __init__(self, env):
        super().__init__(env)
        self.frames = []
    
    def step(self, action):
        obs, reward, terminated, truncated, info = self.env.step(action)
        self.frames.append(info['pov'])
        return obs, reward, terminated, truncated, info

    def reset(self):
        obs, info = self.env.reset()
        self.frames.append(info['pov'])
        return obs, info
    
import yaml
import random 
from pathlib import Path
import json

from jarvis.assets import SPAWN_FILE
with open(SPAWN_FILE, 'r') as f:
    spawn = json.load(f)

# # Ensure reproducibility
# random.seed(42)

seeds = {}
for s in spawn:
    if s['biome'] not in seeds.keys():
        seeds[s['biome']] = []
    seeds[s['biome']].append(s['seed'])

ENV_CONFIG_DIR = Path(__file__).parent.parent.parent / "lby" / "global_configs" / "envs"

def build_env_yaml(env_config, save_config_name="tmp"):
    with open(ENV_CONFIG_DIR / "jarvis.yaml", 'r') as f:
        env_yaml = yaml.load(f, Loader=yaml.FullLoader)
    # biome -> seed: 12345, close_ended: True
    if env_config["biome"]:
        env_yaml['candidate_preferred_spawn_biome'] = [env_config["biome"]]
        if env_config["biome"] in seeds.keys():
            env_yaml['close_ended'] = True
            env_yaml['seed'] = random.choice(seeds[env_config["biome"]])

    # mobs -> summon_mobs
    if env_config["mobs"]:
        env_yaml['summon_mobs'] = env_config["mobs"]

    # init_inventory -> init_inventory
    env_yaml['init_inventory'] = {}
    if env_config["init_inventory"]:
        for k,v in env_config["init_inventory"].items():
            env_yaml['init_inventory'][k] = v

    with open(ENV_CONFIG_DIR / f"{save_config_name}.yaml", 'w') as f:
        yaml.dump(env_yaml, f, sort_keys=False)
    
    return env_yaml

