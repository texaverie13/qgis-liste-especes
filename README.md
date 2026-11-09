# Liste d'espèces — extension QGIS

Liste les espèces d'une couche naturaliste **sans doublon**, en regroupant sur
le **CD NOM** (TAXREF) plutôt que sur le nom écrit.

Compatible QGIS 3.22 et QGIS 4.

## Le problème

Dans une base d'observations saisie par plusieurs personnes sur plusieurs
années, la même espèce s'écrit de plusieurs façons :

```
Barbastella barbastellus
Barbastella barbastellus (Schreber, 1774)
Abies alba
Abies alba Mill., 1768
```

Un regroupement sur le nom en fait deux espèces. Un regroupement sur le CD NOM
en fait une. Mesuré sur une base réelle : les oiseaux passent de **457 lignes à
287 espèces**, les chiroptères de **108 à 35**.

## Ce que l'extension produit

Deux tables, sans géométrie.

**Espèces** — une ligne par espèce : nom scientifique, nom vernaculaire,
CD NOM, nombre d'observations, et les colonnes supplémentaires de votre choix
(statuts de protection, par exemple).

**À vérifier** — chaque arbitrage rendu et chaque ligne écartée. C'est la liste
des corrections à porter dans la base, pas un journal technique.

## Ce qu'elle ne fait pas passer pour une espèce

`Plecotus sp.`, `Myotis blythii/Myotis myotis`, `Gr. Sérotule` ne sont pas des
doublons : ce sont des déterminations incomplètes. Elles sont conservées, dans
une colonne à part, et ne sont pas comptées comme des espèces.

## Les arbitrages, et comment ils sont signalés

| Situation rencontrée | Ce que fait l'extension |
|---|---|
| Un CD NOM mal saisi scinde une espèce | Rattache au code majoritaire, et l'écrit dans « À vérifier » |
| Un nom vernaculaire diverge sur quelques lignes | Retient la majorité, signale l'écart |
| Aucun nom scientifique sur la ligne | Écarte la ligne, et la compte |
| La couche porte un groupe biologique | Permet de n'extraire qu'un groupe |
| La couche n'en porte pas | Ne pose pas la question |

Les champs sont reconnus automatiquement. Les menus ne servent qu'à corriger
une reconnaissance.

## Installation

**Depuis QGIS** — Extensions ▸ Installer/Gérer les extensions ▸ chercher
« Liste d'espèces ».

**Depuis ce dépôt** — télécharger le dossier `liste_especes`, le compresser en
ZIP, puis Extensions ▸ Installer depuis un ZIP.

L'algorithme apparaît dans Traitement ▸ Boîte à outils ▸ **Liste d'espèces**.
L'extension n'ajoute ni menu ni barre d'outils.

## Signaler un problème

Par l'onglet [Issues](../../issues) de ce dépôt.

## Licence

GPL v2 ou ultérieure. Voir [LICENSE](LICENSE).

## Auteure

Valérie Texier — géomaticienne-cartographe.
