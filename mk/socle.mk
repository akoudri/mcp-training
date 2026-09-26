SERVICES_SOCLE :=

ouvrir = { command -v wslview >/dev/null && wslview $(1); } || { command -v xdg-open >/dev/null && xdg-open $(1) >/dev/null 2>&1; } || true

up: ## Démarre le socle (observateur, client)
	$(DC) up -d observateur $(SERVICES_SOCLE)
	@echo "Observateur : http://localhost:7001 (mot de passe : pharos)"

down: ## Arrête tout
	$(DC) --profile outils down

logs: ## Journaux (S=service pour un seul)
	$(DC) logs -f --tail=100 $(S)

test: ## Tests du kit, dans le conteneur
	$(DC) run --rm atelier pytest -q

fixtures: ## Régénère les PDF du corpus
	$(DC) run --rm atelier python -m donnees.generer

inspector: ## Ouvre l'Inspector (observateur du trafic MCP)
	@echo "Inspector (observateur de trafic) : http://localhost:7001 — mot de passe : pharos"
	@$(call ouvrir,http://localhost:7001)

.PHONY: up down logs test fixtures inspector

construire: ## Construit l'image Python du kit
	docker build -t pharos/python:1 -f images/python/Dockerfile .
.PHONY: construire

client: ## Ouvre VS Code sur le dépôt (client graphique)
	@command -v code >/dev/null || { echo "VS Code (commande code) introuvable : voir PREPARATION.md"; exit 1; }
	code .
.PHONY: client

inspector-client: ## Démarre l'Inspector officiel (appels manuels)
	$(DC) --profile outils up -d inspector
	@echo "Inspector officiel : http://localhost:7002 — URL du serveur : http://observateur:8100/mcp (transport Streamable HTTP)"
	@$(call ouvrir,http://localhost:7002)

.PHONY: inspector-client

doctor: ## Vérifie l'environnement : trois lignes OK attendues
	@docker info >/dev/null 2>&1 || { echo "  socle     ÉCHEC  Docker ne répond pas : démarrer le service Docker (sudo service docker start sous WSL)."; exit 1; }
	@$(DC) run --rm -T atelier python -m outils.doctor $(if $(SANS_MODELE),--sans-modele)

.PHONY: doctor
