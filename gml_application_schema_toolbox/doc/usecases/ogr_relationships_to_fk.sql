
CREATE OR REPLACE FUNCTION ogr_add_fk_from_relationships(schema TEXT) 
RETURNS integer AS
$BODY$
DECLARE
    t RECORD;
    r RECORD;
    q TEXT;
    aq TEXT;
BEGIN
    RAISE NOTICE 'Converting OGR relationships to database foreign keys ...';
    FOR t IN 
	SELECT table_schema, table_name
	FROM information_schema.tables
	WHERE table_name = '_ogr_layer_relationships' AND
              table_schema = $1
	ORDER BY table_schema,table_name
    LOOP
            RAISE NOTICE 'Processing %.% ...', t.table_schema, t.table_name;
            q := (
              'SELECT parent_layer, parent_pkid, child_layer, child_pkid '
	      || 'FROM ' || t.table_schema || '.' || t.table_name
            );
	    FOR r IN EXECUTE q
	    LOOP
                BEGIN
		  RAISE NOTICE 'Creating FK on %.%', r.parent_layer, r.parent_pkid;
                  aq := (
		    'ALTER TABLE ' || t.table_schema || '.' || r.parent_layer || 
		    ' ADD CONSTRAINT ' || r.parent_layer || r.parent_pkid || '_uk ' ||
		    ' UNIQUE (' || r.parent_pkid || ')'
		    );
		  EXECUTE aq;
                EXCEPTION WHEN OTHERS THEN
                  RAISE NOTICE '  Constraints already exists.';
                  RAISE NOTICE '  [%] %', SQLSTATE, SQLERRM;
                END;
                -- Create FK
		BEGIN
                  aq := (
		    'ALTER TABLE ' || t.table_schema || '.' || r.child_layer || 
		    ' ADD CONSTRAINT ' || r.parent_layer || r.parent_pkid || 
		    ' FOREIGN KEY (' || r.child_pkid || ') ' || 
		    ' REFERENCES ' || t.table_schema || '.' || r.parent_layer || ' (' || r.parent_pkid || ')'
		  );
		  EXECUTE aq;
                EXCEPTION WHEN OTHERS THEN
                  RAISE NOTICE '  Error during constraint creation. Probably missing element in target table.';
                  RAISE NOTICE '  [%] %', SQLSTATE, SQLERRM;
                END;

	    END LOOP;
    END LOOP;
    RETURN 1;
END
$BODY$
LANGUAGE 'plpgsql' ;


CREATE OR REPLACE FUNCTION ogr_drop_fk_from_relationships(schema TEXT) 
RETURNS integer AS
$BODY$
DECLARE
    t RECORD;
    r RECORD;
    q TEXT;
    aq TEXT;
BEGIN
    RAISE NOTICE 'Converting OGR relationships to database foreign keys ...';
    FOR t IN 
	SELECT table_schema, table_name
	FROM information_schema.tables
	WHERE table_name = '_ogr_layer_relationships' AND
              table_schema = $1
	ORDER BY table_schema,table_name
    LOOP
            RAISE NOTICE 'Processing %.%', t.table_schema, t.table_name;
            q := (
              'SELECT parent_layer, parent_pkid, child_layer, child_pkid '
	      || 'FROM ' || t.table_schema || '.' || t.table_name
            );
	    FOR r IN EXECUTE q
	    LOOP
		RAISE NOTICE 'Drop UK/FK on %.%', r.parent_layer, r.parent_pkid;
		aq := (
		  'ALTER TABLE ' || t.table_schema || '.' || r.child_layer || 
		  ' DROP CONSTRAINT ' || r.parent_layer || r.parent_pkid
		);
		EXECUTE aq;

		aq := (
		  'ALTER TABLE ' || t.table_schema || '.' || r.parent_layer || 
		  ' DROP CONSTRAINT ' || r.parent_layer || r.parent_pkid || '_pk '
		);
		EXECUTE aq;

	    END LOOP;
    END LOOP;
    RETURN 1;
END
$BODY$
LANGUAGE 'plpgsql' ;
