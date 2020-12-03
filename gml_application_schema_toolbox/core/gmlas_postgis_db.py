
from processing.tools.postgis import GeoDB

try:
    from qgis.core import QgsProcessingException as DbError
except ImportError:
    from processing.tools.postgis import DbError

from gml_application_schema_toolbox.core.logging import log


class ForeignKey():

    def __init__(self, table, column, referenced_table, referenced_column):
        self.table = table
        self.column = column
        self.referenced_table = referenced_table
        self.referenced_column = referenced_column
        self.name = "{self.column}_fkey".format(self=self)

    def __str__(self):
        return ('ForeignKey("{self.name}", '
                '"{self.table}"."{self.column}" => '
                '"{self.referenced_table}"."{self.referenced_column}")'
                .format(self=self))


class GmlasPostgisDB(GeoDB):

    def _add_foreign_key_constraint(self,
                                    schema,
                                    foreign_key):
        if self._constraint_exists(schema=schema,
                                   table=foreign_key.table,
                                   constraint=foreign_key.name):
            return
        sql = """
ALTER TABLE "{schema}"."{foreign_key.table}"
    ADD CONSTRAINT "{foreign_key.name}"
    FOREIGN KEY ("{foreign_key.column}")
    REFERENCES "{schema}"."{foreign_key.referenced_table}" ("{foreign_key.referenced_column}");
""".format(schema=schema, foreign_key=foreign_key)
        c = self.con.cursor()
        self._exec_sql(c, sql)

    def _add_unique_constraint(self, schema, table, column):
        constraint = ("{table}_{column}_unique"
                      .format(table=table,
                              column=column))

        if self._constraint_exists(schema=schema,
                                   table=table,
                                   constraint=constraint):
            return

        sql = """
ALTER TABLE "{schema}"."{table}"
    ADD CONSTRAINT "{constraint}"
    UNIQUE ("{column}");
""".format(schema=schema,
           table=table,
           constraint=constraint,
           column=column)
        c = self.con.cursor()
        self._exec_sql(c, sql)

    def _constraint_exists(self, schema, table, constraint):
        sql = """
SELECT count(*)
FROM information_schema.table_constraints
WHERE table_schema = '{schema}'
AND table_name = '{table}'
AND constraint_name = '{constraint}';
""".format(schema=schema,
           table=table,
           constraint=constraint)
        c = self.con.cursor()
        self._exec_sql(c, sql)
        count, = c.fetchone()
        return count == 1

    def _drop_constraint(self, schema, table, constraint):
        if not self._constraint_exists(schema, table, constraint):
            return
        sql = """
ALTER TABLE "{schema}"."{table}"
    DROP CONSTRAINT "{constraint}";
""".format(schema=schema,
           table=table,
           constraint=constraint)
        c = self.con.cursor()
        self._exec_sql(c, sql)

    def _exec_sql(self, c, sql):
        log(sql)
        super(GmlasPostgisDB, self)._exec_sql(c, sql)

    def _foreign_keys(self, schema):
        foreign_keys = []

        # one to many relationships
        sql = """
SELECT
    _ogr_fields_metadata.layer_name,
    _ogr_fields_metadata.field_name,
    _ogr_layer_relationships.child_layer,
    _ogr_layer_relationships.child_pkid

FROM "{schema}"._ogr_fields_metadata

INNER JOIN "{schema}"._ogr_layer_relationships
    ON _ogr_layer_relationships.parent_element_name = _ogr_fields_metadata.field_name
    AND _ogr_layer_relationships.parent_layer = _ogr_fields_metadata.layer_name
    AND _ogr_layer_relationships.child_layer = _ogr_fields_metadata.field_related_layer

-- Filter by existing columns in current schema
INNER JOIN information_schema.columns
    ON  columns.table_schema = '{schema}'
    AND columns.table_name = _ogr_fields_metadata.layer_name
    AND columns.column_name = _ogr_fields_metadata.field_name

INNER JOIN information_schema.columns referenced_columns
    ON  referenced_columns.table_schema = '{schema}'
    AND referenced_columns.table_name = _ogr_layer_relationships.child_layer
    AND referenced_columns.column_name = _ogr_layer_relationships.child_pkid

WHERE field_category IN (
    'PATH_TO_CHILD_ELEMENT_NO_LINK',
    'PATH_TO_CHILD_ELEMENT_WITH_LINK');
""".format(schema=schema)
        c = self.con.cursor()
        self._exec_sql(c, sql)
        for (layer_name,
             field_name,
             child_layer,
             child_pkid) in c:
            foreign_keys.append(ForeignKey(
                table=layer_name,
                column=field_name,
                referenced_table=child_layer,
                referenced_column=child_pkid))

        # many to many relationships
        sql = """
SELECT
    _ogr_fields_metadata.field_junction_layer,
    _ogr_layer_relationships.parent_layer,
    _ogr_layer_relationships.parent_pkid,
    _ogr_layer_relationships.child_layer,
    _ogr_layer_relationships.child_pkid

FROM "{schema}"._ogr_fields_metadata

LEFT JOIN "{schema}"._ogr_layer_relationships
    ON _ogr_layer_relationships.parent_element_name = _ogr_fields_metadata.field_name
    AND _ogr_layer_relationships.parent_layer = _ogr_fields_metadata.layer_name

-- Filter by existing columns in current schema
INNER JOIN information_schema.tables
    ON tables.table_schema = '{schema}'
    AND tables.table_name = _ogr_fields_metadata.field_junction_layer

WHERE field_category = 'PATH_TO_CHILD_ELEMENT_WITH_JUNCTION_TABLE';
""".format(schema=schema)
        c = self.con.cursor()
        self._exec_sql(c, sql)
        for (field_junction_layer,
             parent_layer,
             parent_pkid,
             child_layer,
             child_pkid) in c:

            foreign_keys.append(ForeignKey(
                table=field_junction_layer,
                column='parent_pkid',
                referenced_table=parent_layer,
                referenced_column=parent_pkid))

            foreign_keys.append(ForeignKey(
                table=field_junction_layer,
                column='child_pkid',
                referenced_table=child_layer,
                referenced_column=child_pkid))

        return foreign_keys

    def add_foreign_key_constraints(self, schema):
        try:
            for foreign_key in self._foreign_keys(schema):
                self._add_unique_constraint(schema,
                                            foreign_key.referenced_table,
                                            foreign_key.referenced_column)
                self._add_foreign_key_constraint(schema, foreign_key)
            self.con.commit()
        except DbError:
            self.con.rollback()
            raise

    def drop_foreign_key_constraints(self, schema):
        try:
            for foreign_key in self._foreign_keys(schema):
                self._drop_constraint(
                    schema,
                    table=foreign_key.table,
                    constraint=foreign_key.name)
                self._drop_constraint(
                    schema,
                    table=foreign_key.referenced_table,
                    constraint=("{table}_{column}_unique"
                                .format(table=foreign_key.referenced_table,
                                        column=foreign_key.referenced_column)))
            self.con.commit()
        except DbError:
            self.con.rollback()
            raise
