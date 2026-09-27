"""python -m donnees.referentiel — réécrit donnees/referentiel/navires.yaml depuis la base générée."""

from donnees.referentiel import generer

generer.FICHIER.write_text(generer.rendre(), encoding="utf-8")
print(f"{generer.FICHIER.name} : {len(generer.navires())} navires")
