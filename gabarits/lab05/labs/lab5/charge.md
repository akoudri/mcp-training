# LAB 5 — La charge du handle, conçue avant de coder

À remplir **avant d'ouvrir l'éditeur**.

La forme des sorties est imposée (le vérificateur s'y appuie) :
- `ouvrir_dossier(escale_id)` → `{"handle": …, "sections": [{"id": "CM-0412:s07", "titre": …, "pages": [début, fin]}]}`
  (l'identifiant de section porte le document : sans cela, le refus « hors portée » ne se teste pas) ;
- `lire_section(handle, section)` → `{"handle": …, "section": {…}}`.

Signer avec `from pharos_docs.jetons import signer, verifier` :
`signer(charge, cle, duree_s=900)` ajoute lui-même le champ `exp` ; `verifier(jeton, cle)` lève
`JetonExpire` ou `JetonAltere` (deux cas de `JetonInvalide`). La clé : `os.environ["CLE_SERVEUR"]`.

## Ce que la charge contient

| Champ | Pourquoi il y est | Ce qui casse s'il manque |
|---|---|---|
| | | |

## Ce que la charge ne contiendra pas, et pourquoi

- Le nom du navire : …
- Le texte de la section en cours : …
- L'identité complète de l'utilisateur : …
