from jarvis.assembly.marks import MarkI
from jarvis.stark_tech.env_interface import MinecraftWrapper
from jarvis.assembly.env import RecordWrapper, RenderWrapper, build_env_yaml

from jarvis.assembly.evaluate import monitor_function
from jarvis.assembly.base import jarvis_tasks, get_task_config, memory
from jarvis.assembly.core import get_skill, get_skill_pddl, evaluate_plan

import random
import json
import os
import argparse

from datetime import datetime
from functools import partial

from rich import print as rprint
import yaml
from lby.pddl_gen import extract_primitive_steps, write_domain_and_problem
from collections import defaultdict

ENV_CONFIG_DIR = "/home/marmot/Boyang/JARVIS-1/lby/global_configs/envs"

def step_pddl_to_txt(pddl_txt):
    start = pddl_txt.index('(')
    end   = pddl_txt.index(')')
    return pddl_txt[start+1: end]

def get_pddl_plan(obj_name):
    plan = []
    pddl_task_name = f"minecraft:{obj_name}"

    pddl_sequences = write_domain_and_problem(pddl_task_name, extract_primitive_steps(pddl_task_name))
    plan = pddl_sequences.split('\n')
    plan = [step_pddl_to_txt(p) for p in plan]
    plan_dict= defaultdict(int)
    for x in plan:
        plan_dict[x] += 1
    plan.clear()
    for subgoal, num in plan_dict.items():
        action, item = subgoal.split("__")
        if action == "collect":
            action = 'mine'
        if action == 'make':
            action = 'craft'
        plan.append(
            {
            'goal': {item: num}, 
            'type': action, 
            'text': item}
        )
    return plan

def update_plan(plan_origin, plan_add):
    idx = 0
    while len(plan_add):
        new_p = plan_add.pop(0)
        if plan_origin[idx]['text'] == new_p['text']:
            if plan_origin[idx]['text'] not in ['crafting_table', 'furnace']:
                plan_origin[idx]['goal'][plan_origin[idx]['text']] += new_p['goal'][new_p['text']]
        else:
            plan_origin.insert(idx, new_p)  
        idx+=1
    return plan_origin

def execute(agent, goal, llm_model="gpt-3.5-turbo"):
    goal_type = goal["type"]
    assert goal_type in ["mine", "craft", "smelt"], f"subgoal type {goal_type} is not supported"

    goal_target = list(goal["goal"].keys())[0]
    goal_target_num = list(goal["goal"].values())[0]

    if goal_type == 'mine':
        skill = get_skill_pddl(goal_target, agent.record_infos[-1], llm_model)
        
        if "timeout" in goal.keys():
            timeout = goal["timeout"]
        else:
            timeout = 600
        text_prompt = skill['text']
        rprint(f"[{datetime.now()}] Current skill prompt: {text_prompt}")
        agent.record_prompts[len(agent.record_infos)] = text_prompt
        if skill['type'] == 'mine':
            ret_flag, ret_info = agent.do(text_prompt, reward = float('inf'), monitor_fn = partial(monitor_function, goal["goal"]), timeout=timeout)
        else:
            ret_flag, ret_info = agent.do(skill['type'], target_item=skill['object_item'])
    elif goal_type == 'craft' or goal_type == 'smelt':
        agent.record_prompts[len(agent.record_infos)] = f"{goal_type} {goal_target}"
        ret_flag, ret_info = agent.do(goal_type, target = goal_target, target_num = goal_target_num)
    else:
        raise NotImplementedError
    return ret_flag, ret_info


def evaluate_task(env, mark, task_dict, llm_model="gpt-3.5-turbo"):
    
    env.reset()
    mark.reset()

    mark.current_task = task_dict
    mark.record_goals = {}
    mark.record_prompts = {}
    mark.record_infos = mark.post_infos([env.step(env.noop_action())[-1]])
    print(mark.record_infos)

    task_obj = task_dict['task_obj']
    plan = getattr(task_dict, 'plan', None)
    
    if plan is None:
        print("No memory of current task, planning with pddl planner.")
        obj_name = list(task_obj.keys())[0]
        plan = get_pddl_plan(obj_name)
        
    insights, eval_type = evaluate_plan(plan, llm_model)
    if eval_type == "refine":
        # update_plan(get_pddl_plan("iron_pickaxe"), get_pddl_plan("wooden_pickaxe"))
        add_plan = get_pddl_plan(insights)
        plan = update_plan(plan, add_plan)

    mark.current_plan = plan

    rprint(r"[bold blue][INFO]: Current task: [/bold blue]", task_dict['task'])

    task_done = False
    # for subgoal in plan:
    while not task_done:
        subgoal = plan[0]  
        # print(f"current goal is {subgoal['goal']} from step {len(mark.record_infos)}!")
        print(f"Step: {len(mark.record_infos)}, Goal: {subgoal['goal']}!")
  
        mark.record_goals[len(mark.record_infos)] = subgoal

        goal_obj_ret, goal_obj_info = monitor_function(obj=subgoal['goal'], info = mark.record_infos[-1])
        while not goal_obj_ret:
            ret_flag, ret_info = execute(mark, subgoal, llm_model)
            rprint(f"[{datetime.now()}] Executation Flag: {ret_flag} Information: {ret_info}")

            goal_obj_ret, goal_obj_info = monitor_function(obj=subgoal['goal'], info = mark.record_infos[-1])
            task_done, done_info = monitor_function(obj=task_obj, info = mark.record_infos[-1])
            if task_done or len(mark.record_infos) >  env.maximum_step:
                break
        if goal_obj_ret:
            plan.pop(0)
        
        task_done, done_info = monitor_function(obj=task_obj, info = mark.record_infos[-1])
        if task_done:
            rprint(r"[bold green][INFO]: Finish the task[/bold green]", task_dict['task'])
            return True, "success"
        if len(mark.record_infos) >  env.maximum_step:
            # print(f"reach maximum steps for task ")
            rprint("[bold red][INFO]: Reach maximum steps for task[/bold red]", task_dict['task'])
            return False, "timeout"
    
    return False, "plan_error"

