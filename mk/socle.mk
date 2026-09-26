SERVICES_SOCLE := mcpjam

ouvrir = { command -v wslview >/dev/null && wslview $(1); } || { command -v xdg-open >/dev/null && xdg-open $(1) >/dev/null 2>&1; } || true

up: ## Démarre le socle (observateur, client)
	@mkdir -p config/mcpjam && test -f config/mcpjam/client.config.json || echo '{"mcpServers": {}}' > config/mcpjam/client.config.json
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

client: ## Ouvre le client graphique MCPJam
	@mkdir -p config/mcpjam
	@test -f config/mcpjam/client.config.json || echo '{"mcpServers": {}}' > config/mcpjam/client.config.json
	$(DC) up -d mcpjam
	@echo "Client graphique : http://localhost:7000"
	@$(call ouvrir,http://localhost:7000)

client-redemarrer: ## Redémarre le client (après changement de configuration)
	$(DC) restart mcpjam

.PHONY: client client-redemarrer

inspector-client: ## Démarre l'Inspector officiel (appels manuels)
	$(DC) --profile outils up -d inspector
	@echo "Inspector officiel : http://localhost:7002 — URL du serveur : http://observateur:8100/mcp (transport Streamable HTTP)"
	@$(call ouvrir,http://localhost:7002)

.PHONY: inspector-client
