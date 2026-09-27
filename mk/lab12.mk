lab12-canal: ## LAB 12 — démarre les mocks s'il le faut et remet le canal d'alertes à zéro
	$(DC) up -d --wait mocks
	@$(DC) run --rm -T atelier python -m outils.lab12 canal

lab12-compteur: ## LAB 12 — alertes réellement parties, par destinataire : la seule vérité du lab
	@$(DC) run --rm -T atelier python -m outils.lab12 compteur

lab12-clients: ## LAB 12 — appelle publier_alerte avec un client de test (pharos-ops, 8103) : [SANS_ELICITATION=1] [DEFAUT=1] [URL=http://observateur:8203/mcp]
	@$(DC) run --rm -T atelier python -m outils.lab12 clients $(if $(SANS_ELICITATION),--sans-elicitation) $(if $(DEFAUT),--defaut) $(if $(URL),--url $(URL))

lab12-scaffold: ## LAB 12 — recopie les gabarits sans rien écraser
	@$(MAKE) --no-print-directory gabarits LAB=12

lab12-deux-instances: ## LAB 12 — deux instances de pharos-ops derrière un répartiteur (http://localhost:8203/mcp)
	@test -f serveurs/pharos_ops/serveur.py || { echo "serveurs/pharos_ops/serveur.py absent : lancer d'abord « make depart LAB=12 »."; exit 1; }
	$(DC) up -d --wait mocks
	$(DC) up -d observateur pharos-ops-a pharos-ops-b repartiteur-ops
	@echo "Répartiteur : http://localhost:8203/mcp (poste) — http://observateur:8203/mcp (conteneurs) ; X-Pharos-Instance : a ou b"
	@echo "Votre boucle contre les deux instances : make lab4-question URL=http://observateur:8203/mcp PHAROS_JETON=jeton-exploitation QUESTION=\"…\""
	@echo "Les clients de test contre les deux instances : make lab12-clients URL=http://observateur:8203/mcp"

lab12-verifier: ## LAB 12 — aucun chemin sans rejeu, demande conforme, rejeu augmenté, repli, deux instances, refus propres
	@$(DC) run --rm -T $(if $(SANS_MODELE),-e SANS_MODELE=1) atelier python -m outils.verifier lab12

.PHONY: lab12-canal lab12-compteur lab12-clients lab12-scaffold lab12-deux-instances lab12-verifier
