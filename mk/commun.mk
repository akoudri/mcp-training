appeler: ## Appelle un outil : REV=2026-07-28|2025-11-25 URL=… OUTIL=… ARGS='{…}'
	@$(DC) run --rm -T atelier python -m outils.client_test --rev $(or $(REV),2026-07-28) $(or $(URL),http://observateur:8101/mcp) $(OUTIL) '$(or $(ARGS),{})'

.PHONY: appeler
