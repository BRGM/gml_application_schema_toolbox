from __future__ import print_function
import logging
import pyspatialite.dbapi2 as db

def stream_sql_schema(tables):
    """Creates SQL(ite) table creation statements from a dict of Table
    :returns: a generator that yield a new SQL line
    """
    for name, table in tables.iteritems():
        assert name == table.name()
        stmt = u"CREATE TABLE " + name + u"(\n";
        columns = []
        for c in table.columns():
            if c.ref_type():
                l = c.name() + u" " + c.ref_type()
            else:
                l = c.name() + u" INT PRIMARY KEY"
            if not c.optional():
                l += u" NOT NULL"
            columns.append("  " + l)

        fk_constraints = []
        sub_groups = {}
        for link in table.links():
            if link.ref_table() is None or link.max_occurs() is None:
                continue
            if not link.optional() and not link.substitution_group():
                nullity = u" NOT NULL"
            else:
                nullity = u""

            # deal with substitution groups
            sgroup = link.substitution_group()
            if sgroup is not None:
                if not sub_groups.has_key(sgroup):
                    sub_groups[sgroup] = [link]
                else:
                    sub_groups[sgroup].append(link)

            id = link.ref_table().uid_column()
            if id is not None and id.ref_type() is not None:
                fk_constraints.append((link.name(), link.ref_table(), id.ref_type() + nullity))
            else:
                fk_constraints.append((link.name(), link.ref_table(), u"INT" + nullity))

        for bl in table.back_links():
            if bl.ref_table() is None:
                continue
            id = bl.ref_table().uid_column()
            if id is not None and id.ref_type() is not None:
                fk_constraints.append((bl.ref_table().name(), bl.ref_table(), id.ref_type()))
            else:
                fk_constraints.append((bl.ref_table().name(), bl.ref_table(), u"INT"))

        for n, t, type_str in fk_constraints:
            columns.append("  " + n + u"_id " + type_str)
        for n, t, type_str in fk_constraints:
            columns.append(u"  FOREIGN KEY({}_id) REFERENCES {}(id)".format(n, t.name()))

        # substitution group checks
        for sg, links in sub_groups.iteritems():
            # XOR constraint
            c = [[l2.name() + u"_id IS " + ("NOT NULL" if l == l2 else "NULL") for l2 in links] for l in links]
            txt = u"(" + u") OR (".join([u" AND ".join(e) for e in c]) + u")"
            columns.append(u"  CHECK (" + txt +u")")

        stmt += u",\n".join(columns) + u");"
        yield(stmt)

        for g in table.geometries():
            yield(u"SELECT AddGeometryColumn('{}', '{}', {}, '{}', '{}');".format(table.name(), g.name(), g.srid(), g.type(), "XY" if g.dimension() == 2 else "XYZ"))


def stream_sql_rows(tables_rows):
    def escape_value(v):
        if v is None:
            return u'null'
        if isinstance(v, (str,unicode)):
            return u"'" + unicode(v).replace("'", "''") + u"'"
        if isinstance(v, tuple):
            # ('GeomFromText('%s', %d)', 'POINT(...)')
            pattern = v[0]
            args = v[1:]
            return pattern % args
        else:
            return unicode(v)

    yield(u"PRAGMA foreign_keys = OFF;")
    for table_name, rows in tables_rows.iteritems():
        for row in rows:
            columns = [n for n,v in row if v is not None]
            values = [escape_value(v) for _,v in row if v is not None]
            yield(u"INSERT INTO {} ({}) VALUES ({});".format(table_name, ",".join(columns), ",".join(values)))
    yield(u"PRAGMA foreign_keys = ON;")


def create_sqlite_from_model(model, sqlite_file):
    conn = db.connect(sqlite_file)
    cur = conn.cursor()
    cur.execute("SELECT InitSpatialMetadata(1);")
    conn.commit()
    for line in stream_sql_schema(model.tables()):
        logging.debug(line)
        cur.execute(line)
    conn.commit()
    for line in stream_sql_rows(model.tables_rows()):
        logging.debug(line)
        cur.execute(line)
    conn.commit()


