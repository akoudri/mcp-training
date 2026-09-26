depart: ## Commence un lab : make depart LAB=N (branche du binôme + gabarits)
	@test -n "$(LAB)" || { echo "Préciser le lab : make depart LAB=1"; exit 1; }
	@python3 -m outils.depart $(LAB)

gabarits: ## Recopie les gabarits d'un lab sans rien écraser : make gabarits LAB=N
	@test -n "$(LAB)" || { echo "Préciser le lab : make gabarits LAB=1"; exit 1; }
	@python3 -m outils.depart --gabarits-seulement $(LAB)

construire-etats: ## (formateur) Assemble les branches etat/* ; POUSSER=1 pour les pousser
	@python3 -m outils.construire_etats $(if $(POUSSER),--pousser)

.PHONY: depart gabarits construire-etats
