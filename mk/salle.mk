salle-demarrer: ## (formateur) Démarre le service de salle sur le réseau (0.0.0.0:8300) [N=5 : tire les jetons]
	@mkdir -p salle
	@test -s salle/cle-admin || python3 -c "import secrets; open('salle/cle-admin','w').write(secrets.token_hex(8))"
	@grep -q "jeton formateur :" salle/jetons.txt 2>/dev/null || echo "jeton formateur : $$(cat salle/cle-admin)" >> salle/jetons.txt
	SALLE_BIND=0.0.0.0 SALLE_CLE_ADMIN=$$(cat salle/cle-admin) $(DC) --profile salle up -d --wait pharos-salle
	@echo "Service de salle : http://$$(hostname -I | awk '{print $$1}'):8300 — tableau : /tableau"
	@test -z "$(N)" || $(MAKE) --no-print-directory salle-jetons N=$(N)

salle-locale: ## (formateur/tests) Démarre le service de salle sur 127.0.0.1:8300 seulement
	@mkdir -p salle
	@test -s salle/cle-admin || python3 -c "import secrets; open('salle/cle-admin','w').write(secrets.token_hex(8))"
	@grep -q "jeton formateur :" salle/jetons.txt 2>/dev/null || echo "jeton formateur : $$(cat salle/cle-admin)" >> salle/jetons.txt
	SALLE_CLE_ADMIN=$$(cat salle/cle-admin) $(DC) --profile salle up -d --wait pharos-salle
	@echo "Service de salle (local) : http://localhost:8300 — tableau : /tableau"

salle-jetons: ## (formateur) Tire un jeton par binôme (N=5), écrit dans salle/jetons.txt (à distribuer sur papier)
	@test -n "$(N)" || { echo "Préciser N= (nombre de binômes)."; exit 1; }
	@$(DC) run --rm -T atelier python -m outils.salle jetons --n $(N) --url http://pharos-salle:8300

salle-manche: ## (formateur) Passe à la manche M=1|2|3 (anneau : m1 b→b+1, m2 dépôt fermé, m3 b→b+2)
	@test -n "$(M)" || { echo "Préciser M=1, 2 ou 3."; exit 1; }
	@$(DC) run --rm -T atelier python -m outils.salle manche --manche $(M) --url http://pharos-salle:8300

.PHONY: salle-demarrer salle-locale salle-jetons salle-manche
