#!/usr/bin/env python
# -*- coding: utf-8 -*-
import unittest

import os
import sys
import tempfile
sys.path = [os.path.join(os.path.dirname(__file__), "../whl/all")] + sys.path

from relational_model_builder import load_gml_model

testdata_path = os.path.join(os.path.dirname(__file__), "testdata")


class TestModelBuilder(unittest.TestCase):

    def assertTableEqualRepr(self, table, trepr):
        # trepr = set of Field's repr
        torig_repr = set([repr(f) for f in table.fields().values()])
        missing_fields = torig_repr - trepr
        self.assertTrue(missing_fields == set(), "Missing fields : {} got {} expected {}".format(missing_fields, trepr, torig_repr))
        new_fields = trepr - torig_repr
        self.assertTrue(new_fields == set(), "New fields : {} got {} expected {}".format(new_fields, trepr, torig_repr))
    
    def test1a(self):
        model = load_gml_model(os.path.join(testdata_path, "t1.xml"), tempfile.gettempdir())
        self.assertEqual(len(model.tables()), 2)
        ta = set(["Column<d/text(),TEXT>",
                  "Link<c/cdetails/name(1-*),a_c_cdetails_name>",
                  "Column<c/type/text(),TEXT>",
                  "Column<b/text(),TEXT>",
                  "Column<e/text(),INT>",
                  "Column<@id,None,autoincremented>"])
        self.assertTableEqualRepr(model.tables()['a'], ta)

        tb = set(["Column<prefix/text(),TEXT,optional>",
                  "BackLink<c_cdetails_name(a)>",
                  "Column<@id,None,autoincremented>"])
        self.assertTableEqualRepr(model.tables()['a_c_cdetails_name'], tb)

    def test1b(self):
        # with sequence merging
        model = load_gml_model(os.path.join(testdata_path, "t1.xml"), tempfile.gettempdir(), merge_sequences = True)
        self.assertEqual(len(model.tables()), 1)
        t = set(["Column<d/text(),TEXT>",
                 "Column<c/cdetails/name[0]/prefix/text(),TEXT,optional>",
                 "Column<c/type/text(),TEXT>",
                 "Column<b/text(),TEXT>",
                 "Column<e/text(),INT>",
                 "Column<@id,None,autoincremented>"])
        self.assertTableEqualRepr(model.tables()['a'], t)

    def test1c(self):
        # with 0 max merge depth
        model = load_gml_model(os.path.join(testdata_path, "t1.xml"), tempfile.gettempdir(), merge_max_depth = 0)
        t1 = set(["Link<c(1-1),a_c>","Link<b(1-1),a_b>","Link<e(1-1),a_e>","Column<@id,None,autoincremented>","Link<d(1-1),a_d>"])
        self.assertTableEqualRepr(model.tables()['a'], t1)
        t2 = set(["Link<prefix(0-1),a_c_cdetails_name_prefix>","Column<@id,None,autoincremented>","BackLink<name(a_c_cdetails)>"])
        self.assertTableEqualRepr(model.tables()['a_c_cdetails_name'], t2)
        t3 = set(["Column<@id,None,autoincremented>","Column<text(),TEXT>"])
        self.assertTableEqualRepr(model.tables()['a_c_type'], t3)
        t4 = set(["Column<@id,None,autoincremented>","Column<text(),TEXT>"])
        self.assertTableEqualRepr(model.tables()['a_d'], t4)
        t5 = set(["Link<cdetails(1-1),a_c_cdetails>","Link<type(1-1),a_c_type>","Column<@id,None,autoincremented>"])
        self.assertTableEqualRepr(model.tables()['a_c'], t5)
        t6 = set(["Column<@id,None,autoincremented>","Column<text(),TEXT>"])
        self.assertTableEqualRepr(model.tables()['a_b'], t6)
        t7 = set(["Column<@id,None,autoincremented>","Column<text(),TEXT,optional>"])
        self.assertTableEqualRepr(model.tables()['a_c_cdetails_name_prefix'], t7)
        t8 = set(["Column<@id,None,autoincremented>","Link<name(1-*),a_c_cdetails_name>"])
        self.assertTableEqualRepr(model.tables()['a_c_cdetails'], t8)
        t9 = set(["Column<@id,None,autoincremented>","Column<text(),INT>"])
        self.assertTableEqualRepr(model.tables()['a_e'], t9)

    def test2(self):
        model = load_gml_model(os.path.join(testdata_path, "t2.xml"), tempfile.gettempdir(), merge_max_depth = 6, merge_sequences = False)
        self.assertEqual(len(model.tables()), 2)
        ta = set(["Column<d/text(),TEXT>",
                  "Link<c/cdetails/name(1-*),a_c_cdetails_name>",
                  "Column<c/type/text(),TEXT>",
                  "Column<b/text(),TEXT>",
                  "Column<e/text(),INT>",
                  "Column<@id,None,autoincremented>"])
        self.assertTableEqualRepr(model.tables()['a'], ta)
        tb = set(["Column<prefix/text(),TEXT,optional>",
                  "BackLink<c_cdetails_name(a)>",
                  "Column<@id,None,autoincremented>",
                  "Column<suffix/text(),TEXT,optional>"])
        self.assertTableEqualRepr(model.tables()['a_c_cdetails_name'], tb)        

        # it should be the same with sequence merging
        model = load_gml_model(os.path.join(testdata_path, "t2.xml"), tempfile.gettempdir(), merge_max_depth = 6, merge_sequences = True)
        self.assertEqual(len(model.tables()), 2)
        self.assertTableEqualRepr(model.tables()['a'], ta)
        self.assertTableEqualRepr(model.tables()['a_c_cdetails_name'], tb)        

    def test3(self):
        model = load_gml_model(os.path.join(testdata_path, "t3.xml"), tempfile.gettempdir(), merge_sequences = True)
        t = set(["Column<d/text(),TEXT>",
                 "Column<c/cdetails/name[0]/prefix/text(),TEXT,optional>",
                 "Column<c/type/text(),TEXT>",
                 "Column<b/text(),TEXT>",
                 "Column<f/@attr2,INT>",
                 "Column<f/@attr1,TEXT,optional>",
                 "Column<e/text(),INT>",
                 "Column<@id,None,autoincremented>"])
        self.assertTableEqualRepr(model.tables()['a'], t)
        
    def test4(self):
        # tables with ID => unmergeable
        model = load_gml_model(os.path.join(testdata_path, "t4.xml"), tempfile.gettempdir(), merge_sequences = True)
        ta = set(["Link<g(0-1),a_g_t>",
                  "Column<d/text(),TEXT>",
                  "Link<h(0-1),MyHType>",
                  "Column<c/cdetails/name[0]/prefix/text(),TEXT,optional>",
                  "Column<c/type/text(),TEXT>","Column<b/text(),TEXT>",
                  "Column<e/text(),INT>",
                  "Column<@id,None,autoincremented>"])
        self.assertTableEqualRepr(model.tables()['a'], ta)
        tb = set(["Column<name/text(),TEXT>","Column<@id,INT>"])
        self.assertTableEqualRepr(model.tables()['a_g_t'], tb)
        tc = set(["Column<name/text(),TEXT>","Column<@id,TEXT>"])
        self.assertTableEqualRepr(model.tables()['MyHType'], tc)

    def xtest_geom1(self):
        # schema with a geometry
        model = load_gml_model(os.path.join(testdata_path, "t5.xml"), tempfile.gettempdir(), merge_sequences = True)
        for table in model.tables().values():
            print(table)
        t = set(["Column<name/text(),TEXT>","Geometry<location/Point,Point(4326)>","Column<@id,None,autoincremented>"])

if __name__ == '__main__':
    unittest.main()
