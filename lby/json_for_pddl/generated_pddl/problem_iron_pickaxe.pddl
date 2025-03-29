(define (problem minecraft_domain-problem)
 (:domain minecraft_domain-domain)
 (:objects
 )
 (:init (= (count minecraft_planks) 0) (= (count minecraft_iron_ore) 0) (= (count minecraft_iron_pickaxe) 0) (= (count minecraft_iron_ingot) 0) (= (count minecraft_stick) 0) (= (count minecraft_cobblestone) 0) (= (count minecraft_crafting_table) 0) (= (count minecraft_furnace) 0) (= (count minecraft_logs) 0))
 (:goal (and (<= 1 (count minecraft_iron_pickaxe))))
)
