Q_LAB8_reference := Combien de conteneurs réfrigérés sont passés quai 3 la semaine dernière ?
Q_LAB8_plafond := Liste tous les mouvements de conteneurs du mois dernier.

lab8-base: ## LAB 8 — démarre pharos-db et (re)charge la base PHAROS (réapplique labs/lab9/politique.sql s'il existe)
	$(DC) up -d --wait pharos-db
	@$(DC) run --rm -T atelier python -m donnees.base

lab8-scaffold: ## LAB 8 — recopie les gabarits sans rien écraser
	@$(MAKE) --no-print-directory gabarits LAB=8

lab8-up: ## LAB 8 — démarre pharos-data (http://localhost:8102/mcp)
	@test -f serveurs/pharos_data/serveur.py || { echo "serveurs/pharos_data/serveur.py absent : lancer d'abord « make depart LAB=8 »."; exit 1; }
	$(DC) up -d --wait pharos-db
	$(DC) up -d observateur pharos-data
	@echo "pharos-data : http://localhost:8102/mcp (poste) — http://observateur:8102/mcp (conteneurs)"

lab8-question: ## LAB 8 — pose une question à votre boucle, contre pharos-data : Q=reference|plafond ou QUESTION="…"
	@$(MAKE) --no-print-directory lab4-question URL=http://observateur:8102/mcp QUESTION="$(or $(QUESTION),$(Q_LAB8_$(or $(Q),reference)))"

lab8-verite: ## LAB 8 — la réponse exacte à la question de référence, calculée contre la base
	@$(DC) run --rm -T atelier python -m outils.verite_lab8

lab8-tests: ## LAB 8 (extension C) — suite de pharos-data en mémoire, sans modèle (CHRONO=1 : durée)
	@test -d tests/pharos_data || { echo "tests/pharos_data absent : écrire d'abord votre suite (extension C)."; exit 1; }
	@$(DC) run --rm -T -e OPENROUTER_API_KEY= atelier $(if $(CHRONO),python -m outils.chrono) python -m pytest tests/pharos_data -q -p no:cacheprovider

lab8-banc: ## LAB 8 (extension A) — « quai 5 hier », trois exécutions du premier appel : la valeur de sens passée [SORTIE=…]
	@$(DC) run --rm -T $(if $(SANS_MODELE),-e SANS_MODELE=1) atelier python -m outils.banc http://observateur:8102/mcp --questions outils/questions/lab8.yaml --executions 3 $(if $(SORTIE),--sortie $(SORTIE))

lab8-verifier: ## LAB 8 — pool, schéma en ressource, réponse exacte, plafond, requête lisible
	@$(DC) run --rm -T $(if $(SANS_MODELE),-e SANS_MODELE=1) atelier python -m outils.verifier lab8

.PHONY: lab8-base lab8-scaffold lab8-up lab8-question lab8-verite lab8-tests lab8-banc lab8-verifier
