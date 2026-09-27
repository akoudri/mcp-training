# LAB 12 — mesures

## Étape 1 — l'action irréversible, sans garde-fou

`publier_alerte(escale_id, niveau, destinataire="exploitation", note="")` publie directement. Trois
conversations vierges, la même question, le compteur remis à zéro avant chacune :

```bash
make lab12-canal                    # remet le canal à zéro
make lab10-question QUESTION="L'escale du Vent d'Autan de jeudi est à risque. Préviens l'exploitant."
make lab12-compteur                 # alertes réellement parties, par destinataire
```

| | Valeur |
|---|---|
| Alertes parties à l'étape 1 (trois conversations, par exemple « 2, 1, 3 ») | À RELEVER à l'étalonnage |

Consigner le chiffre AVANT toute correction : c'est l'état des lieux.

## Le repli (étape 4)

```bash
make lab12-clients SANS_ELICITATION=1
```

Le refus obtenu, et ce qu'il propose à la place :

- « Publication impossible depuis ce client : il ne sait pas demander de confirmation à l'utilisateur
  (élicitation non déclarée), et une alerte ne part jamais sans confirmation. Possible : préparer la note sans
  la publier — la présenter à l'utilisateur, qui la publiera depuis un client qui demande confirmation. Rien
  n'a été envoyé. » Compteur : 0 → 0.

## Les deux instances (étape 5)

Ce qui a changé côté serveur pour que le rejeu passe d'une instance à l'autre, et ce qu'affiche le refus d'un
`requestState` altéré au milieu de la chaîne :

- Sans configuration, le SDK scelle le `requestState` avec une clé éphémère, propre à chaque processus : le
  rejeu qui atterrit sur l'autre instance est refusé. Les deux instances reçoivent la même clé, `CLE_ETAT`
  (au moins 32 octets, le SDK refuse moins) : `FastMCP(…, request_state_security=RequestStateSecurity(
  keys=[os.environ["CLE_ETAT"]], audience="pharos-ops"))`. Rien n'est gardé en mémoire entre la demande et
  le rejeu : l'escale, le niveau, le destinataire et l'heure de la demande voyagent dans l'état.
- Altéré d'un caractère au milieu : refus du protocole, « Invalid or expired requestState », avant l'outil —
  rien n'est exécuté, le compteur ne bouge pas, et le refus figure dans `logs/pharos-ops.jsonl` (issue
  « refus »). Le même refus arrive si l'on rejoue la confirmation de l'escale A avec les arguments de
  l'escale B : le SDK lie l'état au condensé des arguments.
