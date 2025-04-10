(define (problem make_golden_shovel-problem)
 (:domain make_golden_shovel-domain)
 (:objects
   minecraft_oak_planks minecraft_crafting_table minecraft_gold_ingot minecraft_stick minecraft_diamond minecraft_cobblestone minecraft_golden_shovel minecraft_leather minecraft_iron_ore - item
 )
 (:init (= (count minecraft_oak_planks) 999) (= (count minecraft_crafting_table) 0) (= (count minecraft_gold_ingot) 999) (= (count minecraft_stick) 999) (= (count minecraft_diamond) 999) (= (count minecraft_cobblestone) 999) (= (count minecraft_golden_shovel) 0) (= (count minecraft_leather) 999) (= (count minecraft_iron_ore) 999))
 (:goal (and (<= 1 (count minecraft_golden_shovel))))
)
