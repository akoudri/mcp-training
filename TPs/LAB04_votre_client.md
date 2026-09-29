# LAB 4 — Votre client

**Module OR1** · durée 1 h 30
**Artefact produit** : **A4** — `pharos-client`, la boucle agentique instrumentée
**Checkpoint de sortie** : `etat/or1-fin`

---

## Contexte

Depuis le début du parcours, un client fourni interroge vos serveurs. Ce lab produit le vôtre.

`pharos-client` est la boucle : elle construit le contexte, laisse le modèle choisir, exécute contre
`pharos-docs`, réinjecte, et sait s'arrêter. Environ quatre-vingts lignes. Aucun cadre
d'orchestration.

C'est l'artefact le plus consommé du parcours : **sept modules s'appuient dessus** — OR2, TQ1, DA3,
IS2, IS3, SR3 et OR3. Chaque serveur écrit à partir de demain sera exercé par cette boucle, le jour
même. Ce qui est mal instrumenté ici se paiera tous les jours suivants.

**Répartition indicative du temps** : 25 min pour la boucle nue · 25 min pour l'instrumentation ·
20 min pour les arrêts · 10 min pour la question impossible · 10 min de relevé et mise en commun.

---

## Prérequis

| | |
|---|---|
| **Modules** | OR1 (blocs 8.1 à 8.5) |
| **Labs** | LAB 1 |
| **Artefacts consommés** | **A1** — `pharos-docs v0` |
| **Fourni** | transport MCP, adaptateur de modèle, affichage d'arbre, trois questions de référence |

```bash
make depart LAB=4         # branche binome-<B>-lab04 depuis etat/pr5-fin, client fourni et squelette de boucle
make lab4-docs            # démarre pharos-docs v0
```

### Ce qui est fourni, et ce qui ne l'est pas

```python
from pharos_client.transport import Session     # tools/list, tools/call — MCP déjà branché
from pharos_client          import modele      # modele.completer(...) : appel au modèle, avec outils
from pharos_client.trace     import afficher    # rendu de l'arbre d'appels
```

**Fourni** : le transport MCP et l'adaptateur de modèle. Réimplémenter le protocole n'est pas
l'objet du lab, et vous l'avez déjà lu au module PR3.

`modele.completer` expose le format **OpenAI / Chat Completions** (passerelle multi-fournisseurs), modèle
`google/gemini-3.6-flash`. Les appels d'outils arrivent dans `tool_calls[].function.arguments`,
une **chaîne JSON** — donc syntaxiquement invalide à l'occasion : un mode d'échec de plus à traiter
comme une erreur métier.

**Pas fourni** : la boucle, la collecte de la trace, les critères d'arrêt. C'est le lab.

`afficher(trace)` attend une liste d'enregistrements portant les cinq champs du bloc 8.5. Le format
exact est décrit dans le squelette.

---

## SOCLE — pour tous

### Étape 1 — La boucle nue

Écrire la boucle avec le seul arrêt heureux : le modèle ne demande plus d'outil.

Vérifier sur la **question 1** :

> Quelles sont les pénalités de retard prévues au contrat de manutention de l'escale ESC-2026-0412 ?

Deux appels sont attendus. S'il y en a huit, ne pas corriger tout de suite : l'étape 2 dira
pourquoi.

### Étape 2 — Les cinq champs

Instrumenter, en collectant pour chaque appel :

| Champ | Remarque |
|---|---|
| Identifiant de corrélation | Un seul pour toute l'exécution |
| Numéro de tour | Sans lui, l'ordre est perdu dès qu'il y a deux appels au même tour |
| Outil et arguments | Normalisés, **secrets masqués à l'écriture** |
| Durée et taille du résultat | En millisecondes et en octets |
| Tokens cumulés | Avant l'appel au modèle, pas après |

Puis afficher l'arbre avec `afficher(trace)`, et **reposer la question 2** :

> Résume les obligations de l'opérateur portuaire pour l'escale ESC-2026-0412.

### Étape 3 — Les deux autres arrêts

Ajouter le budget — nombre de tours **et** nombre de tokens — puis l'arrêt sur échec non
récupérable. Dans les trois cas, l'arrêt doit **remonter la trace complète**, pas seulement un
message.

### Étape 4 — La question impossible

> Quelle est la météo à Marseille jeudi ?

Aucun outil de `pharos-docs` ne peut y répondre. Observer ce que fait la boucle, et faire en sorte
qu'elle s'arrête proprement en deux tours au plus, avec une réponse honnête.

**Ne pas ajouter d'outil météo.** `pharos-ops` arrive au module IS2 ; l'objet ici est l'arrêt.

### Étape 5 — Le relevé

Consigner dans `labs/lab4/mesures.md` :

- le coût fixe : consigne système + catalogue, avant toute question ;
- le contexte au dernier tour de la question 2 ;
- les tokens d'entrée cumulés sur l'exécution — la facture est la **somme** des envois, pas la
  taille au dernier tour ;
- le nombre de tours et la durée totale des trois questions.

Comparer aux ordres de grandeur du bloc 8.2. L'écart est intéressant dans les deux sens.

### Critères de réussite

