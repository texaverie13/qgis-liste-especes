# -*- coding: utf-8 -*-
"""Liste d'espèces — extension QGIS.

Copyright (C) 2026 Valérie Texier

Ce programme est un logiciel libre : vous pouvez le redistribuer et le
modifier selon les termes de la Licence publique générale GNU telle que
publiée par la Free Software Foundation, soit la version 2 de la licence,
soit (à votre choix) toute version ultérieure. Voir le fichier LICENSE.
"""


def classFactory(iface):                   # noqa: N802 — nom impose par QGIS
    from .plugin import ListeEspecesPlugin
    return ListeEspecesPlugin()
