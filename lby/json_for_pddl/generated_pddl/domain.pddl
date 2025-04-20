(define (domain minecraft_domain-domain)
 (:requirements :strips :typing :numeric-fluents)
 (:types item)
 (:constants
   minecraft_planks minecraft_crafting_table minecraft_logs minecraft_stick minecraft_wooden_pickaxe - item
 )
 (:functions (count ?item - item))
 (:action collect__logs
  :parameters ()
  :effect (and (increase (count minecraft_logs) 1)))
 (:action make__wooden_pickaxe
  :parameters ()
  :precondition (and (<= 3 (count minecraft_planks)) (<= 2 (count minecraft_stick)) (<= 1 (count minecraft_crafting_table)))
  :effect (and (decrease (count minecraft_planks) 3) (decrease (count minecraft_stick) 2) (increase (count minecraft_wooden_pickaxe) 1)))
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
