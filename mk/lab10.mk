Q_LAB10 := L'escale du Vent d'Autan de jeudi présente-t-elle un risque ?

lab10-mocks: ## LAB 10 — démarre les mocks et règle leurs interrupteurs, à chaud : [PANNE=meteo] [LENTEUR=8s] [LENTEUR_QUAIS=5,7] [QUOTA=5]
	$(DC) up -d --wait mocks
	@$(DC) run --rm -T atelier python -m outils.lab10 mocks $(if $(PANNE),--panne $(PANNE)) $(if $(LENTEUR),--lenteur $(LENTEUR)) $(if $(LENTEUR_QUAIS),--lenteur-quais $(LENTEUR_QUAIS)) $(if $(QUOTA),--quota $(QUOTA))

lab10-appels: ## LAB 10 — combien d'appels les mocks ont réellement reçus, par route (extension B)
	@$(DC) run --rm -T atelier python -m outils.lab10 appels

lab10-scaffold: ## LAB 10 — recopie les gabarits sans rien écraser
	@$(MAKE) --no-print-directory gabarits LAB=10

lab10-up: ## LAB 10 — démarre pharos-ops (http://localhost:8103/mcp), et les mocks s'ils ne tournent pas
	@test -f serveurs/pharos_ops/serveur.py || { echo "serveurs/pharos_ops/serveur.py absent : lancer d'abord « make depart LAB=10 »."; exit 1; }
	$(DC) up -d --wait mocks
	$(DC) up -d observateur pharos-ops
	@echo "pharos-ops : http://localhost:8103/mcp (poste) — http://observateur:8103/mcp (conteneurs) ; identité : PHAROS_JETON"

lab10-question: ## LAB 10 — pose une question à votre boucle, contre pharos-ops (défaut : le Vent d'Autan ; PHAROS_JETON=jeton-exploitation)
	@$(MAKE) --no-print-directory lab4-question URL=http://observateur:8103/mcp PHAROS_JETON=$(or $(PHAROS_JETON),jeton-exploitation) QUESTION="$(or $(QUESTION),$(Q_LAB10))"

lab10-note-panne: ## LAB 10 — critère décisif : météo en panne, votre boucle et le vrai modèle → labs/lab10/note-panne.md
	@test -f serveurs/pharos_ops/serveur.py || { echo "serveurs/pharos_ops/serveur.py absent : lancer d'abord « make depart LAB=10 »."; exit 1; }
	@$(DC) run --rm -T -e PHAROS_JETON=$(or $(PHAROS_JETON),jeton-exploitation) atelier python -m outils.lab10 note-panne

lab10-verifier: ## LAB 10 — trois outils, clé invisible, normalisation, plafond, réponse partielle, note en panne
	@$(DC) run --rm -T $(if $(SANS_MODELE),-e SANS_MODELE=1) atelier python -m outils.verifier lab10

.PHONY: lab10-mocks lab10-appels lab10-scaffold lab10-up lab10-question lab10-note-panne lab10-verifier
