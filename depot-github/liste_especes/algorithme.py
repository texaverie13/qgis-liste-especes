# -*- coding: utf-8 -*-
"""
Liste des espèces, sans répétition — algorithme pour la boîte à outils QGIS.

INSTALLATION
    Cet algorithme est fourni par l'extension « Liste d'espèces ». Il apparaît
    dans Traitement ▸ Boîte à outils ▸ « Liste d'espèces » dès que l'extension
    est installée ; il n'y a rien à ajouter à la main.

Copyright (C) 2026 Valérie Texier

Ce programme est un logiciel libre : vous pouvez le redistribuer et le
modifier selon les termes de la Licence publique générale GNU telle que
publiée par la Free Software Foundation, soit la version 2 de la licence,
soit (à votre choix) toute version ultérieure.

Ce programme est distribué dans l'espoir qu'il sera utile, mais SANS AUCUNE
GARANTIE, ni explicite ni implicite. Voir la Licence publique générale GNU
pour plus de détails — le fichier LICENSE accompagne cette extension.

CE QU'IL FAIT
    À partir d'une couche chargée, il rend la liste des espèces rencontrées,
    une par ligne : nom scientifique, nom vernaculaire, CD NOM, nombre
    d'observations. Si la couche porte un champ de groupe biologique, on peut
    n'extraire qu'un groupe ; sinon la question ne se pose pas et tout est
    traité. Les champs sont reconnus tout seuls ; les menus ne servent qu'à
    corriger une reconnaissance.

CE QU'IL PRODUIT
    Deux tables (sans géométrie) :
      • Espèces — la liste.
      • À vérifier — chaque arbitrage rendu, et ce qui a été écarté. C'est la
        liste des corrections à porter dans la base.

POURQUOI IL EST ÉCRIT AINSI — quatre faits mesurés sur la base AGIR le
06/11/2026, et non des précautions de principe :
  1. « Barbastella barbastellus » et « Barbastella barbastellus (Schreber,
     1774) » comptaient pour deux espèces. La clé de regroupement est donc le
     CD NOM, le nom normalisé ne servant que de repli : lui seul rapproche
     « Abies alba » de « Abies alba Mill., 1768 ». Les oiseaux passent de 457
     à 287, les chiroptères de 108 à 35.
  2. Un CD NOM mal saisi scindait une espèce (la barbastelle portait 60348 sur
     une ligne et 60345 sur 180). On rattache au code majoritaire, et on le
     signale.
  3. 55 noms scientifiques portaient un nom vernaculaire faux sur une seule
     ligne. Majorité retenue, écart signalé.
  4. « Myotis blythii/Myotis myotis », « Plecotus sp. », « Gr. Sérotule » ne
     sont pas des doublons : ce sont des déterminations incomplètes. Elles
     sont gardées, dans une colonne à part, et ne sont pas comptées comme des
     espèces.

Le champ « LB Nom » n'est jamais utilisé comme source de nom : il mélange des
espèces et des indications de gestion.
"""
import re
import unicodedata
from collections import Counter, defaultdict

from qgis.core import (QgsFeature, QgsField, QgsFields, QgsProcessing,
                       QgsProcessingAlgorithm, QgsProcessingException,
                       QgsProcessingParameterBoolean,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterField,
                       QgsProcessingParameterString, QgsWkbTypes)
from qgis.PyQt.QtCore import QCoreApplication

# QGIS 4 est bâti sur Qt6 : QgsField attend un QMetaType et non plus un
# QVariant.Type. On accepte les deux, pour que le script survive à un retour
# en arrière comme à une mise à jour.
try:
    from qgis.PyQt.QtCore import QMetaType
    T_TEXTE, T_ENTIER = QMetaType.Type.QString, QMetaType.Type.Int
except Exception:                                    # QGIS 3.x
    from qgis.PyQt.QtCore import QVariant
    T_TEXTE, T_ENTIER = QVariant.String, QVariant.Int

# De même, les énumérations sont devenues scopées. Si aucune des deux formes
# n'existe, on ne devine pas une valeur numérique : on omet simplement
# l'argument, et QGIS retient son propre défaut (tous les types de champs).
def _type_champ():
    for chemin in (("DataType", "Any"), ("Any",)):
        obj = QgsProcessingParameterField
        try:
            for attribut in chemin:
                obj = getattr(obj, attribut)
            return {"type": obj}
        except AttributeError:
            continue
    return {}


