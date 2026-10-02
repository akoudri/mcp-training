# Fiche de sécurité — pharos-ops

| Rubrique | |
|---|---|
| **Périmètre** | météo marine, référentiel navires, recalcul du plan de quai, **publication d'alerte** (irréversible). |
| **Données touchées** | fiches navires (référentiel), plan de quai ; le canal d'alertes fait sortir une donnée vers un destinataire. |
| **Actions irréversibles exposées** | `publier_alerte` : une alerte partie ne se rattrape pas. |
| **Droits requis** | jeton porteur ; confirmation humaine (LAB 12) avant publication. |
| **Propriétaire** | binôme PHAROS (équipe exploitation). |

Durcissement (manche 2), deux contre-mesures :
1. **Liste d'autorisation de destinataires** (`PHAROS_DESTINATAIRES`) sur `publier_alerte` : un destinataire
   injecté est refusé et journalisé — ferme l'exfiltration par canal légitime (bloc 22.5).
2. **Moindre privilège** sur `navire_par_nom` : sous l'identité d'un agent, les escales des navires d'une autre
   agence sont masquées — ferme le confused deputy (bloc 22.3).
