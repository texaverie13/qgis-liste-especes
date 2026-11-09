# -*- coding: utf-8 -*-
"""Charge l'extension avec un FAUX module qgis, hors de QGIS.

    python3 tests/banc_plugin.py

A lancer avant chaque publication d'une version.

Ce que ce banc attrape : import manquant, nom indéfini, nom réutilisé,
classe mal héritée, erreur de syntaxe — toute la famille d'erreurs qui ne se
voit aujourd'hui qu'en lançant QGIS.
Ce qu'il n'attrape pas : le comportement réel des objets QGIS.
"""
import importlib, os, sys, types

class MetaFaux(type):
    """L'acces a un attribut DE CLASSE (QMetaType.Type) passe par la
    metaclasse, pas par __getattr__ de l'instance. Sans elle, le banc
    echouait sur mon propre faux module en faisant croire a un bug du
    code teste."""
    def __getattr__(cls, nom):
        if nom.startswith("__"):
            raise AttributeError(nom)
        return type(nom, (Faux,), {})


class Faux(metaclass=MetaFaux):
    """Une classe qui accepte tout : heritage, appel, attribut."""
    def __init__(self, *a, **k): pass
    def __call__(self, *a, **k): return Faux()
    def __getattr__(self, nom): return Faux()

def _module(nom):
    m = types.ModuleType(nom)
    def getattr_(cle):
        if cle.startswith("__"):
            raise AttributeError(cle)
        return type(cle, (Faux,), {})
    m.__getattr__ = getattr_
    m.__path__ = []
    return m

for nom in ("qgis", "qgis.core", "qgis.gui", "qgis.PyQt", "qgis.PyQt.QtCore",
            "qgis.PyQt.QtGui", "qgis.PyQt.QtWidgets"):
    sys.modules[nom] = _module(nom)
# QCoreApplication.translate doit rendre une chaîne, pas un faux objet
sys.modules["qgis.PyQt.QtCore"].QCoreApplication = type(
    "QCoreApplication", (), {"translate": staticmethod(lambda ctx, t, *a: t)})

# La RACINE DU DEPOT, et non le dossier courant : le banc doit tourner
# depuis n'importe ou, y compris depuis une integration continue.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
paquet = importlib.import_module("liste_especes")
print("   ✓ liste_especes importé — classFactory : %s" % callable(paquet.classFactory))
plugin = paquet.classFactory(Faux())
print("   ✓ classFactory() a rendu %s" % type(plugin).__name__)
for methode in ("initGui", "initProcessing", "unload"):
    assert hasattr(plugin, methode), "méthode manquante : " + methode
print("   ✓ initGui / initProcessing / unload présents")
plugin.initGui(); plugin.unload()
print("   ✓ initGui() puis unload() sans erreur")

from liste_especes.provider import FournisseurListeEspeces
from liste_especes.algorithme import ExtraireEspeces
f = FournisseurListeEspeces()
print("   ✓ fournisseur : id=%r  name=%r" % (f.id(), f.name()))
a = ExtraireEspeces()
print("   ✓ algorithme  : name=%r  displayName=%r" % (a.name(), a.displayName()))
print("   ✓ createInstance -> %s" % type(a.createInstance()).__name__)
a.initAlgorithm()
print("   ✓ initAlgorithm() sans erreur")
aide = a.shortHelpString()
print("   ✓ aide : %d caractères" % len(aide))
