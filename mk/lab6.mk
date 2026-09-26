lab6-scaffold: ## LAB 6 — recopie les gabarits sans rien écraser
	@$(MAKE) --no-print-directory gabarits LAB=6

lab6-quai: ## LAB 6 — démarre pharos-quai (http://localhost:8105/mcp)
	$(DC) up -d observateur pharos-quai
	@echo "pharos-quai : http://localhost:8105/mcp (poste) — http://observateur:8105/mcp (conteneurs)"

lab6-mesurer: ## LAB 6 — premier appel des cinq questions, trois exécutions (SORTIE=labs/lab6/avant.md)
	@$(DC) run --rm -T atelier python -m outils.mesure_quai $(if $(SORTIE),--sortie $(SORTIE))

lab6-verifier: ## LAB 6 — schémas inchangés, mesures avant/après consignées, progression
	@$(DC) run --rm -T $(if $(SANS_MODELE),-e SANS_MODELE=1) atelier python -m outils.verifier lab6

.PHONY: lab6-scaffold lab6-quai lab6-mesurer lab6-verifier
