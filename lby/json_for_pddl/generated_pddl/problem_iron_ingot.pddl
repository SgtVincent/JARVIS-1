(define (problem make_iron_ingot-problem)
 (:domain make_iron_ingot-domain)
 (:objects
   minecraft_oak_planks minecraft_gold_ingot minecraft_stick minecraft_diamond minecraft_cobblestone minecraft_iron_ingot minecraft_leather minecraft_furnace minecraft_iron_ore - item
 )
 (:init (= (count minecraft_oak_planks) 999) (= (count minecraft_gold_ingot) 999) (= (count minecraft_stick) 999) (= (count minecraft_diamond) 999) (= (count minecraft_cobblestone) 999) (= (count minecraft_iron_ingot) 0) (= (count minecraft_leather) 999) (= (count minecraft_furnace) 0) (= (count minecraft_iron_ore) 999))
 (:goal (and (<= 1 (count minecraft_iron_ingot))))
)
