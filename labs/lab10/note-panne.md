# LAB 10 — note produite en mode panne

Produite par `make lab10-note-panne` : météo en panne (503), votre boucle du LAB 4, le vrai modèle, contre pharos-ops. Relue par `make lab10-verifier` (critère décisif), sans rappeler le modèle.

Question : L'escale du Vent d'Autan de jeudi présente-t-elle un risque ?

## Note de l'agent

L'escale du navire **Vent d'Autan** prévue ce **jeudi 8 octobre 2026** présente les caractéristiques suivantes :

* **Navire :** Vent d'Autan (IMO 9412884, L : 225 m, TE : 13,2 m, Pavillon : Bahamas)
* **ID Escale :** ESC-2026-0412
* **Quai d'accostage :** Quai 3
* **Créneau :** De 06h00 à 20h00 (heure de Paris)

**Évaluation du risque météo :**
Le service météo marine est actuellement **indisponible** (erreur 503). En conséquence, le risque météo pour cette escale (vent, rafales, houle, visibilité) **ne peut pas être évalué** pour le moment.

## Trace

| Tour | Outil | Arguments | Erreur | Résultat (début) |
|---|---|---|---|---|
| 1 | navire_par_nom | {'nom': "Vent d'Autan"} | non | {"navires":[{"navire_id":"NAV-0007","nom":"Vent d'Autan","imo":"9412884","longueur_m":225.0,"tirant_eau_max_m":13.2,"pavillon":"BS","escales":[{"escale_id":"ESC… |
| 2 | meteo_creneau | {'debut': '2026-10-08T06:00:00+02:00', 'fin': '2026-10-08T20:00:00+02:00', 'quai… | oui | Le service météo marine est indisponible (service en panne, HTTP 503). Les données des navires et de leurs escales restent accessibles (navire_par_nom), comme c… |
| 3 | meteo_alerte | {'horizon_h': 72, 'quai': 3} | oui | Le service météo marine est indisponible (service en panne, HTTP 503). Les données des navires et de leurs escales restent accessibles (navire_par_nom), comme c… |
