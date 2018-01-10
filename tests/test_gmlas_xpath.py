import unittest

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "gml_application_schema_toolbox"))

from core.gmlas_xpath import GmlAsXPathResolver

class TestGMLASXPath(unittest.TestCase):
 
    def test_geologylog(self):
        resolver = GmlAsXPathResolver("geology_log1.sqlite", "SQLite", "")
        v = resolver.resolve_xpath("gw_geologylogcoverage", "id", "ab.ww.402557.log.1.coverage", "element/LogValue/value/DataRecord/field/Category/value/text()")
        self.assertEqual(sorted(v), ['Clay', 'Gravel', 'Soil', 'Till'])
        v = resolver.resolve_xpath("gw_geologylogcoverage", "id", "ab.ww.402557.log.1.coverage", "element/LogValue/fromDepth/Quantity/value")
        self.assertEqual(sorted(v), [0.0, 0.3, 4.27, 9.14])
        v = resolver.resolve_xpath("gw_geologylogcoverage", "id", "ab.ww.402557.log.1.coverage", "element/LogValue/toDepth/Quantity/value")
        self.assertEqual(sorted(v), [0.3, 4.27, 9.14, 11.58])        
 
if __name__ == '__main__':
    unittest.main()
