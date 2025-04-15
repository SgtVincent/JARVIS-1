import os
from typing import Dict, List

# Import your environment's client (Jarvis/OpenAI/qwen, etc.)
from jarvis.assembly.base import client

TASK_SKILLS_MAP = {
    "logs": [
        "chop down the tree",
        "equip iron axe to chop down the tree"
    ],
    "cobblestone": [
        "equip wooden_pickaxe",
        "dig down"
    ],
    "iron_ore": [
        "dig down",
        "equip stone pickaxe",
        "break iron_ore blocks",
        "break iron blocks",
        "break the stone blocks and mine iron ore"
    ]
}

class RealLLMClient:
    """
    Example class that uses jarvis.assembly.base.client.chat.completions.create
    to call an LLM. Replace the details as needed.
    """
    def ask(self, prompt_text: str) -> str:
        # Using 'qwen-max' as an example model. Replace with your model name if needed.
        response = client.chat.completions.create(
            model="qwen-max",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt_text}
            ],
            temperature=0.7,
            max_tokens=1024
        )
        return response.choices[0].message.content


import json


def get_domain_from_llm(folder: str, model_client, max_retries: int = 3) -> str:
    os.makedirs(folder, exist_ok=True)
    domain_file_path = os.path.join(folder, "domain.pddl")

    # Short example snippet (avoid providing the entire domain to prevent verbatim copying)
    example_snippet = """(:action chop_down_the_tree
  :parameters ()
  :precondition (and)
  :effect (and (increase (count minecraft_logs) 1))
)"""

    partial_domain_example = f"""
(define (domain minecraft-domain)
 (:requirements :strips :typing :numeric-fluents)
 (:types item)
 (:predicates (equipped ?tool - item))
 (:functions (count ?item - item) (agent_height))

 ;; Example snippet (not the full domain):
 {example_snippet}
 ...
)""".strip()

    # Skill mapping as JSON (for reference)
    skill_list_json = json.dumps(TASK_SKILLS_MAP, indent=2)

    # --- Updated prompt in English ---
    prompt = f"""
Your task is to produce a complete and valid PDDL domain for Minecraft-like actions. 
Follow these strict rules:

1. **File structure**: It must start with 
   (define (domain minecraft-domain)
   and contain:
   - (:requirements :strips :typing :numeric-fluents)
   - (:types item)
   - (:predicates (equipped ?tool - item))
   - (:functions (count ?item - item) (agent_height))

2. **Action definitions**: 
   You must define 8 actions, logically matching these skill names:
      - break iron blocks
      - break iron_ore blocks
      - break the stone blocks and mine iron ore
      - chop down the tree
      - dig down
      - equip iron axe to chop down the tree
      - equip stone pickaxe
      - equip wooden_pickaxe

   The action names can differ slightly (e.g. break_iron_blocks vs. break-iron-blocks), 
   but they must clearly correspond to the above skills in logic.

3. **Preconditions and effects**:
   - *break iron blocks* and *break iron_ore blocks*: Must require having a stone pickaxe, 
     must also require agent_height <= 15, and must produce minecraft_iron_ore.
   - *break the stone blocks and mine iron ore*: Similar to breaking iron ore, 
     requires a stone pickaxe, agent_height <= 15, and produces minecraft_iron_ore.
   - *chop down the tree*: Has no special precondition (just (and)) or optionally 
     any axe, and produces minecraft_logs.
   - *dig down*: Must have either a wooden or stone pickaxe, must have agent_height > 15, 
     and effects should include producing minecraft_cobblestone, producing minecraft_iron_ore, 
     and reducing agent_height by some numeric (e.g. (decrease (agent_height) 5)).
   - *equip iron axe to chop down the tree*: Must have a precondition indicating 
     you have at least one iron axe in your count, e.g. (<= 1 (count minecraft_iron_axe)), 
     and effect should equip minecraft_iron_axe.
   - *equip stone pickaxe* and *equip wooden_pickaxe*: Similar logic; 
     if you want to equip stone pickaxe, you must have (<= 1 (count minecraft_stone_pickaxe)) 
     in precondition, and effect is (equipped minecraft_stone_pickaxe), etc.

4. **Naming**:
   - Every item in preconditions or effects should begin with 'minecraft_', e.g. 
     (equipped minecraft_stone_pickaxe).
   - The final domain must be syntactically valid. 
   - Avoid extra commentary, code fences, or any format other than the PDDL text.

For reference, here is a small partial example (NOT the full domain):
{partial_domain_example}

Skill mapping information:
{skill_list_json}

Now, please return **only** the complete domain.pddl text (no code blocks, no explanations). 
Make sure it meets the numeric preconditions (<= or > for agent_height), 
produces the right items (minecraft_logs, minecraft_iron_ore, minecraft_cobblestone), 
and uses the correct structure for equipping items.

If you cannot satisfy the above requirements on the first try, try to correct your domain 
until it meets all points. Remember: do not copy verbatim from the example; 
the domain must be original but logically equivalent.
"""

    domain_text = ""
    error_reason = None

    for attempt in range(max_retries):
        if error_reason:
            full_prompt = (
                    prompt
                    + f"\n[Error in attempt {attempt}: {error_reason}]\nPlease fix any issues and try again."
            )
        else:
            full_prompt = prompt

        raw_output = model_client.ask(full_prompt).strip()

        # Quick checks: must start with (define (domain...) and contain "(:action"
        if not raw_output.startswith("(define (domain"):
            error_reason = "Domain must start with (define (domain..."
            continue
        if "(:action " not in raw_output:
            error_reason = "No (:action) definitions found"
            continue

        # Passed checks
        domain_text = raw_output
        break

    # If no valid domain after retries, write an empty template.
    if not domain_text:
        domain_text = """(define (domain minecraft-domain)
 (:requirements :strips :typing :numeric-fluents)
 (:types item)
 (:predicates (equipped ?tool - item))
 (:functions (count ?item - item) (agent_height))
)
"""

    with open(domain_file_path, "w", encoding="utf-8") as f:
        f.write(domain_text)

    return domain_file_path


if __name__ == "__main__":
    # Use RealLLMClient for an actual model call
    model_client = RealLLMClient()
    folder_name = "action_plan_2"
    domain_path = get_domain_from_llm(folder_name, model_client)
    print("Domain PDDL saved to:", domain_path)
