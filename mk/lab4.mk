lab4-scaffold: ## LAB 4 — recopie les gabarits sans rien écraser
	@$(MAKE) --no-print-directory gabarits LAB=4

lab4-docs: ## LAB 4 — démarre pharos-docs (celui du checkpoint)
	@$(MAKE) --no-print-directory lab1-up

lab4-question: ## LAB 4 — pose une question à votre boucle : Q=1|2|3 ou QUESTION="…" [URL=…] [PHAROS_JETON=…]
	@test -f client/pharos_client/boucle.py || { echo "client/pharos_client/boucle.py absent : lancer d'abord « make depart LAB=4 »."; exit 1; }
	@$(DC) run --rm -T $(if $(URL),-e PHAROS_URL=$(URL)) $(if $(PHAROS_JETON),-e PHAROS_JETON=$(PHAROS_JETON)) atelier python -m pharos_client $(if $(QUESTION),"$(QUESTION)",$(or $(Q),1))

lab4-verifier: ## LAB 4 — contrôle la boucle (modèle simulé), puis les questions 1 et 3 (vrai modèle)
	@$(DC) run --rm -T $(if $(SANS_MODELE),-e SANS_MODELE=1) atelier python -m outils.verifier lab4

.PHONY: lab4-scaffold lab4-docs lab4-question lab4-verifier
