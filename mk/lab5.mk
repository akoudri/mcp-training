lab5-scaffold: ## LAB 5 — recopie les gabarits sans rien écraser
	@$(MAKE) --no-print-directory gabarits LAB=5

lab5-deux-instances: ## LAB 5 — deux instances de pharos-docs derrière un répartiteur (http://localhost:8201/mcp)
	@test -f serveurs/pharos_docs/serveur.py || { echo "serveurs/pharos_docs/serveur.py absent : lancer d'abord « make depart LAB=5 »."; exit 1; }
	$(DC) up -d observateur pharos-docs-a pharos-docs-b repartiteur-docs
	@echo "Répartiteur : http://localhost:8201/mcp (poste) — http://observateur:8201/mcp (conteneurs)"
	@echo "L'en-tête X-Pharos-Instance (a ou b) est visible dans l'Inspector : http://localhost:7001"

lab5-verifier: ## LAB 5 — contrôle les handles, les trois refus et le test des deux instances
	@$(DC) run --rm -T $(if $(SANS_MODELE),-e SANS_MODELE=1) atelier python -m outils.verifier lab5

.PHONY: lab5-scaffold lab5-deux-instances lab5-verifier
