# LAB 3 — Constat, avant de coder

Lancer `make lab3-clients` : les deux clients de test jouent le même scénario (etat_escale, puis
lister_mouvements et page_suivante) contre le serveur tel que le LAB 2 l'a laissé. Le trafic est dans
l'Inspector (http://localhost:7001, port 8104).

## Ce que reçoit le client 2025-11-25, et à quel moment exact il échoue

## Ce que reçoit le client 2026-07-28

## Quelle information, dans la requête, permet de distinguer les deux

## Étape 4 — deux requêtes d'un même client ancien sur deux instances

`make lab3-verifier` rejoue le client ancien derrière un répartiteur **sans** affinité de session et
affiche ce qui arrive. Ce qu'on en conclut (même si on ne le corrige pas aujourd'hui) :
