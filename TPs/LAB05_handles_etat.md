# LAB 5 — Handles d'état

**Module OR2** · durée 1 h 30
**Artefact produit** : **A5** — les handles d'état signés dans `pharos-docs`
**Checkpoint de sortie** : `etat/or2-fin`

---

## Contexte

Un contrat de manutention fait quarante à quatre-vingts pages. L'exploitant ne le lit jamais en
entier : il ouvre le dossier de l'escale, consulte la clause de pénalités, puis celle des délais,
puis referme.

Aujourd'hui, `pharos-docs` refait tout le travail d'ouverture à chaque appel. Ce lab lui donne une
**session d'analyse** : un dossier qu'on ouvre une fois et qu'on parcourt ensuite — sans que le
serveur ne conserve quoi que ce soit entre deux requêtes.

C'est le premier endroit du fil rouge où PHAROS a un état. Le module PR3 a expliqué pourquoi le
handle existe ; ce lab l'écrit, et surtout écrit tout ce qui doit le **refuser**.

**Répartition indicative du temps** : 15 min de conception · 30 min pour les deux outils ·
25 min pour les trois refus · 10 min pour le test des deux instances · 10 min de reformatage et
mise en commun.

---

## Prérequis

| | |
|---|---|
| **Modules** | OR2 (blocs 9.1 à 9.5), PR3 (bloc 5.5) |
| **Labs** | LAB 1, LAB 4 |
| **Artefacts consommés** | **A1** — `pharos-docs v0` · **A4** — `pharos-client` |
| **Fourni** | signature et vérification, découpage en sections, répartiteur à deux instances |

```bash
make depart LAB=5         # branche binome-<B>-lab05 depuis etat/or1-fin, charge.md et mesures.md
```

### Ce qui est fourni

```python
from pharos_docs.jetons import signer, verifier
# signer(charge: dict, cle: str, duree_s: int = 900) -> str     ajoute lui-même le champ exp
# verifier(jeton: str, cle: str) -> dict     lève JetonInvalide si signature ou date KO

from pharos_docs.extraction import sections_du_document
# sections_du_document(document_id) -> list[Section]   (titre, page_debut, page_fin)
```

La cryptographie est fournie : ce n'est pas la leçon. La leçon, ce sont les cinq propriétés du bloc
9.2 — et notamment **ce que l'on met, ou non, dans la charge**.

`signer` **signe, il ne chiffre pas** : le jeton produit est lisible (type JWT), pas opaque au sens
cryptographique. Opaque pour le modèle : il ne doit rien pouvoir en tirer. Signé ne veut pas dire
chiffré — c'est ce qui doit guider la liste des champs exclus de l'étape 1.

---

## SOCLE — pour tous

### Étape 1 — Concevoir la charge, avant de coder

Remplir `labs/lab5/charge.md` **avant d'ouvrir l'éditeur** :

| Champ | Pourquoi il y est | Ce qui casse s'il manque |
|---|---|---|
| | | |

Puis, dans le même fichier, la seconde liste — celle qu'on oublie toujours :

> **Ce que la charge ne contiendra pas, et pourquoi.**

Trois candidats à trancher explicitement : le nom du navire, le texte de la section en cours,
l'identité complète de l'utilisateur.

### Étape 2 — Les deux outils

| Outil | Entrées | Sortie |
|---|---|---|
| `ouvrir_dossier` | `escale_id` | La liste des sections disponibles, **et** un handle |
| `lire_section` | `handle`, `section` | Le contenu de la section, **et** un nouveau handle |

Le handle est opaque, signé, daté, porteur d'une portée, et sans donnée sensible. Expiration :
quinze minutes.

