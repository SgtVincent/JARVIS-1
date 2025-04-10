(define (problem minecraft_domain-problem)
 (:domain minecraft_domain-domain)
 (:objects
 )
 (:init (= (count minecraft_planks) 0))
 (:goal (and (<= 1 (count minecraft_planks))))
)
