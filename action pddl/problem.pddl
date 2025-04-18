(define (problem minecraft-problem)
 (:domain minecraft-domain)
 (:objects
    minecraft_cobblestone minecraft_crafting_table minecraft_dirt minecraft_iron_axe minecraft_logs minecraft_oak_log minecraft_oak_planks minecraft_stick minecraft_wooden_pickaxe - item
 )
 (:init
    (= (count minecraft_wooden_pickaxe) 1)
    (= (count minecraft_oak_log) 1)
    (= (count minecraft_crafting_table) 1)
    (= (count minecraft_oak_planks) 3)
    (= (count minecraft_stick) 2)
    (= (count minecraft_dirt) 10)
    (= (count minecraft_cobblestone) 3)
    (= (count minecraft_iron_axe) 1)
    (= (count minecraft_logs) 0)
    (= (agent_height) 58)
    (equipped minecraft_iron_axe)
 )
 (:goal (and
    (<= 1 (count minecraft_logs))
 ))
)
