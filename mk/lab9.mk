lab9-identites: ## LAB 9 — les trois identités de salle (exploitation, agents Rance et Iroise) et leurs navires
	@$(DC) run --rm -T atelier python -m outils.lab9 identites

lab9-scaffold: ## LAB 9 — recopie les gabarits sans rien écraser
	@$(MAKE) --no-print-directory gabarits LAB=9

lab9-politique: ## LAB 9 — applique labs/lab9/politique.sql (sous le propriétaire des tables)
	@$(DC) run --rm -T atelier python -m donnees.base --politique

lab9-contourner: ## LAB 9 — envoie le contournement N (1, 2 ou 3) à requete_sql : N=1 [PHAROS_JETON=jeton-rance]
	@test -n "$(N)" || { echo "Préciser le contournement : make lab9-contourner N=1 (1, 2 ou 3)"; exit 1; }
	@$(DC) run --rm -T $(if $(PHAROS_JETON),-e PHAROS_JETON=$(PHAROS_JETON)) atelier python -m outils.lab9 contourner $(N)

lab9-tests: ## LAB 9 — suite de pharos-data, sans modèle, contre pharos-db (CHRONO=1 : durée)
	@test -d tests/pharos_data || { echo "tests/pharos_data absent : lancer d'abord « make depart LAB=9 »."; exit 1; }
	@$(DC) run --rm -T -e OPENROUTER_API_KEY= atelier $(if $(CHRONO),python -m outils.chrono) python -m pytest tests/pharos_data -q -p no:cacheprovider

lab9-verifier: ## LAB 9 — outils métier, cloisonnement dans la base, contournements, test automatisé
	@$(DC) run --rm -T $(if $(SANS_MODELE),-e SANS_MODELE=1) atelier python -m outils.verifier lab9

.PHONY: lab9-identites lab9-scaffold lab9-politique lab9-contourner lab9-tests lab9-verifier
