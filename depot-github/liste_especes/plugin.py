# -*- coding: utf-8 -*-
"""Point d'entrée de l'extension.

L'extension n'ajoute NI menu NI barre d'outils : elle déclare un fournisseur
Processing, et rien d'autre. metadata.txt porte « hasProcessingProvider=yes »,
donc QGIS appelle initProcessing() au chargement de la boîte à outils, sans
attendre l'interface — l'algorithme est ainsi disponible aussi en mode console
et dans un modèle de traitement.

Copyright (C) 2026 Valérie Texier — GPL v2 ou ultérieure, voir LICENSE.
"""
from qgis.core import QgsApplication

from .provider import FournisseurListeEspeces


class ListeEspecesPlugin:
    def __init__(self):
        self.fournisseur = None

    def initProcessing(self):              # noqa: N802 — nom imposé par QGIS
        self.fournisseur = FournisseurListeEspeces()
        QgsApplication.processingRegistry().addProvider(self.fournisseur)

    def initGui(self):                     # noqa: N802 — nom imposé par QGIS
        self.initProcessing()

    def unload(self):
        if self.fournisseur is not None:
            QgsApplication.processingRegistry().removeProvider(self.fournisseur)
            self.fournisseur = None
