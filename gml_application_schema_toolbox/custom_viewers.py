import sys
from viewers import *

__custom_viewers = None

def get_custom_viewers():
    global __custom_viewers

    if __custom_viewers is not None:
        # viewers already loaded
        return __custom_viewers
    __custom_viewers = {}

    # introspect the viewers module
    #print(sys.modules.keys())
    module = sys.modules['gml_application_schema_toolbox.viewers']
    for klass in dir(module):
        if klass.startswith('__'):
            continue
        k = getattr(module, klass)
        if hasattr(k, 'xml_tag'):
            __custom_viewers[k.xml_tag()] = k

    return __custom_viewers


