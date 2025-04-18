(define (problem minecraft-problem)
 (:domain minecraft-domain)
 (:objects
    minecraft_cobblestone minecraft_dirt minecraft_iron_axe minecraft_oak_log minecraft_oak_planks minecraft_stick minecraft_wooden_pickaxe - item
 )
 (:init
    (= (count minecraft_wooden_pickaxe) 1)
    (= (count minecraft_oak_planks) 3)
    (= (count minecraft_dirt) 4)
    (= (count minecraft_stick) 2)
    (= (count minecraft_oak_log) 1)
    (= (count minecraft_iron_axe) 1)
    (= (count minecraft_cobblestone) 0)
    (= (agent_height) 59)
    (equipped minecraft_wooden_pickaxe)
 )
 (:goal (and
    (<= 1 (count minecraft_cobblestone))
 ))
)
