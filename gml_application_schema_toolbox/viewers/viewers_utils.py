"""
/**
 *   Copyright (C) 2016 BRGM (http:///brgm.fr)
 *   Copyright (C) 2016 Oslandia <infos@oslandia.com>
 *
 *   This library is free software; you can redistribute it and/or
 *   modify it under the terms of the GNU Library General Public
 *   License as published by the Free Software Foundation; either
 *   version 2 of the License, or (at your option) any later version.
 *
 *   This library is distributed in the hope that it will be useful,
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 *   Library General Public License for more details.
 *   You should have received a copy of the GNU Library General Public
 *   License along with this library; if not, see <http://www.gnu.org/licenses/>.
 */
"""
# -*- coding: utf-8 -*-
def resolve_xpath_in_model(model, table, xpath):
    # returns sql_tables, sql_wheres, sql_table, sql_column
    for column in table.columns():
        if xpath.startswith(column.xpath()):
            return [table.name()], [], table.name(), column.name()

    for link in table.links():
        link_xpath = link.xpath()
        if xpath.startswith(link_xpath):
            sql_tables, sql_wheres, sql_table, sql_column = resolve_xpath_in_model(model, link.ref_table(), xpath[len(link_xpath)+1:])
            sql_tables.append(table.name())
            if link.max_occurs() is None:
                # * cardinality
                sql_wheres.append((link.ref_table().name() + "." + table.name() + "_id", table.name() + ".id"))
            else:
                # 1 cardinality
                sql_wheres.append((link.ref_table().name() + ".id", table.name() + "." + link.name() + "_id"))
            return sql_tables, sql_wheres, sql_table, sql_column
    return [], [], None, None

def xpath_to_sql(model, table, xpath, id):
    sql_tables, sql_wheres, sql_table, sql_column = resolve_xpath_in_model(model, table, xpath)
    if table.name() not in sql_tables:
        sql_tables.append(table.name())
    sql_wheres.append((table.name() + ".id", "'" + id + "'"))
    return "SELECT {}.{} FROM {} WHERE {} ORDER by {}.id".format(sql_table, sql_column, ", ".join(sql_tables), " AND ".join(t + "=" + v for t, v in sql_wheres), sql_table)

def xpath_on_db(model, table, xpath, id, db):
    cur = db.cursor()
    sql = xpath_to_sql(model, table, xpath, id)
    cur.execute(sql)
    return [r[0] for r in cur.fetchall()]
