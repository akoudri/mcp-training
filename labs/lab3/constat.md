# LAB 3 — Constat (réponse de référence)

## Ce que reçoit le client 2025-11-25, et à quel moment exact il échoue

Il échoue à sa **première requête**, `initialize` : HTTP 400, erreur `-32022 Révision non prise en
charge`. Le serveur migré lit la révision dans `params._meta`, et `initialize` n'en porte pas. Aucun
outil n'est appelé.

## Ce que reçoit le client 2026-07-28

Tout : `etat_escale`, puis `lister_mouvements` et deux `page_suivante(handle)`, 57 mouvements en trois
pages, sans session ni poignée de main.

## Quelle information, dans la requête, permet de distinguer les deux

- 2025-11-25 : la méthode `initialize`, puis l'en-tête `Mcp-Session-Id` sur toutes les requêtes
  suivantes (et `Mcp-Protocol-Version: 2025-11-25`) ;
- 2026-07-28 : `params._meta["io.modelcontextprotocol/protocolVersion"]`, avec `Mcp-Method` et
  `Mcp-Name` en en-têtes.

Quand la poignée de main a eu lieu, c'est elle qui fait foi ; l'absence de `_meta` n'est qu'un indice.

## Étape 4 — deux requêtes d'un même client ancien sur deux instances

Sans affinité, la première requête du client ancien qui atterrit sur l'instance qui n'a pas ouvert sa
session reçoit 404 « Session inconnue » : il échoue avant même la pagination. Tant qu'on sert
2025-11-25, le répartiteur doit ramener chaque session vers son instance (affinité), ou la table des
sessions doit être partagée. C'est le prix de l'état conservé pour les clients anciens, et le compteur
de l'extension B dit quand on peut cesser de le payer.
