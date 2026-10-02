# Fiche de sécurité — pharos-data

| Rubrique | |
|---|---|
| **Périmètre** | escales, mouvements, navires, quais ; conflits de créneau, escales à risque, requête SQL en lecture stricte. |
| **Données touchées** | données d'exploitation du port. Cloisonnées par identité : un agent maritime ne voit que ses escales. |
| **Actions irréversibles exposées** | aucune (lecture seule). |
| **Droits requis** | jeton porteur ; chaque requête s'exécute sous le rôle de l'appelant, la politique RLS filtre (LAB 9). |
| **Propriétaire** | binôme PHAROS (équipe données). |

Durcissement : le cloisonnement RLS du LAB 9 tient déjà le confused deputy sur les données ; rien à ajouter ici.
