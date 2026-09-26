lab1-up: ## LAB 1 — démarre pharos-docs (http://localhost:8101/mcp)
	@test -f serveurs/pharos_docs/serveur.py || { echo "serveurs/pharos_docs/serveur.py absent : lancer d'abord « make depart LAB=1 »."; exit 1; }
	$(DC) up -d observateur pharos-docs
	@echo "pharos-docs : http://localhost:8101/mcp (poste) — http://observateur:8101/mcp (conteneurs)"
	@echo "Brancher VS Code :  mkdir -p .vscode && cp labs/lab1/client.config.json .vscode/mcp.json"

lab1-scaffold: ## LAB 1 — recopie les gabarits sans rien écraser
	@$(MAKE) --no-print-directory gabarits LAB=1

lab1-fixtures: fixtures ## LAB 1 — documents d'escale (alias de make fixtures)

lab1-verifier: ## LAB 1 — contrôle les critères et relève le premier appel des cinq questions
	@$(DC) run --rm -T $(if $(SANS_MODELE),-e SANS_MODELE=1) atelier python -m outils.verifier lab1

.PHONY: lab1-up lab1-scaffold lab1-fixtures lab1-verifier