La forme des sorties est imposée (le vérificateur s'y appuie) : `ouvrir_dossier` rend
`{"handle": …, "sections": [{"id": "CM-0412:s07", "titre": …, "pages": [début, fin]}]}` — l'identifiant
de section porte le document, sans quoi le refus « hors portée » ne se teste pas ; `lire_section`
rend `{"handle": …, "section": {…}}`.

Vérifier le tout via la boucle du LAB 4, sur l'enchaînement :

> Ouvre le dossier de l'escale ESC-2026-0412, puis donne-moi la clause de pénalités, puis celle des
> délais.

### Étape 3 — Les trois refus

| Refus | Comment le provoquer |
|---|---|
| Handle expiré | Forcer l'expiration à cinq secondes, attendre, réessayer |
| Handle altéré ou forgé | Changer un caractère ; puis fabriquer un handle avec une autre clé |
| Handle hors portée | Utiliser le handle de l'escale A pour lire une section de l'escale B |

Les trois produisent une **erreur métier**, jamais une exception. Le message doit dire quoi faire —
rouvrir le dossier — et non « handle invalide ».

### Étape 4 — Le test des deux instances

```bash
make lab5-deux-instances
make lab5-verifier
```

Enchaîner `ouvrir_dossier` puis `lire_section` à travers le répartiteur. Les deux requêtes
atterrissent sur des instances différentes.

### Étape 5 — Reformater le résultat

`lire_section` renvoie sans doute une belle phrase française. La convertir en structure, selon le
bloc 9.5, et relever dans `labs/lab5/mesures.md` le contexte final avant et après, sur
l'enchaînement de l'étape 2.

### Critères de réussite

- [ ] `labs/lab5/charge.md` est rempli, **et la liste des champs exclus est justifiée**.
- [ ] `ouvrir_dossier` rend un handle ; `lire_section` le consomme et en rend un nouveau.
- [ ] Le handle ne contient aucune donnée métier **sensible** (ni texte, ni nom de navire), ni
      donnée personnelle. L'identifiant d'escale, qui porte la portée, est admis.
- [ ] Les trois refus produisent une erreur métier dont le modèle sait quoi faire.
- [ ] Le contexte final après reformatage est mesuré et consigné.
- [ ] **Critère décisif** — deux requêtes portant le même handle, atterrissant sur deux instances
      différentes, se comportent identiquement ; et un handle altéré d'un seul caractère est refusé.

---

## EXTENSION — pour aller plus loin

*Jamais évaluée, jamais due.*

### A — Le handle tournant

Faire en sorte que chaque `lire_section` **invalide** le handle précédent, en plus d'en émettre un
nouveau.

C'est plus sûr : un handle intercepté ne vaut qu'un appel. Mais ce n'est pas gratuit — répondre par
écrit à deux questions :

- que se passe-t-il si le modèle relit deux fois la même section, en repartant du même handle ?
- que devient l'ouverture de deux dossiers en parallèle, annoncée comme un avantage au bloc 9.3 ?

Il n'y a pas de bonne réponse universelle. Il y a un arbitrage, et il se documente.

### B — La compaction

Dans la boucle du LAB 4, remplacer le contenu des sections lues il y a plus de trois tours par leur
seul handle, rechargeable au besoin. C'est la troisième stratégie du bloc 9.4 —
l'externalisation.

Mesurer le contexte final. Puis vérifier ce qui compte vraiment : **le nombre de tours a-t-il
augmenté ?** Si l'agent doit recharger deux fois ce qu'il avait déjà, la compaction a coûté plus
qu'elle n'a rapporté.

### C — La rotation de la clé serveur

Faire tourner `CLE_SERVEUR` sans invalider les handles en circulation : accepter deux clés en
vérification, n'en utiliser qu'une en signature.

C'est exactement le raisonnement du module PR5 — servir l'ancien pendant qu'on bascule — appliqué à
autre chose qu'une révision de protocole.

---

## Pièges & indices

**Ne pas mettre le texte de la section dans la charge.** Le handle deviendrait énorme, et il voyage
dans le contexte du modèle à chaque tour. Le handle désigne un état, il ne le transporte pas.

**Ne pas y mettre de donnée personnelle.** Le handle finit dans les journaux, et de là dans les
tickets de support. La chaîne du bloc 9.2 n'est pas une hypothèse d'école.

**Quinze minutes, pas vingt-quatre heures.** La tentation de mettre une expiration confortable
« quitte à la raccourcir plus tard » va dans le mauvais sens : on ne raccourcit jamais une
expiration en production sans casser quelqu'un. Commencer court, allonger si c'est mesurément
gênant.

**Un handle non signé se teste en trente secondes.** L'incrémenter, et voir si l'on obtient le
dossier du voisin. Si le test réussit, ce n'est pas un jeton.

**Le handle doit rester court.** Le modèle le recopie caractère par caractère d'un tour à l'autre.
Un jeton de huit cents caractères se fait tronquer ou déformer plus souvent qu'on ne le croit, et le
symptôme — « signature invalide » alors que tout semble correct — coûte cher à diagnostiquer. Si la
charge grossit, c'est le signal qu'elle contient quelque chose qui n'a rien à y faire.

**Le message de refus dit quoi faire.** « Handle invalide » laisse le modèle sans recours. « Cette
session d'analyse a expiré, rouvrir le dossier de l'escale » lui donne le tour suivant. C'est le
bloc 4.3 de PR2, appliqué à un cas nouveau.

**Ne pas exposer d'outil `verifier_handle`.** Le modèle n'a rien à en faire, et l'exposer offre à
un attaquant un oracle de vérification gratuit.

**Le test sur une seule instance ne prouve rien.** Un handle mal conçu — par exemple une clé de
dictionnaire côté serveur — fonctionne parfaitement en local. C'est le même piège qu'au LAB 2, et il
se retend ici.

**Ne pas garder de trace côté serveur des handles émis.** La tentation, pour gérer la révocation,
est de tenir une liste. Elle réintroduit exactement l'état que PR3 a supprimé. La révocation
d'urgence se fait par rotation de clé — voir l'extension C.

---

## Livrable

| | |
|---|---|
| **Produit** | `serveurs/pharos_docs/` — session d'analyse, deux outils, trois refus |
| **Consigné** | `labs/lab5/charge.md` et `labs/lab5/mesures.md` |
| **Artefact du fil rouge** | **A5**, consommé par OR3 et SG1 |
| **Checkpoint** | `etat/or2-fin` |

```bash
make lab5-verifier
git add serveurs/ labs/lab5/ && git commit -m "LAB 5 — handles d'état"
```

**Suite.** Le module **SR1** change de registre. Jusqu'ici, la qualité d'un serveur se discutait ;
à partir de demain matin, elle se mesure. Un catalogue volontairement mauvais vous sera fourni, et
le livrable du LAB 6 sera un chiffre : le taux de bon choix d'outil, avant et après réécriture.

Le nombre d'appels relevé à la question 1 du LAB 4 sera votre point de comparaison.
