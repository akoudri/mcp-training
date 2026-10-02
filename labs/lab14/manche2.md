# Manche 2 — durcir

1. **Liste d'autorisation de destinataires** (`publier_alerte`, `PHAROS_DESTINATAIRES`) — arrête, de cette
   attaque-là : la publication vers `veille@armateur-exemple.test` (destinataire hors liste) est refusée et
   journalisée ; le compteur reste à zéro pour cette adresse.
2. **Moindre privilège** (`navire_par_nom`) — arrête, de l'attaque C : sous `jeton-rance`, les escales du
   *Cormoran* (agence Iroise) sont masquées ; la trace ne contient plus d'escale hors périmètre.

Les trois fiches de sécurité d'une page sont remplies (securite/fiche-*.md).
