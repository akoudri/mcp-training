# Fiche de sécurité — pharos-docs

| Rubrique | |
|---|---|
| **Périmètre** | lecture des contrats de manutention, connaissements et avis d'escale du corpus ; recherche de clause, lecture par sections (handles). Aucune écriture, aucune action externe. |
| **Données touchées** | texte des documents d'escale. Un document déposé par un tiers entre ici : c'est la surface d'injection indirecte (bloc 22.2). |
| **Actions irréversibles exposées** | aucune. |
| **Droits requis** | lecture seule du corpus ; les handles sont signés (CLE_SERVEUR), à durée bornée. |
| **Propriétaire** | binôme PHAROS (équipe documentaire). |

Durcissement (manche 2) : les extraits reviennent dans `extrait_document`, marqué « donnée non fiable » et
borné à 1 500 caractères — le modèle ne doit pas exécuter ce qu'un document lui demande (bloc 22.7).
