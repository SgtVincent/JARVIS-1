from lby.pddl_gen import extract_primitive_steps, write_domain_and_problem, USED_RECIPE
from collections import defaultdict
from copy import deepcopy
from jarvis.assembly.core import evaluate_plan
import random
def step_pddl_to_txt(pddl_txt):
    start = pddl_txt.index('(')
    end   = pddl_txt.index(')')
    return pddl_txt[start+1: end]


def get_pddl_plan(obj_name):
    plan = []
    pddl_task_name = f"minecraft:{obj_name}"

    pddl_sequences = write_domain_and_problem(pddl_task_name, extract_primitive_steps(pddl_task_name))
    plan = [step_pddl_to_txt(p) for p in pddl_sequences]
    count_dict= defaultdict(int)
    for x in plan:
        count_dict[x] += 1
    plan.clear()
    for subgoal, num in count_dict.items():
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
    while len(plan_add):
        new_p = plan_add.pop(0)

        for p in plan_origin:
            if p['text'] == new_p['text']:
                if p['text'] not in ['crafting_table', 'furnace']:
                    p['goal'][p['text']] += new_p['goal'][new_p['text']]
                break
        
        if p == plan_origin[-1] and p['text'] != new_p['text']:
            plan_origin.append(new_p)
    
    return plan_origin

def keep_new_plan(new_plan, plan_buff):
    new_task = new_plan[-1]['text']
    for plan in plan_buff:
        for item in plan:
            if item['text'] == new_task:
                return False
    
    return True

def merge_all_plan(plan_buff):
    if len(plan_buff) == 1:
        return plan_buff[0]
    while len(plan_buff) > 1:
        plan_buff = sorted(plan_buff, key=len)
        plan_short = plan_buff.pop(0)
        plan_long = plan_buff.pop(0)
        t_merge = update_plan(plan_short, plan_long)
        plan_buff.append(t_merge)
    
    return plan_buff[0]

def refine_plan_llm(plan, llm_type="qwen-turbo", max_eval=5):
    addition_info = ""
    plan_buff = [plan]
    TOKEN_USE = []
    for _ in range(max_eval):
        insights, eval_type, token_usage = evaluate_plan(merge_all_plan(deepcopy(plan_buff)), addition_info, llm_type)
        TOKEN_USE.append(("plan", token_usage))
        addition_info = ""
        if eval_type == "proceed":
            break
        elif eval_type in ["refine", "craft"]:
            insights = insights.lower()
            insights = insights.split(" ")[-1]
            try:
                if f"minecraft:{insights}" not in USED_RECIPE.keys():
                    addition_info = f"\nYour former propose: '{insights}, {eval_type}' there is not a item can or need to be crafted."
                    continue

                add_plan = get_pddl_plan(insights)
                if len(add_plan) > len(plan):
                    addition_info = f"\nYour refine propose: '{insights}, {eval_type}' is not realistic, you are making task harder."
                else:
                    if keep_new_plan(add_plan, plan_buff):
                        plan_buff.append(add_plan)
                    else:
                        addition_info = f"\nYour refine propose: '{insights}, {eval_type}' is redundant, original plan has already covered it."

            except Exception:
                addition_info = f"\nYour former propose: '{insights}, {eval_type}' is not valid."

    plan = merge_all_plan(plan_buff)
    return plan, TOKEN_USE

def get_plan_pddl_quantity(obj_name, llm_type, max_eval, if_rule_based=False):
    plan = get_pddl_plan(obj_name)

    if if_rule_based:
        if obj_name == "stone_pickaxe":
            plan_buff = [plan]
            plan_buff.append(get_pddl_plan("wooden_pickaxe"))
        elif obj_name == "iron_pickaxe":
            plan_buff = [plan]
            plan_buff.append(get_pddl_plan("wooden_pickaxe"))
            if random.random() < 0.7:
                plan_buff.append(get_pddl_plan("stone_pickaxe"))
        plan = merge_all_plan(plan_buff)
        token_usage = []
    else:
        plan, token_usage = refine_plan_llm(plan, llm_type, max_eval)
    
    return plan, token_usage

if __name__ == "__main__":
    print("LLM refine")
    plan, token_usage = get_plan_pddl_quantity("stone_pickaxe", llm_type="qwen-turbo", max_eval=3)

    print("rule based refine")
    plan, token_usage = get_plan_pddl_quantity("stone_pickaxe", llm_type="qwen-turbo", max_eval=3, if_rule_based=True)

    print("Tested")

    