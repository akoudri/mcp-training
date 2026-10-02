# LAB 2 — Inventaire des ruptures (réponse de référence)

| Rupture | Où elle se manifeste | Ce qu'il faut faire |
|---|---|---|
| Poignée de main `initialize` / `initialized` | `point_mcp` : `initialize` ouvre la session ; toute autre requête sans session reçoit 400 « Session absente ». Le client 2026-07-28 échoue dès sa première requête. | Retirer la branche `initialize` et l'exigence de session : chaque requête est traitée seule. |
| En-tête `Mcp-Session-Id` | Émis dans la réponse à `initialize`, exigé ensuite (400 s'il manque, 404 s'il est inconnu) ; visible dans l'Inspector sur chaque échange. | Ne plus l'émettre ni le lire. Révision et client se lisent dans `params._meta` (`io.modelcontextprotocol/protocolVersion`, `…/clientInfo`), requête par requête. |
| `server/discover` absent | `-32601 Méthode inconnue` : rien ne le signale tant qu'aucun client ne l'appelle (le mode `auto` le sonde, puis se replie). | L'implémenter : `supportedVersions: ["2026-07-28"]`, capacités, identité dans `_meta`, et `resultType`, `ttlMs`, `cacheScope`, exigés par le client 2026-07-28. |
| État conservé côté serveur | `Sessions` : le curseur `{"escale_id", "page"}` de `page_suivante` vit dans la session, donc dans **une** instance. | Le rendre au client : un handle signé (`pharos.jetons`), daté, expirant, portant escale, appelant et position ; `page_suivante(handle)`. |
| Code d'erreur `-32002` | `tools/call` sur une escale inconnue : erreur JSON-RPC `-32002`, code propre à MCP en 2025-11-25. | À consigner : en 2026-07-28, ce cas relève de `-32602`. Traité au LAB 3, avec la liste de migration. |

## Notes

- `Mcp-Method` et `Mcp-Name` déclarent, ils ne prouvent pas : le serveur migré refuse (400) une requête
  dont les en-têtes contredisent le corps.
- Le client met en cache la liste des outils : redémarrer le client après avoir changé la signature de
  `page_suivante`.
