(define (domain minecraft_domain-domain)
 (:requirements :strips :typing :numeric-fluents)
 (:types item)
 (:constants
   minecraft_stone_pickaxe minecraft_crafting_table minecraft_planks minecraft_cobblestone minecraft_stick minecraft_logs - item
 )
 (:functions (count ?item - item))
 (:action collect__logs
  :parameters ()
  :effect (and (increase (count minecraft_logs) 1)))
 (:action collect__cobblestone
  :parameters ()
  :effect (and (increase (count minecraft_cobblestone) 1)))
 (:action make__stone_pickaxe
  :parameters ()
  :precondition (and (<= 3 (count minecraft_cobblestone)) (<= 2 (count minecraft_stick)) (<= 1 (count minecraft_crafting_table)))
  :effect (and (decrease (count minecraft_cobblestone) 3) (decrease (count minecraft_stick) 2) (increase (count minecraft_stone_pickaxe) 1)))
 (:action make__crafting_table
  :parameters ()
  :precondition (and (<= 4 (count minecraft_planks)))
  :effect (and (decrease (count minecraft_planks) 4) (increase (count minecraft_crafting_table) 1)))
 (:action make__planks
  :parameters ()
  :precondition (and (<= 1 (count minecraft_logs)))
  :effect (and (decrease (count minecraft_logs) 1) (increase (count minecraft_planks) 4)))
 (:action make__stick
  :parameters ()
  :precondition (and (<= 2 (count minecraft_planks)) (<= 1 (count minecraft_crafting_table)))
  :effect (and (decrease (count minecraft_planks) 2) (increase (count minecraft_stick) 4)))
)
