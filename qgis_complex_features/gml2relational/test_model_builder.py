#!/usr/bin/env python
# -*- coding: utf-8 -*-
import unittest

import os
import sys
sys.path = [os.path.join(os.path.dirname(__file__), "../whl/all")] + sys.path

from relational_model_builder import load_gml_model

testdata_path = os.path.join(os.path.dirname(__file__), "testdata")

class TestModelBuilder(unittest.TestCase):

    def test1a(self):
        model = load_gml_model(os.path.join(testdata_path, "t1.xml"), "/tmp")
        self.assertEqual(len(model.tables()), 2)
        ta = "Table<a;"
        ta += "Column<d/text(),TEXT>;"
        ta += "Link<c/cdetails/name(1-*),a_c_cdetails_name>;"
        ta += "Column<c/type/text(),TEXT>;"
        ta += "Column<b/text(),TEXT>;"
        ta += "Column<e/text(),INT>;"
        ta += "Column<id,None,autoincremented>"
        ta += ">"
        self.assertEqual(repr(model.tables()['a']), ta)
        tb = "Table<a_c_cdetails_name;"
        tb += "Column<prefix/text(),TEXT,optional>;"
        tb += "BackLink<c_cdetails_name(a)>;"
        tb += "Column<id,None,autoincremented>"
        tb += ">"
        self.assertEqual(repr(model.tables()['a_c_cdetails_name']), tb)

    def test1b(self):
        # with sequence merging
        model = load_gml_model(os.path.join(testdata_path, "t1.xml"), "/tmp", do_merge_sequences = True)
        self.assertEqual(len(model.tables()), 1)
        t = "Table<a;"
        t += "Column<d/text(),TEXT>;"
        t += "Column<c/cdetails/name[0]/prefix/text(),TEXT,optional>;"
        t += "Column<c/type/text(),TEXT>;"
        t += "Column<b/text(),TEXT>;"
        t += "Column<e/text(),INT>;"
        t += "Column<id,None,autoincremented>"
        t += ">"
        self.assertEqual(repr(model.tables()['a']), t)

    def test1c(self):
        # with 0 max merge depth
        model = load_gml_model(os.path.join(testdata_path, "t1.xml"), "/tmp", merge_max_depth = 0)
        t1 = "Table<a;Link<c(1-1),a_c>;Link<b(1-1),a_b>;Link<e(1-1),a_e>;Column<id,None,autoincremented>;Link<d(1-1),a_d>>"
        self.assertEqual(repr(model.tables()['a']), t1)
        t2 = "Table<a_c_cdetails_name;Link<prefix(0-1),a_c_cdetails_name_prefix>;Column<id,None,autoincremented>;BackLink<name(a_c_cdetails)>>"
        self.assertEqual(repr(model.tables()['a_c_cdetails_name']), t2)
        t3 = "Table<a_c_type;Column<id,None,autoincremented>;Column<text(),TEXT>>"
        self.assertEqual(repr(model.tables()['a_c_type']), t3)
        t4 = "Table<a_d;Column<id,None,autoincremented>;Column<text(),TEXT>>"
        self.assertEqual(repr(model.tables()['a_d']), t4)
        t5 = "Table<a_c;Link<cdetails(1-1),a_c_cdetails>;Link<type(1-1),a_c_type>;Column<id,None,autoincremented>>"
        self.assertEqual(repr(model.tables()['a_c']), t5)
        t6 = "Table<a_b;Column<id,None,autoincremented>;Column<text(),TEXT>>"
        self.assertEqual(repr(model.tables()['a_b']), t6)
        t7 = "Table<a_c_cdetails_name_prefix;Column<id,None,autoincremented>;Column<text(),TEXT,optional>>"
        self.assertEqual(repr(model.tables()['a_c_cdetails_name_prefix']), t7)
        t8 = "Table<a_c_cdetails;Column<id,None,autoincremented>;Link<name(1-*),a_c_cdetails_name>>"
        self.assertEqual(repr(model.tables()['a_c_cdetails']), t8)
        t9 = "Table<a_e;Column<id,None,autoincremented>;Column<text(),INT>>"
        self.assertEqual(repr(model.tables()['a_e']), t9)

    def test2(self):
        model = load_gml_model(os.path.join(testdata_path, "t2.xml"), "/tmp", merge_max_depth = 6, do_merge_sequences = False)
        self.assertEqual(len(model.tables()), 2)
        ta = "Table<a;"
        ta += "Column<d/text(),TEXT>;"
        ta += "Link<c/cdetails/name(1-*),a_c_cdetails_name>;"
        ta += "Column<c/type/text(),TEXT>;"
        ta += "Column<b/text(),TEXT>;"
        ta += "Column<e/text(),INT>;"
        ta += "Column<id,None,autoincremented>>"
        self.assertEqual(repr(model.tables()['a']), ta)
        tb = "Table<a_c_cdetails_name;"
        tb += "Column<prefix/text(),TEXT,optional>;"
        tb += "BackLink<c_cdetails_name(a)>;"
        tb += "Column<id,None,autoincremented>;"
        tb += "Column<suffix/text(),TEXT,optional>>"
        self.assertEqual(repr(model.tables()['a_c_cdetails_name']), tb)        

        # it should be the same with sequence merging
        model = load_gml_model(os.path.join(testdata_path, "t2.xml"), "/tmp", merge_max_depth = 6, do_merge_sequences = True)
        self.assertEqual(len(model.tables()), 2)
        self.assertEqual(repr(model.tables()['a']), ta)
        self.assertEqual(repr(model.tables()['a_c_cdetails_name']), tb)        

    def test3(self):
        model = load_gml_model(os.path.join(testdata_path, "t3.xml"), "/tmp", do_merge_sequences = True)
        t = "Table<a;"
        t += "Column<d/text(),TEXT>;"
        t += "Column<c/cdetails/name[0]/prefix/text(),TEXT,optional>;"
        t += "Column<c/type/text(),TEXT>;"
        t += "Column<b/text(),TEXT>;"
        t += "Column<f/@attr2,INT>;"
        t += "Column<f/@attr1,TEXT,optional>;"
        t += "Column<e/text(),INT>;"
        t += "Column<id,None,autoincremented>>"
        self.assertEqual(repr(model.tables()['a']), t)
        
    def test4(self):
        # tables with ID => unmergeable
        model = load_gml_model(os.path.join(testdata_path, "t4.xml"), "/tmp", do_merge_sequences = True)
        ta = "Table<a;"
        ta += "Link<g(0-1),a_g_t>;"
        ta += "Column<d/text(),TEXT>;"
        ta += "Link<h(0-1),MyHType>;"
        ta += "Column<c/cdetails/name[0]/prefix/text(),TEXT,optional>;"
        ta += "Column<c/type/text(),TEXT>;Column<b/text(),TEXT>;"
        ta += "Column<e/text(),INT>;"
        ta += "Column<id,None,autoincremented>>"
        self.assertEqual(repr(model.tables()['a']), ta)
        tb = "Table<a_g_t;Column<name/text(),TEXT>;Column<@id,INT>>"
        self.assertEqual(repr(model.tables()['a_g_t']), tb)
        tc = "Table<MyHType;Column<name/text(),TEXT>;Column<@id,TEXT>>"
        self.assertEqual(repr(model.tables()['MyHType']), tc)

    def test_geom1(self):
        # schema with a geometry
        model = load_gml_model(os.path.join(testdata_path, "t5.xml"), "/tmp", do_merge_sequences = True)
        for table in model.tables().values():
            print(table)
        t = "Table<mma;Column<name/text(),TEXT>;Geometry<location/Point,Point(4326)>;Column<id,None,autoincremented>>"

if __name__ == '__main__':
    unittest.main()
