(define (domain minecraft-domain)
 (:requirements :strips :typing :numeric-fluents)
 (:types item)
 (:predicates (equipped ?tool - item))
 (:functions (count ?item - item) (agent_height))

 
 (:action break_iron_blocks
  :parameters ()
  :precondition (and (equipped minecraft_stone_pickaxe) (<= (agent_height) 15))
  :effect (and (increase (count minecraft_iron_ore) 1))
 )


 (:action break_iron_ore_blocks
  :parameters ()
  :precondition (and (equipped minecraft_stone_pickaxe) (<= (agent_height) 15))
  :effect (and (increase (count minecraft_iron_ore) 1))
 )


 (:action break_the_stone_blocks_and_mine_iron_ore
  :parameters ()
  :precondition (and (equipped minecraft_stone_pickaxe) (<= (agent_height) 15))
  :effect (and (increase (count minecraft_iron_ore) 1))
 )


 (:action chop_down_the_tree
  :parameters ()
  :precondition (and)
  :effect (and (increase (count minecraft_logs) 1))
 )


 (:action dig_down
  :parameters ()
  :precondition (and (or (equipped minecraft_wooden_pickaxe) (equipped minecraft_stone_pickaxe)) (> (agent_height) 15))
  :effect (and (increase (count minecraft_cobblestone) 1) (increase (count minecraft_iron_ore) 1) (decrease (agent_height) 5))
 )


 (:action equip_iron_axe_to_chop_down_the_tree
  :parameters ()
  :precondition (and (<= 1 (count minecraft_iron_axe)))
  :effect (and (equipped minecraft_iron_axe))
 )


 (:action equip_stone_pickaxe
  :parameters ()
  :precondition (and (<= 1 (count minecraft_stone_pickaxe)))
  :effect (and (equipped minecraft_stone_pickaxe))
 )


 (:action equip_wooden_pickaxe
  :parameters ()
  :precondition (and (<= 1 (count minecraft_wooden_pickaxe)))
  :effect (and (equipped minecraft_wooden_pickaxe))
 )

)
