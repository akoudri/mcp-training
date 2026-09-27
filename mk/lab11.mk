lab11-scaffold: ## LAB 11 — recopie les gabarits sans rien écraser, puis (re)démarre pharos-ops [VITESSE=rapide : durées divisées par dix]
	@$(MAKE) --no-print-directory gabarits LAB=11
	@test -f serveurs/pharos_ops/serveur.py || { echo "serveurs/pharos_ops/serveur.py absent : lancer d'abord « make depart LAB=11 »."; exit 1; }
	$(DC) up -d --wait pharos-db mocks
	PHAROS_VITESSE=$(VITESSE) $(DC) up -d --force-recreate observateur pharos-ops
	@echo "pharos-ops : http://localhost:8103/mcp — moteur à vitesse $(or $(VITESSE),réelle) (la vérification finale se fait à vitesse réelle)"

lab11-clients: ## LAB 11 — recalcule jeudi avec un client qui déclare Tasks, ou non : [SANS_TASKS=1] [QUAI=3]
	@$(DC) run --rm -T atelier python -m outils.lab11 clients $(if $(SANS_TASKS),--sans-tasks) $(if $(QUAI),--quai $(QUAI))

lab11-verifier: ## LAB 11 — décision côté serveur, progression réelle, trois issues, plan B, boucle honnête
	@$(DC) run --rm -T $(if $(SANS_MODELE),-e SANS_MODELE=1) atelier python -m outils.verifier lab11

.PHONY: lab11-scaffold lab11-clients lab11-verifier
