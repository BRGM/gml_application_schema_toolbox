import urllib2

def parse_schemas(schema_files, urlopen = urllib2.urlopen):
    """
    Returns a pyxb Namespace for the given schemas.
    Every dependent schemas will be downloaded thanks to the urlopen function passed in argument.
    :param schema_files: list of schema filename
    :param urlopen: function that takes an URL and returns a file-like object
    :returns: a dict {namespace_uri: pyxb Namespace that is resolved}
    """
    import pyxb.binding.generate
    import pyxb.utils.utility

    try:
        # monkey patch DataFromURI to use our own function
        # so that we can easily manage cache, proxies, and so on
        old_DataFromURI = pyxb.utils.utility.DataFromURI
        pyxb.utils.utility.DataFromURI = lambda uri, archive_directory = None : urlopen(uri)
        
        generator = pyxb.binding.generate.Generator()
        # default options
        parser = generator.optionParser()
        (options, args) = parser.parse_args(args = schema_files)
        generator.applyOptionValues(options, schema_files)
        # call to moduleRecords and ignore the returned value
        # we only need to make sure the namespace is validated and "resolved"
        print(schema_files)
        generator.moduleRecords()
    except pyxb.SchemaValidationError as e:
        raise RuntimeError("When parsing {} - {}".format(schema_files, e.args))
    finally:
        # restore the initial DataFromURI
        pyxb.utils.utility.DataFromURI = old_DataFromURI

    schemas = generator.schemas()
    ns_map = {}
    for schema in schemas:
        ns = schema.targetNamespace()

        # must call resolve to have a walkable schema tree
        ns.resolveDefinitions()
        ns_map[ns.uri()] = ns

        for sub_ns in ns.AvailableNamespaces():
            if not any([sub_ns.uri().startswith(u) for u in ('http://www.w3.org/2000/xmlns/',
                                                             'http://www.w3.org/2001/XMLSchema',
                                                             'http://www.w3.org/XML',
                                                             'http://www.w3.org/1999/xhtml')]):
                ns_map[sub_ns.uri()] = sub_ns

    return ns_map
