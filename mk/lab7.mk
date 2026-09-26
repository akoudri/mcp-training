lab7-scaffold: ## LAB 7 — recopie les gabarits sans rien écraser
	@$(MAKE) --no-print-directory gabarits LAB=7

lab7-fixtures: fixtures ## LAB 7 — documents (le contrat de 80 pages est CM-0409, versionné)

lab7-tests: ## LAB 7 — suite de pharos-docs en mémoire, sans modèle (CHRONO=1 : durée)
	@test -d tests/pharos_docs || { echo "tests/pharos_docs absent : lancer d'abord « make depart LAB=7 »."; exit 1; }
	@$(DC) run --rm -T -e OPENROUTER_API_KEY= atelier $(if $(CHRONO),python -m outils.chrono) python -m pytest tests/pharos_docs -q -p no:cacheprovider

lab7-empreinte: ## LAB 7 — (ré)écrit tests/empreinte_catalogue.json depuis le catalogue actuel
	@$(DC) run --rm -T atelier python -m outils.empreinte

lab7-verifier: ## LAB 7 — ressources, prompt, empreinte, suite sous dix secondes
	@$(DC) run --rm -T $(if $(SANS_MODELE),-e SANS_MODELE=1) atelier python -m outils.verifier lab7

.PHONY: lab7-scaffold lab7-fixtures lab7-tests lab7-empreinte lab7-verifier
