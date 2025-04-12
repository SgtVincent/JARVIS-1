def parse_three_logs(inventory_line, equipment_line, height_line):
    inventory = {}
    equipment = []
    current_height = []

    # Parse inventory
    # Example format: "{'Now my inventory has 1 furnace, 3 oak_sapling, 2 oak_log...'}"
    if "Now my inventory has" in inventory_line:
        # Remove surrounding braces
        content = inventory_line.replace("{", "").replace("}", "")
        # Remove leading/trailing spaces and quotes
        content = content.strip().strip("'")
        # Remove trailing period if any
        content = content.rstrip(".")
        # Remove the leading phrase
        content = content.replace("Now my inventory has ", "")
        # Split by comma
        parts = content.split(",")
        for part in parts:
            part = part.strip().strip("'").rstrip(".")
            # Each part should be something like "1 furnace"
            items = part.split()
            if len(items) >= 2:
                try:
                    quantity = int(items[0])
                    name = " ".join(items[1:])
                except ValueError:
                    quantity = 1
                    name = part
                # Remove any leftover periods or quotes from the name
                name = name.strip("'").rstrip(".")
                inventory[name] = quantity

    # Parse equipment
    # Example: "{'Now I equip the furnace in mainhand.'}"
    if "Now I equip the" in equipment_line:
        content = equipment_line.replace("{", "").replace("}", "")
        content = content.strip().strip("'").rstrip(".")
        content = content.replace("Now I equip the ", "")
        content = content.replace(" in mainhand", "").strip()
        # Remove any leftover quotes or periods
        content = content.strip("'").rstrip(".")
        equipment.append(content)

    # Parse current_height
    # Example: "{'Now I locate in height of 49.'}"
    if "Now I locate in height of" in height_line:
        content = height_line.replace("{", "").replace("}", "")
        content = content.strip().strip("'").rstrip(".")
        content = content.replace("Now I locate in height of ", "")
        content = content.strip("'").rstrip(".")
        try:
            height_value = int(content)
            current_height.append(height_value)
        except ValueError:
            pass

    return inventory, equipment, current_height

if __name__ == "__main__":
    line1 = "{'Now my inventory has 1 wooden_pickaxe, 3 oak_planks, 4 dirt, 2 stick, 1 oak_log, 1 iron_axe.'}"
    line2 = "{'Now I equip the wooden_pickaxe in mainhand.'}"
    line3 = "{'Now I locate in height of 59.'}"

    inv, equip, height = parse_three_logs(line1, line2, line3)
    print(inv)
    print(equip)
    print(height)
