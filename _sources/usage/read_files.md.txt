# Read GML App Schema files

Manipulating GML complex features with QGIS revolves around two approaches,
each having a dominating data representation mode:

- a [native XML approach](read_mode_xml.md), where data are stored and manipulated directly in their XML hierarchical form. Each “Complex Feature” is associated with a single row in a vector layer. The user is in charge of identifying among the XML tree, which elements are of interest for its use case.

- a [database (relational) approach](read_mode_db.md), where XML data are first stored in a database with relations between tables. The user then relies on native mechanisms found in QGIS to manipulate these data (joins, relations, form widgets).
