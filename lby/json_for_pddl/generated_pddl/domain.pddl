(define (domain minecraft_domain-domain)
 (:requirements :strips :typing :numeric-fluents)
 (:types item)
 (:constants
   minecraft_crafting_table minecraft_planks minecraft_logs - item
 )
 (:functions (count ?item - item))
 (:action collect__logs
  :parameters ()
  :effect (and (increase (count minecraft_logs) 1)))
 (:action make__crafting_table
  :parameters ()
  :precondition (and (<= 4 (count minecraft_planks)))
  :effect (and (decrease (count minecraft_planks) 4) (increase (count minecraft_crafting_table) 1)))
 (:action make__planks
  :parameters ()
  :precondition (and (<= 1 (count minecraft_logs)))
  :effect (and (decrease (count minecraft_logs) 1) (increase (count minecraft_planks) 4)))
)
