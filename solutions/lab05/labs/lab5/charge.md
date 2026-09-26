# LAB 5 — La charge du handle (réponse de référence)

## Ce que la charge contient

| Champ | Pourquoi il y est | Ce qui casse s'il manque |
|---|---|---|
| `d` — identifiant du contrat | portée : `lire_section` refuse toute section dont le document ne correspond pas à `charge["d"]` ; retrouve aussi le document sans rien garder côté serveur | on lit une section du dossier voisin en changeant l'argument ; il faudrait une table en mémoire pour retrouver le document, qui casserait à la seconde instance |
| `e` — identifiant d'escale | redondant avec `d` pour la portée (déjà assurée par `d`) : ne sert qu'à nommer l'escale dans le message de refus et dans la charge du handle suivant, pour que les messages restent lisibles | rien ne casse fonctionnellement ; seuls les messages perdent l'identifiant d'escale — le premier champ à retirer si la charge doit encore rétrécir |
| `exp` — ajouté par `signer()` | durée de vie bornée (15 min) | un handle volé vaut pour toujours |

## Ce que la charge ne contiendra pas, et pourquoi

- **Le nom du navire** : donnée métier, lisible par qui décode le handle ; il finit dans les journaux et les tickets. L'identifiant suffit.
- **Le texte de la section en cours** : le handle grossirait jusqu'à se faire tronquer par le modèle, qui le recopie à chaque tour. Le handle désigne un état, il ne le transporte pas.
- **L'identité complète de l'utilisateur** : donnée personnelle ; la charge est signée, pas chiffrée. Si une portée par appelant est nécessaire, un identifiant opaque suffit.
