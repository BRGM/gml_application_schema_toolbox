class Link:
    """A Link represents a link to another type/table"""

    def __init__(self, name, optional, min_occurs, max_occurs, ref_type, ref_table = None, substitution_group = None):
        self.__name = name
        self.__optional = optional
        self.__min_occurs = min_occurs
        self.__max_occurs = max_occurs
        self.__ref_type = ref_type # SQL type (str)
        self.__ref_table = ref_table # Table
        self.__substitution_group = substitution_group # for element that derives from a common element

    def name(self):
        return self.__name
    def ref_type(self):
        return self.__ref_type
    def ref_table(self):
        return self.__ref_table
    def set_ref_table(self, ref_table):
        self.__ref_table = ref_table
    def optional(self):
        return self.__optional
    def min_occurs(self):
        return self.__min_occurs
    def max_occurs(self):
        return self.__max_occurs
    def substitution_group(self):
        return self.__substitution_group

    def __repr__(self):
        return "Link<{}({}-{}){}>".format(self.name(), self.min_occurs(),
                                          "*" if self.max_occurs() is None else self.max_occurs(),
                                          "" if self.ref_table() is None else " " + self.ref_table().name())

class BackLink:
    """A BackLink represents a foreign key relationship"""

    def __init__(self, name, ref_table):
        self.__name = name
        self.__ref_table = ref_table

    def name(self):
        return self.__name
    def ref_table(self):
        return self.__ref_table

    def __repr__(self):
        return "BackLink<{}({})>".format(self.name(), self.ref_table().name())

class Column:
    """A Column is a (simple type) column"""

    def __init__(self, name, optional = False, ref_type = None, auto_incremented = False):
        self.__name = name
        self.__optional = optional
        self.__ref_type = ref_type
        self.__auto_incremented = auto_incremented

    def name(self):
        return self.__name
    def ref_type(self):
        return self.__ref_type
    def optional(self):
        return self.__optional
    def auto_incremented(self):
        return self.__auto_incremented

    def __repr__(self):
        return "Column<{}{}>".format(self.__name, " optional" if self.__optional else "")

class Geometry:
    """A geometry column"""

    def __init__(self, name, type, dim, srid, optional = False):
        self.__name = name
        self.__type = type
        self.__dim = dim
        self.__srid = srid
        self.__optional = optional

    def name(self):
        return self.__name
    def type(self):
        return self.__type
    def dimension(self):
        return self.__dim
    def srid(self):
        return self.__srid
    def optional(self):
        return self.__optional
    def __repr__(self):
        return "Geometry<{} {}{}({}){}>".format(self.name(), self.type(), "Z" if self.dimension() == 3 else "", self.srid(), " optional" if self.__optional else "")

class Table:
    """A Table is a list of Columns or Links to other tables, a list of geometry columns and an id"""

    def __init__(self, name = '', fields = [], uid = None):
        self.__name = name
        self.__fields = {}
        for f in fields:
            self.__fields[f.name()] = f
        # uid column
        self.__uid_column = uid
        # last value for autoincremented id
        # A Table must have either a uid column or a autoincremented id
        # but not both
        self.__last_uid = None

    def name(self):
        return self.__name
    def set_name(self, name):
        self.__name = name
    def fields(self):
        return self.__fields
    def add_field(self, field):
        if self.__fields.has_key(field.name()):
            raise RuntimeError("add_field {} already existing".format(field.name()))
        self.__fields[field.name()] = field
    def add_fields(self, fields):
        for f in fields:
            self.add_field(f)
    def has_field(self, field_name):
        return self.__fields.has_key(field_name)
    def field(self, field_name):
        return self.__fields.get(field_name)
    
    def links(self):
        return [x for k, x in self.fields().iteritems() if isinstance(x, Link)]
    def columns(self):
        return [x for k, x in self.fields().iteritems() if isinstance(x, Column)]
    def geometries(self):
        return [x for k, x in self.fields().iteritems() if isinstance(x, Geometry)]
    def back_links(self):
        return [x for k, x in self.fields().iteritems() if isinstance(x, BackLink)]

    def uid_column(self):
        return self.__uid_column
    def set_uid_column(self, uid_column):
        self.__uid_column = uid_column

    def has_autoincrement_id(self):
        return self.__last_uid is not None
    def set_autoincrement_id(self):
        self.__uid_column = Column("id", auto_incremented = True)
        self.__fields['id'] = self.__uid_column
        self.__last_uid = 0
    def increment_id(self):
        self.__last_uid += 1
        return self.__last_uid
        
    def add_back_link(self, name, table):
        f = [x for x in table.back_links() if x.name() == name and x.table() == table]
        if len(f) == 0:
            self.__fields[name] = BackLink(name, table)
