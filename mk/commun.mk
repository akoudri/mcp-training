appeler: ## Appelle un outil : REV=2026-07-28|2025-11-25 URL=… OUTIL=… ARGS='{…}'
	@$(DC) run --rm -T atelier python -m outils.client_test --rev $(or $(REV),2026-07-28) $(or $(URL),http://observateur:8101/mcp) $(OUTIL) '$(or $(ARGS),{})'

essayer: ## (kit) Essaie l'état d'un lab dans Docker, comme la CI : make essayer LAB=N
	@test -n "$(LAB)" || { echo "Préciser le lab : make essayer LAB=1"; exit 1; }
	@python3 -m outils.essayer $(LAB)

.PHONY: appeler essayer
