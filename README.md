# pharos-labs

Kit des labs de la formation « Créer des agents IA avec MCP » (fil rouge PHAROS).

Démarrage : suivre `PREPARATION.md`, puis `make up`, `make lab0-up`, `make doctor`.
Chaque lab commence par `make depart LAB=N` : une branche `binome-<B>-labNN` est créée depuis le
checkpoint précédent (`etat/<module>-fin`), et les gabarits du lab sont copiés sans rien écraser.
Chaque lab se termine par `make labN-verifier`, puis un commit. Les briefs sont dans le dépôt de la formation.
