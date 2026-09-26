# LAB 5 — La charge du handle (réponse de référence)

## Ce que la charge contient

| Champ | Pourquoi il y est | Ce qui casse s'il manque |
|---|---|---|
| `e` — identifiant d'escale | portée : le handle ne vaut que pour ce dossier | on lit le dossier du voisin en changeant l'argument |
| `d` — identifiant du contrat | retrouve le document sans rien garder côté serveur | il faudrait une table en mémoire : casse à la seconde instance |
| `exp` — ajouté par `signer()` | durée de vie bornée (15 min) | un handle volé vaut pour toujours |

## Ce que la charge ne contiendra pas, et pourquoi

- **Le nom du navire** : donnée métier, lisible par qui décode le handle ; il finit dans les journaux et les tickets. L'identifiant suffit.
- **Le texte de la section en cours** : le handle grossirait jusqu'à se faire tronquer par le modèle, qui le recopie à chaque tour. Le handle désigne un état, il ne le transporte pas.
- **L'identité complète de l'utilisateur** : donnée personnelle ; la charge est signée, pas chiffrée. Si une portée par appelant est nécessaire, un identifiant opaque suffit.