- [ ] La question 1 obtient une réponse correcte, sans intervention.
- [ ] La trace porte les cinq champs, pour chaque appel.
- [ ] `afficher(trace)` produit un arbre : exécution → tour → appels.
- [ ] Le budget coupe, sur les tours comme sur les tokens, et l'exception porte la trace.
- [ ] La question 3 s'arrête en deux tours au plus, avec une réponse honnête.
- [ ] Les mesures de l'étape 5 sont consignées.
- [ ] **Critère décisif** — donner votre trace au binôme voisin, sans le code. Il doit pouvoir
      décrire ce qui s'est passé : quels outils, dans quel ordre, avec quels arguments, et pourquoi
      la boucle s'est arrêtée.

---

## EXTENSION — pour aller plus loin

*Jamais évaluée, jamais due.*

### A — Provoquer une boucle, puis la détecter

Faire échouer `rechercher_clause` systématiquement, de la même façon, et observer le
comportement : le modèle réessaie, souvent à l'identique.

Implémenter alors la détection par signature du bloc 8.4 :

```python
signature = (appel.nom, hachage(sans_curseur(appel.arguments)))
if trace.compte(signature) >= 3:
    raise BoucleDetectee(trace)
```

Puis vérifier le faux positif : une pagination légitime ne doit **pas** déclencher l'alarme.

### B — Le plan explicite

Ajouter un appel de planification avant l'exécution, selon le bloc 8.3. Afficher le plan, puis, à la
fin, le comparer à la trace réelle.

La question qui compte : sur la question 2, le modèle a-t-il suivi son propre plan ? S'il s'en est
écarté, avait-il raison de le faire ?

### C — Le prix de la troncature

Tronquer chaque résultat d'outil à cinq cents tokens côté client, et refaire le relevé de l'étape 5.

Deux chiffres à comparer : le contexte final, et le nombre de tours nécessaires. Le second peut
augmenter — auquel cas la troncature au client n'était pas une bonne idée, et le module SR2 dira
pourquoi elle est mieux placée côté serveur.

---

## Pièges & indices

**Ne pas réimplémenter MCP.** Le transport est fourni et branché. Toute minute passée sur
`tools/call` est une minute perdue pour l'instrumentation, qui est le vrai sujet.

**Réinjecter le tour du modèle en entier.** L'oubli classique consiste à ne réinjecter que les
résultats d'outils, sans le message qui les a demandés. La corrélation par identifiant, vue au bloc
2.2, est alors rompue, et le modèle repose la même question au tour suivant. Si vous observez des
appels redondants dès le deuxième tour, c'est presque toujours cela. Y compris les blocs de
réflexion si le modèle en produit : ils font partie du tour — se conformer aux règles du
fournisseur.

**Une erreur métier n'est pas une exception.** Un résultat avec `isError` se réinjecte comme
n'importe quel résultat : c'est ce qui permet au modèle de se corriger, et c'est tout l'intérêt de
la distinction du bloc 4.3. Le rattraper comme une exception arrête la boucle et annule le travail
du LAB 1.

**Les tokens se comptent avant l'appel, pas après.** Un budget vérifié après coup est un budget
dépassé. Le contrôle se place au moment où l'on décide d'envoyer. Mais l'usage réel (`usage`) n'est
renvoyé par l'API **qu'après** l'appel : estimer avant (compteur du fournisseur ou approximation),
réconcilier après avec l'usage renvoyé, et tracer l'écart entre les deux. Que l'adaptateur `modele`
fourni expose ou non un compteur : à préciser selon l'adaptateur.

**Collecter, puis afficher.** Afficher au fil de l'eau avec des `print` entrelace les appels
parallèles et rend la trace illisible exactement quand elle devient utile. Collecter dans la
structure, afficher à la fin.

**Masquer les secrets à l'écriture.** Il n'y a pas encore de clé d'API dans `pharos-docs`, mais il y
en aura dans `pharos-ops` au module IS2. Le masquage se met en place maintenant, pendant qu'il est
gratuit.

**Huit appels sur la question 1 n'est pas un bug de votre boucle.** C'est presque toujours le
catalogue du LAB 1 qui est ambigu. Ne le corrigez pas aujourd'hui : consignez le chiffre. Le module
SR1 fera mesurer avant/après, et ce chiffre-là sera votre point de départ.

**Ne pas juger la qualité des réponses.** Le lab porte sur la boucle et sa trace. La qualité est
traitée avec une mesure au module SR1, et avec un jeu d'évaluation au module EX2.

---

## Livrable

| | |
|---|---|
| **Produit** | `client/pharos_client/boucle.py` — la boucle instrumentée, avec ses trois arrêts |
| **Consigné** | `labs/lab4/mesures.md` — le relevé de l'étape 5, et le nombre d'appels de la question 1 |
| **Artefact du fil rouge** | **A4**, consommé par OR2, TQ1, DA3, IS2, IS3, SR3 et OR3 |
| **Checkpoint** | `etat/or1-fin` |

```bash
make lab4-verifier
git add client/ labs/lab4/ && git commit -m "LAB 4 — pharos-client"
```

**Suite.** Le module **OR2** reprend la boucle par son point faible : le contexte grossit et rien ne
l'oublie. Trois mémoires à ne pas confondre, et le handle d'état repris exactement là où le module
PR3 l'avait laissé — cette fois pour l'écrire, au LAB 5.