TYPE_CHAMP = _type_champ()


# ====================================================================
#  La logique taxonomique — volontairement sans aucun type QGIS, pour
#  qu'elle puisse être relue et vérifiée hors de QGIS.
# ====================================================================
def _clef(nom):
    s = unicodedata.normalize("NFD", str(nom or ""))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[^a-z0-9]+", "", s)


SYNONYMES = {
    "scientifique": ["nomscientifique", "nomlatin", "nomscientifiquevalide",
                     "scientificname", "taxon", "especescientifique"],
    "vernaculaire": ["nomvernaculaire", "nomcommun", "nomfrancais",
                     "vernacularname", "nomvern"],
    "groupe":       ["grpebiologique1", "groupebiologique1", "grpebiologique",
                     "groupebiologique", "grpebio1", "groupe",
                     "grpebiologique2", "groupebiologique2"],
    "code":         ["cdnom", "cdref", "cdnomtaxref", "codetaxref"],
}

INTERDITS = {"lbnom", "nomsaisi"}


def reperer(noms_de_champs):
    dispo = {_clef(c): c for c in noms_de_champs if _clef(c) not in INTERDITS}
    trouve = {}
    for role, candidats in SYNONYMES.items():
        trouve[role] = next((dispo[c] for c in candidats if c in dispo), None)
    return trouve


INDETERMINE = re.compile(
    r"(/|\bsp\b|\bspp\b|\bcf\b|\baff\b|\bgr\b\.?\s|^gr\b|\bindet)", re.IGNORECASE)


def niveau(nom):
    return "indéterminé" if INDETERMINE.search(nom or "") else "espèce"


