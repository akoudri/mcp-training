lab13-tout: ## LAB 13 — démarre la base, les mocks et les trois serveurs (8101, 8102, 8103)
	@for f in serveurs/pharos_docs/serveur.py serveurs/pharos_data/serveur.py serveurs/pharos_ops/serveur.py; do test -f $$f || { echo "$$f absent : lancer d'abord « make depart LAB=13 »."; exit 1; }; done
	$(DC) up -d --wait pharos-db mocks
	$(DC) up -d observateur pharos-docs pharos-data pharos-ops
	@echo "pharos-docs : http://localhost:8101/mcp — pharos-data : http://localhost:8102/mcp — pharos-ops : http://localhost:8103/mcp"
	@echo "Base vide, ou rechargée après le LAB 9 ? make lab8-base (réapplique labs/lab9/politique.sql)."
	@echo "Brancher VS Code (vue du plan de quai) :  mkdir -p .vscode && cp labs/lab13/client.config.json .vscode/mcp.json"

lab13-scaffold: ## LAB 13 — recopie les gabarits sans rien écraser
	@$(MAKE) --no-print-directory gabarits LAB=13

lab13-catalogue: ## LAB 13 — coût fixe du catalogue, par serveur et agrégé ; nombre d'outils ; collisions de noms
	@$(DC) run --rm -T atelier python -m outils.lab13 catalogue

lab13-question: ## LAB 13 — pose une question à votre agent, trois serveurs, vrai modèle : [Q=1|2|3] ou QUESTION="…"
	@$(DC) run --rm -T -e PHAROS_JETON=$(or $(PHAROS_JETON),jeton-exploitation) atelier python -m outils.lab13 question --q "$(or $(Q),1)" $(if $(QUESTION),--question "$(QUESTION)")

lab13-verifier-note: ## LAB 13 — chaque chiffre, date et nom de la dernière note : son origine dans la trace
	@$(DC) run --rm -T atelier python -m outils.lab13 note

lab13-derive: ## LAB 13 — les trois signaux de dérive de la dernière exécution (plan et trace)
	@$(DC) run --rm -T atelier python -m outils.lab13 derive

lab13-banc: ## LAB 13 (extension B) — premier appel sur le catalogue agrégé, trois exécutions par question
	@$(DC) run --rm -T $(if $(SANS_MODELE),-e SANS_MODELE=1) atelier python -m outils.lab13 banc

lab13-verifier: ## LAB 13 — noms, collisions, serveur dans la trace, plan avant action, confirmation, texte sans extension, signaux
	@$(DC) run --rm -T $(if $(SANS_MODELE),-e SANS_MODELE=1) atelier python -m outils.verifier lab13

.PHONY: lab13-tout lab13-scaffold lab13-catalogue lab13-question lab13-verifier-note lab13-derive lab13-banc lab13-verifier
