# Custom viewers API

This directory contains the custom viewer plugins.

A custom viewer plugin receives a complex feature in input and procudes a QWidget that offers a customized view of the feature's data.

A first example is shipped with the current plugin: a custom viewer for timeseries of WaterML2 data. It can be found in [wml2_timeseries.py](wml2_timeseries.py)

The API is subject to changes, but the current situation is the following. Any class found in this directory is a custom viewer if it has :

- an `xml_tag()` method that gives the XML tag (with namespace) this widget is meant for
- a `name()` method that gives its name
- a `icon()` method that returns its icon, as QIcon
- a `table_name()` method that gives the table name this widget is meant for in relational mode
- a `init_from_xml()` method that returns a QWidget from a XML tree
- a `init_from_model()` method that returns QWidget from a model, a sqlite connection and a feature id

These two last methods should be merged in the future. Indeed, custom viewers could be made abstract enough to be independent from the mode used by the user to access data (relational or XML-based).  
Each custom viewer could then declare the data it is interested in by a list of XPath expressions.
