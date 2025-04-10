import re

def modify_summary(text: str) -> str:
    lines = text.strip().split('\n')
    idx = 0
    if lines and "Merged recipe summary" in lines[0]:
        idx = 1
    while idx < len(lines) and lines[idx].strip().startswith("===="):
        idx += 1

    item_header_pattern = re.compile(r'^Item\s+(.+?)\s+=>\s+type:\s+(.+)$')
    needs_pattern = re.compile(r'^-\s+Needs\s+(?:(\d+)\s*x\s+)?(.+)$')

    item_order = []
    item_data = {}

    last_unique_item_key = None
    current_item_key = None

    while idx < len(lines):
        line = lines[idx]
        idx += 1

        match_item = item_header_pattern.match(line.strip())
        if match_item:
            item_name = match_item.group(1).strip()
            item_type = match_item.group(2).strip()
            new_key = (item_name, item_type)

            if new_key not in item_data:
                # 第一次出现
                item_data[new_key] = {
                    "needs": {},
                    "lines": []
                }
                item_order.append(new_key)
                last_unique_item_key = new_key
                current_item_key = new_key
            else:
                current_item_key = new_key
            continue

        needs_match = needs_pattern.match(line.strip())
        if needs_match and current_item_key is not None:
            qty_str = needs_match.group(1)
            mat_name = needs_match.group(2).strip()
            qty = int(qty_str) if qty_str else 1

            item_data[current_item_key]["needs"][mat_name] = (
                item_data[current_item_key]["needs"].get(mat_name, 0) + qty
            )
        else:

            if current_item_key is not None:

                if last_unique_item_key != current_item_key:

                    if last_unique_item_key is not None:
                        item_data[last_unique_item_key]["lines"].append(line)
                else:

                    item_data[current_item_key]["lines"].append(line)


    output_lines = []
    for key in item_order:
        name, t = key
        info = item_data[key]

        output_lines.append(f"Item {name} => type: {t}")

        for mat_name, count in info["needs"].items():
            if count == 1:
                output_lines.append(f"- Needs {mat_name}")
            else:
                output_lines.append(f"- Needs {count} x {mat_name}")

        for extra_line in info["lines"]:
            output_lines.append(extra_line)

    return "\n".join(output_lines)



if __name__ == "__main__":
    input_text = """==== Merged recipe summary ====
Item crafting_table => type: minecraft:crafting_shaped
- Needs 4 x planks
  Item planks => type: minecraft:crafting_shapeless
  - Needs logs
    logs can be obtained by mining or other means.
Item wooden_pickaxe => type: minecraft:crafting_shaped
- Needs 3 x planks
  Item planks => type: minecraft:crafting_shapeless
  - Needs logs
    logs can be obtained by mining or other means.
Item wooden_pickaxe => type: minecraft:crafting_shaped
- Needs 2 x stick
  Item stick => type: minecraft:crafting_shaped
  - Needs 2 x planks
    Item planks => type: minecraft:crafting_shapeless
    - Needs logs
      logs can be obtained by mining or other means.
"""

    print("==== Original ====")
    print(input_text)
    print("\n==== Modified ====")
    result = modify_summary(input_text)
    print(result)
