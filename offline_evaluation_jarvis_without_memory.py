from jarvis.assembly.marks import MarkI
from jarvis.stark_tech.env_interface import MinecraftWrapper
from jarvis.assembly.env import RecordWrapper, RenderWrapper, build_env_yaml

from jarvis.assembly.evaluate import monitor_function
from jarvis.assembly.base import jarvis_tasks, get_task_config, memory
from jarvis.assembly.core import get_skill,get_plan

import random
import json
import os
import argparse

from datetime import datetime
from functools import partial

from rich import print as rprint


def execute(agent, goal):
    goal_type = goal["type"]
    assert goal_type in ["mine", "craft", "smelt"], f"subgoal type {goal_type} is not supported"

    goal_target = list(goal["goal"].keys())[0]
    goal_target_num = list(goal["goal"].values())[0]

    if goal_type == 'mine':
        skill = get_skill(goal_target, agent.record_infos[-1])
        if "timeout" in goal.keys():
            timeout = goal["timeout"]
        else:
            timeout = 600
        text_prompt = skill['text']
        rprint(f"[{datetime.now()}] Current skill prompt: {text_prompt}")
        agent.record_prompts[len(agent.record_infos)] = text_prompt
        if skill['type'] == 'mine':
            ret_flag, ret_info = agent.do(text_prompt, reward=float('inf'),
                                          monitor_fn=partial(monitor_function, goal["goal"]), timeout=timeout)
        else:
            ret_flag, ret_info = agent.do(skill['type'], target_item=skill['object_item'])
    elif goal_type == 'craft' or goal_type == 'smelt':
        agent.record_prompts[len(agent.record_infos)] = f"{goal_type} {goal_target}"
        ret_flag, ret_info = agent.do(goal_type, target=goal_target, target_num=goal_target_num)
    else:
        raise NotImplementedError
    return ret_flag, ret_info


def evaluate_task(env, mark, task_dict):
    env.reset()
    mark.reset()


    mark.record_goals = {}
    mark.record_prompts = {}
    mark.record_infos = mark.post_infos([env.step(env.noop_action())[-1]])
    print(mark.record_infos)

    json_path = "/home/liangjunyi/GitHub/JARVIS-1/jarvis/assets/cared_recipies.json"
    with open(json_path, "r") as f:
        recipes_data = json.load(f)

    rprint(f"[{datetime.now()}] Generating plan for task <{task_config_dict['task']}> via LLM!")

    plan = get_plan(task_config_dict['task_obj'], info=mark.record_infos[-1],recipes_data=recipes_data)

    task_config_dict['plan'] = plan
    mark.current_task = task_dict
    task_obj = task_dict['task_obj']
    plan = task_dict['plan']
    mark.current_plan = plan

    rprint(r"[bold blue][INFO]: Current task: [/bold blue]", task_dict['task'])

    task_done = False
    goal_seq = 0
    # for subgoal in plan:
    while not task_done:
        subgoal = plan[goal_seq]
        # print(f"current goal is {subgoal['goal']} from step {len(mark.record_infos)}!")
        print(f"Step: {len(mark.record_infos)}, Goal: {subgoal['goal']}!")

        mark.record_goals[len(mark.record_infos)] = subgoal

        goal_obj_ret, goal_obj_info = monitor_function(obj=subgoal['goal'], info=mark.record_infos[-1])
        while not goal_obj_ret:
            ret_flag, ret_info = execute(mark, subgoal)
            rprint(f"[{datetime.now()}] Executation Flag: {ret_flag} Information: {ret_info}")

            goal_obj_ret, goal_obj_info = monitor_function(obj=subgoal['goal'], info=mark.record_infos[-1])
            task_done, done_info = monitor_function(obj=task_obj, info=mark.record_infos[-1])
            if task_done or len(mark.record_infos) > env.maximum_step:
                break
        if goal_obj_ret:
            goal_seq += 1

        task_done, done_info = monitor_function(obj=task_obj, info=mark.record_infos[-1])
        if task_done:
            rprint(r"[bold green][INFO]: Finish the task[/bold green]", task_dict['task'])
            return True, "success"
        if len(mark.record_infos) > env.maximum_step:
            # print(f"reach maximum steps for task ")
            rprint("[bold red][INFO]: Reach maximum steps for task[/bold red]", task_dict['task'])
            return False, "timeout"

    return False, "plan_error"


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="Evaluate JARVIS-1 in offline mode.")
    parser.add_argument("-task", "--task_name", type=str, default="wooden_pickaxe", help="evaluation task name")
    parser.add_argument("-time", "--time", type=int, default=10, help="evaluation time(mins) for task")
    parser.add_argument("-dynamic", "--dynamic", type=bool, default=True, help="dynamic environment or not")
    parser.add_argument("-mode", "--evaluation_mode", type=str, default="offline",
                        help="online or offline evaluation mode")
    args = parser.parse_args()

    assert args.evaluation_mode == "offline", "Only support offline evaluation mode now!"

    task_name = args.task_name
    task_config_dict = get_task_config(task_name)

    task_env_setting = task_config_dict['env']
    task_env_yaml = build_env_yaml(task_env_setting)

    env = MinecraftWrapper("demo2")
    env = RenderWrapper(env)
    env.reset()
    env.maximum_step = 1200 * args.time - 1

    mark = MarkI(env=env)
    mark.reset()

    mark.env_yaml = task_env_yaml

    task_res, msg = evaluate_task(env, mark, task_config_dict)
