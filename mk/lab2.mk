lab2-legacy: ## LAB 2 — démarre pharos-legacy tel quel, en 2025-11-25 (http://localhost:8104/mcp)
	$(DC) up -d observateur pharos-legacy
	@echo "pharos-legacy : http://localhost:8104/mcp (poste) — http://observateur:8104/mcp (conteneurs)"
	@echo "Client 2025-11-25 : VS Code (mkdir -p .vscode && cp labs/lab2/client.config.json .vscode/mcp.json), ou"
	@echo "  make appeler REV=2025-11-25 URL=http://observateur:8104/mcp OUTIL=etat_escale ARGS='{\"escale_id\": \"ESC-2026-0412\"}'"
	@echo "Trafic : Inspector, http://localhost:7001 (mot de passe pharos)"

lab2-fixtures: fixtures ## LAB 2 — documents d'escale (alias de make fixtures)

lab2-deux-instances: ## LAB 2 — deux instances de pharos-legacy derrière un répartiteur, sans affinité (http://localhost:8204/mcp)
	AFFINITE_LEGACY=0 $(DC) up -d observateur pharos-legacy-a pharos-legacy-b repartiteur-legacy
	@echo "Répartiteur (sans affinité) : http://localhost:8204/mcp (poste) — http://observateur:8204/mcp (conteneurs)"
	@echo "L'en-tête X-Pharos-Instance (a ou b) est visible dans l'Inspector : http://localhost:7001"

lab2-verifier: ## LAB 2 — contrôle la migration, à travers le répartiteur à deux instances
	@$(DC) run --rm -T atelier python -m outils.verifier lab2

lab2-taille-requetes: ## LAB 2, extension B — taille des requêtes avant et après, sur dix tours
	@$(DC) run --rm -T atelier python -m outils.taille_requetes

.PHONY: lab2-legacy lab2-fixtures lab2-deux-instances lab2-verifier lab2-taille-requetes
