from jarvis.assembly.marks import MarkI
from jarvis.stark_tech.env_interface import MinecraftWrapper
from jarvis.assembly.env import RecordWrapper, RenderWrapper, build_env_yaml
from jarvis.assembly.base import skills
from jarvis.assembly.evaluate import monitor_function
from jarvis.assembly.base import jarvis_tasks, get_task_config, memory
from jarvis.assembly.core import get_skill, get_plan, detect_item_dependencies, check_items,generate_domain_pddl_all_skills,gen_problem_pddl,parse_plan_actions,solve_pddl,get_skill_definitions,RealLLMClient,TASK_SKILLS_MAP,solve_plan_with_fallback,map_action_name


import random
import json
import os
import argparse

from datetime import datetime
from functools import partial

from rich import print as rprint
import yaml

from collections import defaultdict

def summarize_token_usage_detailed(token_records):
    usage_summary = defaultdict(lambda: {"prompt": 0, "completion": 0, "total": 0})
    for call_type, usage in token_records:
        usage_summary[call_type]["prompt"] += usage.prompt_tokens
        usage_summary[call_type]["completion"] += usage.completion_tokens
        usage_summary[call_type]["total"] += usage.total_tokens
    return usage_summary

ENV_CONFIG_DIR = "lby/global_configs/envs"


def execute(agent, goal, llm_model="gpt-3.5-turbo"):
    goal_type = goal["type"]
    assert goal_type in ["mine", "craft", "smelt"], f"subgoal type {goal_type} is not supported"

    goal_target = list(goal["goal"].keys())[0]
    goal_target_num = list(goal["goal"].values())[0]
    TOKEN_RECORD = []

    if goal_type == 'mine':
        print("--------------------Before Get skill--------------------")
        print(goal_target)
        print(agent.record_infos[-1])
        print("--------------------Just before Get skill--------------------")
        if goal_target not in skills.keys():
            skill = {
                "text": f"get {goal_target}",
                "type": "mine",
                "object_item": None
            }
        else:
            gen_problem_pddl(goal_target,agent.record_infos[-1])
            # actioon_plan =  solve_pddl('action pddl/domain.pddl','action pddl/problem.pddl')
            # skill = parse_plan_actions(actioon_plan,goal_target)
            skill = solve_plan_with_fallback(goal_target)
            skill["text"] = map_action_name(skill["text"])
            # skill = get_skill(goal_target, agent.record_infos[-1], llm_model)
        print("skill",skill)
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
    return ret_flag, ret_info, TOKEN_RECORD


def evaluate_task(env, mark, task_dict, llm_model="gpt-3.5-turbo"):
    env.reset()
    mark.reset()

    mark.record_goals = {}
    mark.record_prompts = {}
    mark.record_infos = mark.post_infos([env.step(env.noop_action())[-1]])
    print('mark.record_infos', mark.record_infos)

    json_path = "jarvis/assets/cared_recipies.json"
    with open(json_path, "r") as f:
        recipes_data = json.load(f)

    rprint(f"[{datetime.now()}] Generating plan for task <{task_dict['task']}> via LLM!")

    TOKEN_RECORD =[]

    seq_task = detect_item_dependencies(task_dict['task_obj'])
    if not check_items(seq_task):
        return False, "invalid item generated"
    plan, token_usage = get_plan(seq_task, info=mark.record_infos[-1], recipes_data=recipes_data)
    TOKEN_RECORD.append(("plan", token_usage))

    task_dict['plan'] = plan
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
        max_subgoal_attempts = 20
        attempt_count = 0

        while not goal_obj_ret and attempt_count < max_subgoal_attempts:
            ret_flag, ret_info, token_info = execute(mark, subgoal, llm_model)
            rprint(f"[{datetime.now()}] Executation Flag: {ret_flag} Information: {ret_info}")
            TOKEN_RECORD.extend(token_info)

            attempt_count += 1
            goal_obj_ret, goal_obj_info = monitor_function(obj=subgoal['goal'], info=mark.record_infos[-1])
            task_done, done_info = monitor_function(obj=task_obj, info=mark.record_infos[-1])
            if task_done or len(mark.record_infos) > env.maximum_step:
                break

            if ret_flag is False:
                if ret_info.get("terminated"):
                    rprint("[ERROR] Environment reset. Abort subgoal immediately.")
                    break
                else:
                    rprint(f"[WARNING] Attempt {attempt_count} for subgoal failed. Retrying...")
                    continue

        if goal_obj_ret:
            goal_seq += 1
        else:
            return False, "subgoal_failed", TOKEN_RECORD

        task_done, done_info = monitor_function(obj=task_obj, info=mark.record_infos[-1])
        if task_done:
            rprint(r"[bold green][INFO]: Finish the task[/bold green]", task_dict['task'])
            return True, "success", TOKEN_RECORD
        if len(mark.record_infos) > env.maximum_step:
            # print(f"reach maximum steps for task ")
            rprint("[bold red][INFO]: Reach maximum steps for task[/bold red]", task_dict['task'])
            return False, "timeout", TOKEN_RECORD

    return False, "plan_error", TOKEN_RECORD


