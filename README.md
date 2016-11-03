GML application schema toolbox
==============================

This is prototype implementation of a toolbox designed to manipulate Complex Features.

It mainly consists of a QGIS plugin that allows to import Complex Features in two modes:

  * the native XML mode
  * the relational mode where the XML is first converted into a database, thanks to the PyXB library
 
In native XML mode, the standard QGIS attribute form is extended with a widget that display an XML tree with interaction (like allowing the user to resolve a xlink:href elements)

![](doc/Resolve_embedded_observation.png)

In relational mode, the application schema is first translated into a set of linked tables in a spatialite database. Some options can be set by the user to parameter the way tables and columns are created out of the XSD schemas.

![](doc/creation_dialog.png)

The whole relational model allows to configure QGIS and especially the different relations between tables and the types of edit widgets used for columns. This allows to use standard QGIS form to navigate the relational model


This QGIS plugin also explores a functionality that allows developers to provide custom viewer widgets for certain element types. For example, timeseries of a WaterML2 stream is better seen as a plot diagram rather that as a list of values.

![](doc/custom_WaterML2_viewer.png)

A prototype API allows to extend this mecanism to any kind of complex types.

Directories
-----------

The [gml_application_schema_toolbox](gml_application_schema_toolbox) contains the QGIS plugin sources.

The [samples](samples) directory contains sample Complex Features streams.

The [doc](doc) directory contains some documentation on the project.

Authors
-------

This plugin has been funded by BRGM and developed by Oslandia

License
-------

GPLv2+
