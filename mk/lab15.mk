lab15-scaffold: ## LAB 15 — recopie les gabarits (cas, rapport, référence, chaînes) sans rien écraser
	@$(MAKE) --no-print-directory gabarits LAB=15

lab15-exemple: ## LAB 15 — un cas complet, commenté, dans le format attendu
	@test -f evaluation/exemples/penalites-vent-autan.yaml || { echo "Exemple absent : make lab15-scaffold."; exit 1; }
	@cat evaluation/exemples/penalites-vent-autan.yaml
	@echo; echo "Cas de sécurité de secours : evaluation/exemples/cas_securite.yaml — contexte à figer : make lab15-empreinte."

lab15-empreinte: ## LAB 15 — date, identités, empreinte de la base ; empreintes du catalogue, du prompt et du modèle
	@$(DC) run --rm -T atelier python -m outils.evaluation empreinte

lab15-lancer: ## LAB 15 — le jeu, vrai modèle : [CAS=id1,id2] [FOIS=3] → sortie/lab15/<horodatage>.json
	@$(DC) run --rm -T $(if $(SANS_MODELE),-e SANS_MODELE=1) atelier python -m outils.evaluation lancer $(if $(CAS),--cas $(CAS)) --fois $(or $(FOIS),3)

lab15-rapport: ## LAB 15 — votre rapport : tableau, taux par famille, comparaison à la référence [RESULTAT=…]
	@$(DC) run --rm -T atelier python evaluation/rapport.py $(RESULTAT)

lab15-referencer: ## LAB 15 — fige le dernier résultat (ou RESULTAT=…) comme référence : evaluation/reference.json
	@$(DC) run --rm -T atelier python -m outils.evaluation referencer $(if $(RESULTAT),--resultat $(RESULTAT))

lab15-regression: ## LAB 15 — injecte la régression (un outil renommé, description intacte) et relance pharos-ops
	@python3 -m outils.evaluation.regression
	@$(DC) restart pharos-ops >/dev/null && echo "pharos-ops relancé."

lab15-regression-retirer: ## LAB 15 — retire la régression et relance pharos-ops
	@python3 -m outils.evaluation.regression --retirer
	@$(DC) restart pharos-ops >/dev/null && echo "pharos-ops relancé."

lab15-chaine: ## LAB 15 — la chaîne : rien à lancer si aucun déclencheur n'a bougé, sinon jeu + rapport [PUBLICATION=1]
	@$(DC) run --rm -T atelier python -m outils.evaluation chaine $(if $(filter 1,$(PUBLICATION)),--publication)

lab15-verifier: ## LAB 15 — dix cas, référence, cas instable, chaîne séparée, rien à lancer, rapport décisif
	@$(DC) run --rm -T $(if $(SANS_MODELE),-e SANS_MODELE=1) atelier python -m outils.verifier lab15

.PHONY: lab15-scaffold lab15-exemple lab15-empreinte lab15-lancer lab15-rapport lab15-referencer lab15-regression lab15-regression-retirer lab15-chaine lab15-verifier
