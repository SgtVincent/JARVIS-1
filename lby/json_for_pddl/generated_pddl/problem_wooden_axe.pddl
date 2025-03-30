(define (problem minecraft-domain-problem)
 (:domain minecraft-domain-domain)
 (:objects 
   minecraft_wooden_axe minecraft_planks minecraft_logs minecraft_crafting_table minecraft_stick - item
 )
 (:init (= (count minecraft_wooden_axe) 0) (= (count minecraft_planks) 0) (= (count minecraft_logs) 0) (= (count minecraft_crafting_table) 0) (= (count minecraft_stick) 0))
 (:goal (and (<= 1 (count minecraft_wooden_axe))))
)
