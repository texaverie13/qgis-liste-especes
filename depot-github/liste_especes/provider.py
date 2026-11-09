# -*- coding: utf-8 -*-
"""Le fournisseur Processing de l'extension — un seul algorithme pour l'instant.

Copyright (C) 2026 Valérie Texier — GPL v2 ou ultérieure, voir LICENSE.
"""
import os

from qgis.core import QgsProcessingProvider
from qgis.PyQt.QtGui import QIcon

from .algorithme import ExtraireEspeces


class FournisseurListeEspeces(QgsProcessingProvider):
    """Le groupe « Liste d'espèces » dans la boîte à outils de traitement."""

    def loadAlgorithms(self):
        self.addAlgorithm(ExtraireEspeces())

    def id(self):
        return "liste_especes"

    def name(self):
        return "Liste d'espèces"

    def longName(self):
        return "Liste d'espèces — données naturalistes"

    def icon(self):
        chemin = os.path.join(os.path.dirname(__file__), "icon.png")
        return QIcon(chemin) if os.path.isfile(chemin) else QgsProcessingProvider.icon(self)
