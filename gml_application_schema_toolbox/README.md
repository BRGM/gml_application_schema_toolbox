GML application schema toolbox
==============================

This directory contains the QGIS plugin that demonstrates the manipulation of
Complex Features in two modes (native XML or relational).

It relies on a library called [gml2relational](gml2relational) that does the conversion
from XML to a relational model and export the conversion both to a database (Sqlite) and to a QGIS project file.

The plugin will overload standard QGIS identify / attribute table tools so that XML data can be
seen as an XML-tree widget (in XML mode) or as a bunch of related tables (in relational mode).

Some complex types can have a custom viewer widget provided by the library. A description of such
a feature can be found in the [viewer](viewers) direcotry.