# for single task evaluate
def evaluate_single_task(args, task_name, yaml_file):
    task_config_dict = get_task_config(task_name)

    ### modify original config to fit paper setting ###
    if task_name in ["stone_pickaxe", "iron_pickaxe", "diamond"]:
        task_config_dict['env']['init_inventory'] = {
            0: {
                "type": "iron_axe",
                "quantity": 1
            }
        }
    else:
        task_config_dict['env']['init_inventory'] = {}
    ###################################################

    with open(os.path.join(ENV_CONFIG_DIR, yaml_file), 'r') as f:
        task_env_yaml = yaml.load(f, Loader=yaml.FullLoader)

    task_config_dict['env']['biome'] = task_env_yaml["candidate_preferred_spawn_biome"][0]

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
    env.maximum_step = 1200 * args.time - 1

    mark = MarkI(env=env)
    mark.reset()

    mark.env_yaml = task_env_yaml
    task_res, msg, token_records = evaluate_task(env, mark, task_config_dict, args.llm_type)
    return task_res, msg, task_config_dict['env']['biome'], task_env_yaml['seed'], token_records 


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="Evaluate JARVIS-1 in offline mode.")
    parser.add_argument("-task", "--task_name", type=tuple, default="iron_pickaxe", help="evaluation task name, times")
    parser.add_argument("-time", "--time", type=int, default=10, help="evaluation time(mins) for task")
    parser.add_argument("-dynamic", "--dynamic", type=bool, default=True, help="dynamic environment or not")
    parser.add_argument("-mode", "--evaluation_mode", type=str, default="offline",
                        help="online or offline evaluation mode")

    ############# Newly add args #################
    parser.add_argument(
        "--tasks_list", type=list,
        default=["crafting_table", "wooden_pickaxe", "stone_pickaxe", "iron_pickaxe"],
        help="evaluation tasks_name list"
    )
    parser.add_argument(
        "--llm_type", type=str,
        default="qwen-max",
        choices=["qwen-turbo", "qwen-plus", "qwen-max", "qwen-omni-turbo", "qwen2.5-14b-instruct-1m"],
        help="LLM used for evaluation"
    )
    parser.add_argument("--use_gui", type=int, default=1, help="Disable GUI evaluation")
    ################################

    args = parser.parse_args()

    assert args.evaluation_mode == "offline", "Only support offline evaluation mode now!"

    print(f"Using LLM: {args.llm_type}")

    task_yamls = os.listdir(ENV_CONFIG_DIR)

    # eval for list of task
    output_file = f"lby/eval_{args.llm_type}_pddlact.txt"
    file_exists = os.path.exists(output_file) and os.path.getsize(output_file) > 0
    model_client = RealLLMClient(args.llm_type)

    with open(output_file, 'a') as f_out:
        if not file_exists:
            f_out.write(
                "task name\tenv_index\tbiome\tseed\tresult\tresult_msg\t"
                "plan_prompt\tplan_completion\tplan_total\t"
                "skill_prompt\tskill_completion\tskill_total\n"
            )

        for task_name in args.tasks_list:
            eval_yamls = [x for x in task_yamls if task_name in x]
            for task_yaml_file in eval_yamls:
                skill_preconds, skill_custom_rules, skill_effect_items, token_usage = get_skill_definitions(
                    TASK_SKILLS_MAP, model_client
                )
                folder_name = "action pddl"
                domain_file = generate_domain_pddl_all_skills(
                    folder_name,
                    skill_preconds,
                    skill_custom_rules,
                    skill_effect_items
                )

                task_index = os.path.splitext(task_yaml_file)[0].split("_")[-1]
                task_res, msg, biome, seed, token_records = evaluate_single_task(args, task_name, task_yaml_file)
                token_records.append(("skill", token_usage))
                usage_summary = summarize_token_usage_detailed(token_records)
                plan = usage_summary.get("plan", {"prompt": 0, "completion": 0, "total": 0})
                skill = usage_summary.get("skill", {"prompt": 0, "completion": 0, "total": 0})
                f_out.write(
                    f"{task_name}\t{task_index}\t{biome}\t{seed}\t{task_res}\t{msg}\t"
                    f"{plan['prompt']}\t{plan['completion']}\t{plan['total']}\t"
                    f"{skill['prompt']}\t{skill['completion']}\t{skill['total']}\n"
                )
                f_out.flush()  # Ensure data is written to file immediately
                os.remove(os.path.join(ENV_CONFIG_DIR, task_yaml_file))