# for single task evaluate
def evaluate_single_task(args, task_name, yaml_file):
    task_config_dict = get_task_config(task_name)
    
    ### modify original config to fit paper setting ###
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
    
    with open(os.path.join(ENV_CONFIG_DIR, yaml_file), 'r') as f:
        task_env_yaml  = yaml.load(f, Loader=yaml.FullLoader)
    
    task_config_dict['env']['biome'] = task_env_yaml["candidate_preferred_spawn_biome"][0]

    # NO MEMORY USED
    # if task_config_dict['task'] in memory.keys():
    #     rprint(f"\n[{datetime.now()}] Getting plan from memory for task {task_config_dict['task']}!")
    #     task_config_dict['plan'] = memory[task_config_dict['task']]['plan']
    # else:
    #     rprint(f"[{datetime.now()}] Found no plans in memory for task <{task_config_dict['task']}>!")
    #     rprint(f"[{datetime.now()}] Generating plan for task <{task_config_dict['task']}>!")
    #     # FIXME: generate plan for task 
    #     raise NotImplementedError("Online generating plan for task is not merged yet! Waiting for the next version.")

    env = MinecraftWrapper(yaml_file)
    if args.use_gui:
        env = RenderWrapper(env)
    env.reset()
    env.maximum_step = 1200*args.time - 1
    
    mark = MarkI(env=env)
    mark.reset()

    mark.env_yaml = task_env_yaml
    task_res, msg = evaluate_task(env, mark, task_config_dict, args.llm_type)
    return task_res, msg, task_config_dict['env']['biome'], task_env_yaml['seed']

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="Evaluate JARVIS-1 in offline mode.")
    parser.add_argument("-task", "--task_name", type=tuple, default="iron_pickaxe", help="evaluation task name, times")
    parser.add_argument("-time", "--time", type=int, default=10, help="evaluation time(mins) for task")
    parser.add_argument("-dynamic", "--dynamic", type=bool, default=True, help="dynamic environment or not")
    parser.add_argument("-mode", "--evaluation_mode", type=str, default="offline", help="online or offline evaluation mode")
    
    ############# Newly add args #################
    parser.add_argument(
        "--tasks_list", type=list, 
        default=["crafting_table", "wooden_pickaxe","stone_pickaxe", "iron_pickaxe"],
        help="evaluation tasks_name list"
    )
    parser.add_argument(
        "--llm_type", type=str, 
        default="qwen-turbo", 
        choices=["qwen-turbo", "qwen-plus", "qwen-max", "qwen-omni-turbo", "qwen2.5-14b-instruct-1m"],
        help="LLM used for evaluation"
    )
    parser.add_argument("--use_gui", type=int, default=0, help="Disable GUI evaluation")

    parser.add_argument("--if_debug", type=int, default=0)
    ################################

    args = parser.parse_args()

    assert args.evaluation_mode == "offline", "Only support offline evaluation mode now!"
    
    print(f"Using LLM: {args.llm_type}")

    if not args.if_debug:
        task_yamls = os.listdir(ENV_CONFIG_DIR)
        # eval for list of task
        output_file = f"/home/marmot/Boyang/JARVIS-1/lby/eval_{args.llm_type}_pddl.txt"
        file_exists = os.path.exists(output_file) and os.path.getsize(output_file) > 0
        with open(output_file,'a') as f_out:
            if not file_exists:
                f_out.write(f"task name\tbiome\tseed\tresult\tresult_msg\n")

            for task_name in args.tasks_list:
                eval_yamls = [x for x in task_yamls if task_name in x]
                for task_yaml_file in eval_yamls:
                    task_res, msg, biome, seed = evaluate_single_task(args, task_name, task_yaml_file)
                    f_out.write(f"{task_name}\t{biome}\t{seed}\t{task_res}\t{msg}\n")
                    f_out.flush()  # Ensure data is written to file immediately   
                    os.remove(os.path.join(ENV_CONFIG_DIR, task_yaml_file)) 
    else:
        task_name = "iron_pickaxe"
        task_yaml_file = "tmp.yaml"
        task_res, msg, biome, seed = evaluate_single_task(args, task_name, task_yaml_file)
