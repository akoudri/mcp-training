"""Définition d'exploitation d'une escale « à risque » (bloc 14.1) — version 2.0, retenue pour le LAB 9.

Fournie : c'est une décision d'exploitation, pas un choix de code. escales_a_risque l'applique et rend,
pour chaque escale à risque, les critères déclenchés et leur détail chiffré — jamais un simple booléen :

    {"date": "2026-10-08", "definition_version": "2.0",
     "escales": [{"escale_id": "ESC-2026-0412", "navire": "Vent d'Autan", "quai": 3, "debut": "…", "fin": "…",
                  "criteres": [{"critere": "tirant_eau",
                                "detail": {"tirant_eau_m": 12.9, "quai_max_m": 13.5, "marge_m": 1.0}},
                               {"critere": "conflit_creneau",
                                "detail": {"escale_id": "ESC-2026-0413", "chevauchement_min": 60}}]}]}

Versions réservées : 2.1 = ajout de retard_cumule (extension C) ; 3.0 = branchement de meteo au LAB 13.
"""

DEFINITION_VERSION = "2.0"
MARGE_TIRANT_EAU_M = 1.0          # tirant_eau : tirant d'eau de l'escale > tirant d'eau max du quai − marge
CRITERES = ("tirant_eau", "conflit_creneau", "meteo", "retard_cumule")
CRITERES_EVALUES = ("tirant_eau", "conflit_creneau")   # la météo arrive avec pharos-ops (IS2), branchée au LAB 13
