# LAB 13 — les trois questions

`make lab13-question Q=1` (ou 2, 3) les pose à votre agent, avec le vrai modèle ; `QUESTION="…"` en pose une autre.

1. **La question cible** — L'escale du Vent d'Autan de jeudi est-elle à risque ? Si oui, prépare la note d'alerte
   pour l'exploitant.
   Trois serveurs, une action irréversible : la confirmation du LAB 12 doit être demandée avant publication.
2. **Un seul serveur** — Quelles sont les pénalités de retard prévues au contrat de manutention de l'escale
   ESC-2026-0412 ?
   Contrôle : le plan ne doit annoncer que pharos-docs ; un appel à un autre serveur est un appel superflu.
3. **Aucune publication** — Quelles escales sont en conflit de créneau jeudi 8 octobre ?
   Contrôle : pas de publier_alerte dans le plan ni dans la trace.
