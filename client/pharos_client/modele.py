"""Adaptateur de modèle — fourni : UN appel au modèle, avec outils. La boucle, c'est vous.

Appeler par l'attribut du module (modele.completer(...)), pas par un import direct de la fonction :
le vérificateur remplace le modèle par un modèle simulé à cet endroit.
"""

from pharos.openrouter import Appel, ErreurModele, Reponse, completer, estimer_tokens

__all__ = ["Appel", "ErreurModele", "Reponse", "completer", "estimer_tokens"]
