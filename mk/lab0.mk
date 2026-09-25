lab0-up: ## LAB 0 — démarre pharos-docs-demo (VERBEUX=1 pour le journal brut)
	VERBEUX=$(or $(VERBEUX),0) PHAROS_OUTIL_JUMEAU=0 $(DC) up -d --force-recreate pharos-docs-demo
	@echo "pharos-docs-demo : http://observateur:8100/mcp (depuis le client), http://localhost:8100/mcp (depuis le poste)"
	@echo "Brancher le client :  cp labs/lab0/client.config.json config/mcpjam/ && make client-redemarrer"

lab0-outil-jumeau: ## LAB 0 — extension B : active l'outil jumeau
	VERBEUX=$(or $(VERBEUX),0) PHAROS_OUTIL_JUMEAU=1 $(DC) up -d --force-recreate pharos-docs-demo
	@echo "Outil jumeau actif. Redémarrer le client : make client-redemarrer"

.PHONY: lab0-up lab0-outil-jumeau
