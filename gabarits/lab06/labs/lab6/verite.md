# LAB 6 — Table de vérité de `pharos-quai`

Ce que chaque outil **fait réellement**. Le code est dans `serveurs/pharos_quai/` : `serveur.py` porte
le catalogue (ce que vous réécrivez), `metier.py` le comportement (auquel vous ne touchez pas).

Les paramètres font partie des schémas : on ne les renomme pas, on ne change pas leur type. La
description est l'endroit où dire ce qu'ils contiennent.

Les dates sont au format `AAAA-MM-JJ`, les heures au format `HH:MM`, heure de Paris. Nous sommes le
mardi 6 octobre 2026 ; le planning des créneaux couvre du mardi 6 au jeudi 8 octobre.

| Outil | Paramètres | Ce qu'il fait | Ce qu'il renvoie |
|---|---|---|---|
| `get_data` | `d` : une date | Liste les escales prévues à cette date, **tous quais confondus** (une escale est prévue à une date si elle commence, se poursuit ou se termine ce jour-là). | `{date, escales: [{escale_id, navire, quai, debut, fin}]}` |
| `get_data_2` | `d` : une date ; `f` : un numéro de quai (1 à 4) | Même liste, **limitée à un quai**. | `{date, quai, escales: […]}` |
| `process` | `x` : le nom d'un navire ; `d` : une date | Calcule la **première heure d'accostage possible** ce jour-là : dans les créneaux réservés au navire (sinon dans les créneaux libres d'un quai assez profond), et dans une fenêtre de pleine mer si son tirant d'eau dépasse 12 m. | `{navire, date, tirant_eau_m, maree_requise, heure, quai, jusqu_a, reserve}` ; `heure` vaut `null` s'il n'y a pas de possibilité |
| `info_quai` | `id` : un numéro de quai (1 à 4) | Donne les **caractéristiques physiques** d'un quai. Ne dit rien de son planning. | `{quai, longueur_m, tirant_eau_max_m, equipements}` |
| `search` | `q` : le nom d'un navire ; `d` : une date | Liste les **créneaux réservés** à ce navire ce jour-là (créneaux contigus fusionnés). Ne calcule pas d'heure d'accostage. | `{navire, date, creneaux: [{quai, debut, fin, escale_id}]}` ; liste vide si aucun |
| `check` | `id` : un numéro de quai ; `d` : une date ; `h` : une heure | Dit si le **créneau de deux heures** qui contient cette heure, à ce quai, est libre ou réservé, et à qui. | `{quai, date, creneau: {debut, fin}, libre, escale_id, navire}` |

Erreurs métier (`isError`), avec un message qui dit quoi faire : navire inconnu (le message liste les
navires connus), quai inconnu, date hors du planning des créneaux (`process`, `search`, `check`).

Le nom du navire est reconnu sans tenir compte de la casse, de l'apostrophe typographique ni de
l'article : « le vent d’autan » désigne le *Vent d'Autan*.
