ALTER TABLE "{schema}"."{foreign_key.table}"
    ADD CONSTRAINT "{foreign_key.name}"
    FOREIGN KEY ("{foreign_key.column}")
    REFERENCES "{schema}"."{foreign_key.referenced_table}" ("{foreign_key.referenced_column}");
