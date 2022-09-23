# CHANGELOG

## 1.4.0-beta6 - 2022-09-23

- Rework database selection: fix for spatialite selection #237 by @towa

## 1.4.0-beta5 - 2022-09-19

- Bug fixes, mainly by @towa (Thanks!)

## 1.4.0-beta4 - 13/01/2022

- fix some issues with the new database widget
- fix debug mode
- restore buttons related to foreign key management
- use a processing to convert GMLAS file to database and vice versa instead of subprocessed calls to GDAL
- dependencies upgrade

## 1.4.0-beta3 - 13/08/2021

- fix URI error #163
- modernize database widget
- improved tests

## 1.4.0-beta2 - 02/07/2021

- fix settings and debug mode which was lost in git confusion
- unit tests enlarged

## 1.4.0-beta1 - 21/06/2021

- network requests use the better options from PyQGIS
- settings windows has been redesigned and integrated into QGIS preferences
- minimal QGIS version is now 3.16
- unit tests have been restored
- fix some bugs
- UI improvments (icons...)

## 1.3.1 - 08/03/2021

### Fixed

- request headers were not transmitted in case of redirections [#127](https://github.com/BRGM/gml_application_schema_toolbox/issues/127)
- remove a method which was overriding Python builtin functions [#129](https://github.com/BRGM/gml_application_schema_toolbox/issues/129)
- fix path in File Dialog [#130](https://github.com/BRGM/gml_application_schema_toolbox/issues/130)

## 1.3.0 - 03/03/2021

- refactoring of network requests to better integration in QGIS
- add log abilities
- documentation completly overhauled with updated use cases, docstrings and publication workflow

## 1.3.0-beta1 - 18/12/2020

> Tagged as 1.2.1-beta1 in QGIS Official plugins repository

- refactoring of network requests to better integration in QGIS
- add log abilities
- documentation completly overhauled with updated use cases, docstrings and publication workflow
- fix compatibility with QGIS >= 3.13 ([#94](https://github.com/BRGM/gml_application_schema_toolbox/issues/94))
- start using GitHub Actions for continuous integration and deployment
- bump development guidelines using black, flake8, isort and precommit [#95](https://github.com/BRGM/gml_application_schema_toolbox/pull/95)
- add template for issues [#97](https://github.com/BRGM/gml_application_schema_toolbox/pull/97)
- bump codebase to Python 3 only [#98](https://github.com/BRGM/gml_application_schema_toolbox/pull/98)
- automate release workflow using qgis-plugin-ci [#101](https://github.com/BRGM/gml_application_schema_toolbox/pull/101)

## 1.2.0 - 08/06/2018

New major version, with the following main changes:

- XML mode: support for multiple geometries
- XML mode: support for polyhedral / curves
- UI refactor using a Wizard
- GMLAS mode: handle custom viewers
- GMLAS mode: add href resolution
- WFS version negotiation
- Lots of bug fixes

This work has been funded by [BRGM](http://www.brgm.fr) and [the Association of Finnish Local and Regional Authorities](https://www.localfinland.fi/) (via [Gispo](http://www.gispo.fi/))

## 1.1.4 - 06/11/2017

- Handle multi geometries (#30)
- Allow nested FeatureCollection/members (#29)

## 1.1.3 - 17/07/2017

- Fix download tab
- Fix XML mode with non-spatiail layers

## 1.1.2 - 17/07/2017

- Fix encoding issues
- Code cleanup
- Fix error during export
- Fix handling of unsafe SSL

## 1.1.1 - 13/07/2017

- Use ogr API instead of QGIS to load spatialite layers
- Add TypingConstraints for wml2 and geologylog
- Handle layers with multiple geometries

## 1.1.0 - 11/07/2017

- Remove dependency to pyspatialite
- Bring back XML mode with custom widgets
- Add a custom widget for geology logs
- GMLAS import: option to automatically load layers and configure relations + editor widgets

## 1.0.0 - 15/12/2016

- Add WFS 2 download panel
- Add OGR GMLAS convert panel
- Remove DB relational mode using PyXB (replaced by GMLAS OGR mode)
- Add OGR GMLAS write panel

## 0.8.4 - 17/08/2016

- Handle HTTP 302 redirections

## 0.8.3 - 27/06/2016

- Add licences
- Add doc / readme

## 0.8.2 - 27/06/2016

- Fix custom viewer SQL queries to include order by

## 0.8.1 - 24/06/2016

- Fix an ownership bug only seen on Windows

## 0.8.0 - 20/06/2016

- Add an 'enforce not null constraints' option
- Treat SOS:observationData as features
- Enable custom widgets for embedded href
- Add viewer plugins to the relational mode
- Embed the XML tree widget in the attribute form (and remove custom identify / attribute table buttons)

## 0.7.3 - 16/06/2016

- Fix URI resolution under Windows

## 0.7.1 - 15/06/2016

- Fix remote URI resolving
- Fix XPath handling
- Fix default SRID
- Add support for a Date/Time type in xpath mappings
