def resolve_xpath_in_model(model, table, xpath):
    # returns sql_tables, sql_wheres, sql_column
    for column in table.columns():
        if xpath.startswith(column.xpath()):
            return [table.name()], [], column.name()
        
    for link in table.links():
        link_xpath = link.xpath()
        if xpath.startswith(link_xpath):
            sql_tables, sql_wheres, sql_column = resolve_xpath_in_model(model, link.ref_table(), xpath[len(link_xpath)+1:])
            sql_tables.append(table.name())
            if link.max_occurs() is None:
                # * cardinality
                sql_wheres.append((link.ref_table().name() + "." + table.name() + "_id", table.name() + ".id"))
            else:
                # 1 cardinality
                sql_wheres.append((link.ref_table().name() + ".id", table.name() + "." + link.name() + "_id"))
            return sql_tables, sql_wheres, sql_column
    return [], [], None

def xpath_to_sql(model, table, xpath, id):
    sql_tables, sql_wheres, sql_column = resolve_xpath_in_model(model, table, xpath)
    if table.name() not in sql_tables:
        sql_tables.append(table.name())
    sql_wheres.append((table.name() + ".id", "'" + id + "'"))
    return "SELECT {} FROM {} WHERE {}".format(sql_column, ", ".join(sql_tables), " AND ".join(t + "=" + v for t, v in sql_wheres))

def xpath_on_db(model, table, xpath, id, db):
    cur = db.cursor()
    sql = xpath_to_sql(model, table, xpath, id)
    cur.execute(sql)
    return [r[0] for r in cur.fetchall()]
