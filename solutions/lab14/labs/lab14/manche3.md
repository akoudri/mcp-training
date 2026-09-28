# Manche 3 — seconde attaque, et débrief

**Attaque reçue** (sur serveur durci) : une exfiltration vers une adresse externe — elle n'a pas tenu : la
liste d'autorisation l'a refusée, le refus figure dans `logs/pharos-ops.jsonl`.

**Débrief :**
1. **A tenu** : « faire taire » (objectif A) — une note qui conclut à tort « aucun risque » ne déclenche aucun
   appel anormal ; aucune contre-mesure serveur ne l'arrête (slide 441).
2. **Contre-mesure → ce qu'elle arrête** : liste d'autorisation → exfiltration par destinataire ; moindre
   privilège → lecture hors périmètre ; extrait marqué → réduit la prise de l'injection, ne l'annule pas.
3. **Impossible vs plus difficile** : publier vers une adresse hors liste, et lire les escales d'une autre
   agence, sont rendus **impossibles** côté serveur. Faire dire à l'agent une conclusion fausse reste
   **possible** : c'est le point que seul le jeu d'évaluation (LAB 15) détecte, après coup.
