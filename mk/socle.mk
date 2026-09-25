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
