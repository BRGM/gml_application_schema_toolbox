GML2relational
--------------

This folder contains a Python library to convert an (GML-derived) XML file to a relational database model.

The library relies on the PyXB library to parse a set of XSD schemas and associate a type to each element and attribute
of an XML stream.

The high-level entry point function is `load_gml_model` found in [relational_model_builder.py](relational_model_builder.py) that will parse an XML file,
resolve its schemas and returns a `Model` (see [relational_model.py](relational_model.py)). A model is an abstract representation of a relational model:
a set of table and links between them.

From a `Model`, some writers are available:

  * an SQLite/Spatialite writer found in [sqlite_writer.py](sqlite_writer.py)
  * a QGIS project exporter found in [qgis_project_writer.py](qgis_project_writer.py)


