lab3-clients: ## LAB 3 — joue le scénario avec les deux clients de test (2025-11-25 et 2026-07-28) contre pharos-legacy
	$(DC) up -d observateur pharos-legacy
	@$(DC) run --rm -T atelier python -m outils.scenario_legacy http://observateur:8104/mcp

lab3-scaffold: ## LAB 3 — recopie les gabarits sans rien écraser
	@$(MAKE) --no-print-directory gabarits LAB=3

lab3-deux-instances: ## LAB 3 — deux instances derrière le répartiteur, AVEC affinité de session (http://localhost:8204/mcp)
	AFFINITE_LEGACY=1 $(DC) up -d observateur pharos-legacy-a pharos-legacy-b repartiteur-legacy
	@echo "Répartiteur (affinité de session) : http://localhost:8204/mcp (poste) — http://observateur:8204/mcp (conteneurs)"
	@echo "Les requêtes d'une session 2025-11-25 reviennent à l'instance qui l'a ouverte ; les autres alternent."

lab3-verifier: ## LAB 3 — contrôle les deux révisions, derrière le répartiteur avec affinité
	@$(DC) run --rm -T atelier python -m outils.verifier lab3

lab3-cout-surensemble: ## LAB 3, extension C — tokens des deux formes de résultat
	@$(DC) run --rm -T atelier python -m outils.cout_surensemble http://observateur:8204/mcp

.PHONY: lab3-clients lab3-scaffold lab3-deux-instances lab3-verifier lab3-cout-surensemble
