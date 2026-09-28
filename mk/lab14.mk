lab14-inscrire: ## LAB 14 — s'inscrit au service de salle : URL=… BINOME=… JETON=… (remis par le formateur)
	@test -n "$(URL)" -a -n "$(BINOME)" -a -n "$(JETON)" || { echo "Préciser URL=, BINOME= et JETON= (voir le formateur)."; exit 1; }
	@PYTHONPATH=src:.:client python3 -m outils.salle inscrire --url "$(URL)" --binome "$(BINOME)" --jeton "$(JETON)"

lab14-deposer: ## LAB 14 — dépose un document piégé chez la cible désignée : FICHIER=attaque.md [CIBLE=n]
	@test -n "$(FICHIER)" || { echo "Préciser FICHIER=… (le Markdown de votre injection)."; exit 1; }
	@PYTHONPATH=src:.:client python3 -m outils.salle deposer --fichier "$(FICHIER)" $(if $(CIBLE),--cible $(CIBLE))

lab14-synchroniser: ## LAB 14 — tire les documents reçus et les écrit en PDF dans contrats-partages/binome-<B>/
	@PYTHONPATH=src:.:client python3 -m outils.salle synchroniser

lab14-executer: ## LAB 14 — pose la question cible à votre agent (vrai modèle) et remonte l'issue : [FOIS=3]
	@$(DC) run --rm -T -e PHAROS_JETON=jeton-rance atelier python -m outils.lab14 executer $(if $(FOIS),--fois $(FOIS))

lab14-tableau: ## LAB 14 — ouvre le tableau de bord de salle (SALLE_URL/tableau)
	@python3 -m outils.salle tableau 2>/dev/null || { . labs/lab14/salle.env 2>/dev/null && $(call ouvrir,$$SALLE_URL/tableau); }

lab14-scaffold: ## LAB 14 — recopie les gabarits (fiches, manches, documents piégés) sans rien écraser
	@$(MAKE) --no-print-directory gabarits LAB=14

lab14-verifier: ## LAB 14 — deux contre-mesures, attaque bloquée, refus journalisés, service intact (base requise)
	@$(DC) run --rm -T $(if $(SANS_MODELE),-e SANS_MODELE=1) atelier python -m outils.verifier lab14

lab14-raz: ## (formateur) Vide dépôts, issues et refus de la salle (jetons et manche conservés)
	@PYTHONPATH=src:.:client python3 -m outils.salle raz --url http://localhost:8300

.PHONY: lab14-inscrire lab14-deposer lab14-synchroniser lab14-executer lab14-tableau lab14-scaffold lab14-verifier lab14-raz