def noyau(nom):
    """Le nom réduit à ce qui identifie le taxon : sans citation d'auteur
    entre parenthèses, sans ponctuation, sans accents. On ne touche pas au
    reste, pour que « Myotis sp. » ne rejoigne jamais « Myotis myotis »."""
    s = re.sub(r"\([^)]*\)", " ", nom or "")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    s = re.sub(r"[.,;]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def agreger(observations, lister_tout=False):
    """observations : liste de (scientifique, vernaculaire, code, groupe, extras)
    où « extras » est un dict {nom de colonne: valeur} — éventuellement vide.

    Rend (especes, ecarts, ambigus) où
      especes = [(sci, vern, code, groupe, nb_obs, nb_orthographes, niveau,
                  {colonne: valeur})]
      ecarts  = [(type, retenu, ecarte, nb_lignes)]
      ambigus = {colonne: (taxons_concernes, taxons_a_plusieurs_valeurs)}

    LES COLONNES AJOUTÉES SUIVENT LA MÊME RÈGLE QUE LE RESTE : la valeur
    majoritaire est retenue et les autres sont inscrites dans « À vérifier ».
    C'est juste pour une colonne taxonomique — « Ordre » et « Famille » ne
    varient que sur 1 à 3 % des taxons de la base AGIR. Ça ne l'est pas pour
    une colonne de contexte : « Commune » varie sur 63 % des taxons, « année »
    sur 56 %. Pour celles-là, lister_tout=True rend toutes les valeurs, et le
    script prévient quand une colonne choisie s'y prête mal.
    """
    code_du_noyau = defaultdict(Counter)
    for sci, _v, code, _g, _x in observations:
        if code:
            code_du_noyau[noyau(sci)][code] += 1

    codes_ecartes = Counter()
    familles = defaultdict(lambda: {"orth": Counter(), "vern": Counter(),
                                    "code": Counter(), "grp": Counter(),
                                    "sup": defaultdict(Counter), "n": 0})
    for sci, vern, code, g, extras in observations:
        n = noyau(sci)
        majoritaire = (code_du_noyau[n].most_common(1)[0][0]
                       if code_du_noyau.get(n) else "")
        if majoritaire and code != majoritaire:
            if code:
                codes_ecartes[(sci, code, majoritaire)] += 1
            code = majoritaire
        f = familles[("cd", code) if code else ("nom", n)]
        f["orth"][sci] += 1
        f["n"] += 1
        if vern:
            f["vern"][vern] += 1
        if code:
            f["code"][code] += 1
        if g:
            f["grp"][g] += 1
        for nom, valeur_sup in (extras or {}).items():
            if valeur_sup:
                f["sup"][nom][valeur_sup] += 1

    ambigus = defaultdict(lambda: [0, 0])
    especes, ecarts = [], []
    for f in familles.values():
        sci = f["orth"].most_common(1)[0][0]
        sup = {}
        for nom, compte in f["sup"].items():
            ambigus[nom][0] += 1
            if len(compte) > 1:
                ambigus[nom][1] += 1
            if lister_tout:
                sup[nom] = " | ".join(v for v, _ in compte.most_common())
            else:
                sup[nom] = compte.most_common(1)[0][0]
                for autre, n in compte.most_common()[1:]:
                    ecarts.append(("colonne « %s »" % nom, sci, autre, n))
        especes.append((sci,
                        f["vern"].most_common(1)[0][0] if f["vern"] else "",
                        f["code"].most_common(1)[0][0] if f["code"] else "",
                        f["grp"].most_common(1)[0][0] if f["grp"] else "",
                        f["n"], len(f["orth"]), niveau(sci), sup))
        for autre, n in f["orth"].most_common()[1:]:
            ecarts.append(("orthographe", sci, autre, n))
        if len(f["vern"]) > 1:
            for autre, n in f["vern"].most_common()[1:]:
                ecarts.append(("nom vernaculaire", sci, autre, n))
    for (sci, faux, bon), n in codes_ecartes.items():
        ecarts.append(("CD NOM", "%s (CD NOM %s)" % (sci, bon), faux, n))

    especes.sort(key=lambda e: e[0].lower())
    ecarts.sort(key=lambda e: (e[0], e[1].lower()))
    return especes, ecarts, dict(ambigus)


def texte(valeur):
    """Un CD NOM stocké en réel ressortirait « 60360.0 » et ne se
    rapprocherait plus de TAXREF."""
    if valeur is None:
        return ""
    if isinstance(valeur, float) and valeur.is_integer():
        return str(int(valeur))
    s = str(valeur).strip()
    return "" if s.upper() == "NULL" else s


# ====================================================================
#  L'algorithme
# ====================================================================
class ExtraireEspeces(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    CHAMP_SCI = "CHAMP_SCI"
    CHAMP_VERN = "CHAMP_VERN"
    CHAMP_CODE = "CHAMP_CODE"
    CHAMP_GROUPE = "CHAMP_GROUPE"
    GROUPE = "GROUPE"
    COLONNES = "COLONNES"
    LISTER_TOUT = "LISTER_TOUT"
    ESPECES_SEULES = "ESPECES_SEULES"
    ESPECES = "ESPECES"
    A_VERIFIER = "A_VERIFIER"

    def tr(self, t):
        return QCoreApplication.translate("ExtraireEspeces", t)

    def createInstance(self):
        return ExtraireEspeces()

    def name(self):
        return "extraire_especes"

    def displayName(self):
        return self.tr("Liste des espèces (sans répétition)")

    def group(self):
        # Vide : le fournisseur de l'extension est deja le groupe affiche.
        # Un sous-groupe ajouterait un niveau pour un seul algorithme.
        return ""

    def groupId(self):
        return ""

    def shortHelpString(self):
        return self.tr(
            "Rend la liste des espèces d'une couche naturaliste, une par ligne.\n\n"
            "Les champs sont reconnus automatiquement : ne remplissez les menus "
            "que pour corriger une reconnaissance.\n\n"
            "Si la couche porte un champ de groupe biologique, laissez « Groupe "
            "à extraire » vide pour tout prendre, ou saisissez le nom exact d'un "
            "groupe. Les groupes présents sont listés dans le journal à chaque "
            "exécution, et un nom inconnu provoque une erreur qui les rappelle.\n\n"
            "Deux tables sortent : la liste des espèces, et la liste des écarts "
            "tranchés (orthographes, CD NOM, noms vernaculaires divergents) à "
            "corriger dans la base.")

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, self.tr("Couche d'observations"),
            [QgsProcessing.TypeVector]))
        for cle, libelle in (
                (self.CHAMP_SCI, "Champ du nom scientifique (vide = reconnu seul)"),
                (self.CHAMP_VERN, "Champ du nom vernaculaire (vide = reconnu seul)"),
                (self.CHAMP_CODE, "Champ du CD NOM (vide = reconnu seul)"),
                (self.CHAMP_GROUPE, "Champ du groupe biologique (vide = reconnu seul)")):
            self.addParameter(QgsProcessingParameterField(
                cle, self.tr(libelle), parentLayerParameterName=self.INPUT,
                optional=True, **TYPE_CHAMP))
        self.addParameter(QgsProcessingParameterString(
            self.GROUPE, self.tr("Groupe à extraire (vide = tous)"),
            optional=True))
        self.addParameter(QgsProcessingParameterField(
            self.COLONNES,
            self.tr("Colonnes à reporter (statuts de protection, famille, ordre…)"),
            parentLayerParameterName=self.INPUT, allowMultiple=True,
            optional=True, **TYPE_CHAMP))
        self.addParameter(QgsProcessingParameterBoolean(
            self.LISTER_TOUT,
            self.tr("Colonnes reportées : lister toutes les valeurs "
                    "au lieu de la majoritaire"),
            defaultValue=False))
        self.addParameter(QgsProcessingParameterBoolean(
            self.ESPECES_SEULES,
            self.tr("Ne garder que les déterminations à l'espèce"),
            defaultValue=False))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.ESPECES, self.tr("Espèces")))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.A_VERIFIER, self.tr("À vérifier")))

    # ---------------------------------------------------------------- run
    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException(self.tr("Aucune couche en entrée."))

        presents = [f.name() for f in source.fields()]
        auto = reperer(presents)
        cols = {}
        for role, cle in (("scientifique", self.CHAMP_SCI),
                          ("vernaculaire", self.CHAMP_VERN),
                          ("code", self.CHAMP_CODE),
                          ("groupe", self.CHAMP_GROUPE)):
            choisi = self.parameterAsString(parameters, cle, context)
            cols[role] = choisi if choisi else auto[role]

        if not cols["scientifique"]:
            raise QgsProcessingException(self.tr(
                "Aucun champ de nom scientifique reconnu dans cette couche.\n"
                "Champs présents : %s\n"
                "Désignez-le dans le menu « Champ du nom scientifique »."
                % ", ".join(presents)))

        feedback.pushInfo("Champs retenus :")
        for role in ("scientifique", "vernaculaire", "code", "groupe"):
            feedback.pushInfo("   %-14s %s" % (role, cols[role] or "— aucun"))

        voulu = (self.parameterAsString(parameters, self.GROUPE, context) or "").strip()
        especes_seules = self.parameterAsBool(parameters, self.ESPECES_SEULES, context)
        lister_tout = self.parameterAsBool(parameters, self.LISTER_TOUT, context)
        supplements = [c for c in
                       (self.parameterAsFields(parameters, self.COLONNES, context) or [])
                       if c in presents]
        if supplements:
            feedback.pushInfo("Colonnes reportées : %s" % ", ".join(supplements))

        # ---- lecture ----
        observations = []
        sans_nom = 0
        groupes = Counter()
        total = source.featureCount() or 0
        pas = 100.0 / total if total else 0
        for i, e in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                break
            g = texte(e[cols["groupe"]]) if cols["groupe"] else ""
            if g:
                groupes[g] += 1
            if voulu and g != voulu:
                continue
            sci = texte(e[cols["scientifique"]])
            if not sci:
                sans_nom += 1
                continue
            observations.append((
                sci,
                texte(e[cols["vernaculaire"]]) if cols["vernaculaire"] else "",
                texte(e[cols["code"]]) if cols["code"] else "",
                g,
                {c: texte(e[c]) for c in supplements}))
            if pas:
                feedback.setProgress(int(i * pas))

        if cols["groupe"] and groupes:
            feedback.pushInfo("\nGroupes présents dans la couche :")
            for g, n in groupes.most_common():
                feedback.pushInfo("   %-34s %7d" % (g, n))
            if voulu and voulu not in groupes:
                raise QgsProcessingException(self.tr(
                    "Le groupe « %s » n'existe pas dans cette couche.\n"
                    "Groupes présents : %s" % (voulu, ", ".join(sorted(groupes)))))
        elif not cols["groupe"]:
            feedback.pushInfo("\nPas de champ de groupe biologique : "
                              "toute la couche est traitée.")

        if not observations:
            raise QgsProcessingException(self.tr(
                "Aucune observation ne porte de nom scientifique dans cette "
                "sélection."))

        especes, ecarts, ambigus = agreger(observations, lister_tout)

        # ---- sorties ----
        champs = QgsFields()
        if cols["groupe"] and not voulu:
            champs.append(QgsField("Groupe biologique", T_TEXTE))
        champs.append(QgsField("Nom scientifique", T_TEXTE))
        champs.append(QgsField("Nom vernaculaire", T_TEXTE))
        champs.append(QgsField("CD NOM", T_TEXTE))
        for c in supplements:
            champs.append(QgsField(c, T_TEXTE))
        champs.append(QgsField("Nombre d'observations", T_ENTIER))
        champs.append(QgsField("Orthographes regroupées", T_ENTIER))
        champs.append(QgsField("Détermination", T_TEXTE))

        sink, id_especes = self.parameterAsSink(
            parameters, self.ESPECES, context, champs,
            QgsWkbTypes.NoGeometry)
        gardees = [e for e in especes if e[6] == "espèce"] if especes_seules else especes
        for e in gardees:
            f = QgsFeature(champs)
            valeurs = ([e[3]] if (cols["groupe"] and not voulu) else []) + \
                      [e[0], e[1], e[2]] + \
                      [e[7].get(c, "") for c in supplements] + \
                      [e[4], e[5], e[6]]
            f.setAttributes(valeurs)
            sink.addFeature(f)

        champs2 = QgsFields()
        champs2.append(QgsField("Type d'écart", T_TEXTE))
        champs2.append(QgsField("Retenu", T_TEXTE))
        champs2.append(QgsField("Variante écartée", T_TEXTE))
        champs2.append(QgsField("Nombre de lignes", T_ENTIER))
        sink2, id_verif = self.parameterAsSink(
            parameters, self.A_VERIFIER, context, champs2,
            QgsWkbTypes.NoGeometry)
        for t, retenu, ecarte, n in ecarts:
            f = QgsFeature(champs2)
            f.setAttributes([t, retenu, ecarte, n])
            sink2.addFeature(f)

        # ---- compte rendu ----
        determinees = [e for e in especes if e[6] == "espèce"]
        autres = len(especes) - len(determinees)
        regroupees = sum(1 for e in especes if e[5] > 1)
        feedback.pushInfo("\n%d espèce(s) déterminée(s)." % len(determinees))
        if autres:
            feedback.pushInfo("   + %d détermination(s) incomplète(s) — genres, "
                              "couples acoustiques, groupes%s."
                              % (autres, " (écartées)" if especes_seules else ""))
        if regroupees:
            feedback.pushInfo("   %d espèce(s) rassemblent plusieurs orthographes."
                              % regroupees)
        if sans_nom:
            feedback.pushInfo("   %d ligne(s) sans nom scientifique (repères, "
                              "pièges, fins de protocole) : écartées." % sans_nom)
        if ecarts:
            feedback.pushInfo("\n%d écart(s) tranchés à la majorité — voir la "
                              "table « À vérifier »." % len(ecarts))
        if not lister_tout:
            for nom, (concernes, incertains) in sorted(ambigus.items()):
                if concernes and incertains * 3 > concernes:
                    feedback.pushWarning(
                        "La colonne « %s » porte plusieurs valeurs pour %d des "
                        "%d taxons (%.0f %%) : c'est une colonne de contexte, "
                        "pas un attribut du taxon. La valeur majoritaire qui "
                        "sort n'a guère de sens — cochez « lister toutes les "
                        "valeurs », ou retirez cette colonne."
                        % (nom, incertains, concernes,
                           100.0 * incertains / concernes))

        return {self.ESPECES: id_especes, self.A_VERIFIER: id_verif}
