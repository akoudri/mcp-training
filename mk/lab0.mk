lab0-up: ## LAB 0 — démarre pharos-docs-demo (VERBEUX=1 pour le journal brut)
	VERBEUX=$(or $(VERBEUX),0) PHAROS_OUTIL_JUMEAU=0 $(DC) up -d --force-recreate pharos-docs-demo
	@echo "pharos-docs-demo : http://observateur:8100/mcp (depuis le client), http://localhost:8100/mcp (depuis le poste)"
	@echo "Brancher le client :  mkdir -p .vscode && cp labs/lab0/client.config.json .vscode/mcp.json"
	@echo "Puis, dans VS Code : palette > « MCP: List Servers » > pharos-docs-demo > Start (ou Restart)."

lab0-outil-jumeau: ## LAB 0 — extension B : active l'outil jumeau
	VERBEUX=$(or $(VERBEUX),0) PHAROS_OUTIL_JUMEAU=1 $(DC) up -d --force-recreate pharos-docs-demo
	@echo "Outil jumeau actif. Dans VS Code : palette > « MCP: List Servers » > pharos-docs-demo > Restart."

tokens-catalogue: ## Coût en tokens du catalogue d'un serveur (SERVEUR=url, défaut pharos-docs-demo)
	@$(DC) run --rm -T atelier python -m outils.tokens_catalogue $(or $(SERVEUR),http://observateur:8100/mcp)

.PHONY: lab0-up lab0-outil-jumeau tokens-catalogue
