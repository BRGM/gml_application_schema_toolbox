# Populate a database created from the XSD model

2 sample datasets are used in this use case:

- Geological Unit
- Environmental Facilities

## Environmental Factilities

- XSD: <http://inspire.ec.europa.eu/schemas/ef/4.0/EnvironmentalMonitoringFacilities.xsd>
- Source dataset: PostGIS

### Load PostGIS dump

```bash
psql -U qgis -W -f poc_gwml2_20161207.sql inspire
```

### Create database structure

```bash
ogr2ogr PG:'host=localhost user=qgis password=qgis dbname=inspire' \
    GMLAS: \
    -f PostgreSQL \
    -oo XSD=http://inspire.ec.europa.eu/schemas/ef/4.0/EnvironmentalMonitoringFacilities.xsd \
    -nlt CONVERT_TO_LINEAR -lco SCHEMA=poc_gwml2_inspire -lco OVERWRITE=YES
```

### Populate database

In this step, we convert original database model to the INSPIRE one.
SQL queries are created to do the conversion. An ETL process could
also be an option.

```sql
INSERT INTO poc_gwml2_inspire.environmentalmonitoringfacility (
ogc_fid, id, identifier, identifier_codespace, location_location_pkid, inspireid_pkid,
representativepoint) SELECT
cid, gml_id, code_bss_sans_slash, 'BSS', gml_id, inspire_id,
geom_wgs84
FROM poc_gwml2.ef_environmentalmonitoringfacility_2;
INSERT INTO poc_gwml2_inspire.environmentalmonitoringfacility_ef_name (
ogc_fid, ogr_pkid, parent_id, value) SELECT
cid, cid, cid, libelle
FROM poc_gwml2.ef_environmentalmonitoringfacility_2 WHERE libelle is not null;
```

### Export to GML

```bash
ogr2ogr -f GMLAS ef.gml PG:'host=localhost user=qgis password=qgis dbname=inspire' \
      environmentalmonitoringfacility
```

---

## Geological Unit

- XSD: <http://inspire.ec.europa.eu/schemas/ge-core/3.0/GeologyCore.xsd>
- Source dataset format: PostGIS

### Create ge-core schema in PostGIS

#### Create database structure

```bash
$ ogr2ogr PG:'host=localhost user=qgis password=qgis dbname=inspire' GMLAS: -f PostgreSQL -oo XSD=http://inspire.ec.europa.eu/schemas/ge-core/3.0/GeologyCore.xsd -nlt MULTIPOLYGON -lco SCHEMA=ge-core -lco OVERWRITE=YES
856 tables created
```

#### Populate database

Copy of data from “ge” schema into “ge-core”

List of updated tables :

- Geologicevent
- Geologicevent_eventprocess
- Geologichistory
- Geologicunit
- Geologicunit_composition
- Geologicunit_geologichistory_geologichistory
- Inspireid
- Quantityrange

In this step, we convert original database model to the INSPIRE one.
SQL queries are created to do the conversion. An ETL process could
also be an option.

```sql
-- geologicunit
INSERT INTO "ge-core".geologicunit(ogc_fid, id, description, identifier_codespace, identifier, inspireid_pkid, name, geologicunittype_href, geologicunittype_title)
SELECT ogc_fid, id, description, identifier_codespace, identifier, inspireid_pkid, name, geologicunittype_href, geologicunittype_title FROM "ge".geologicunit

-- geologicunit_composition
/!\ Dans ge-core : parent_id alors que dans ge : parent_ogr_pkid
INSERT INTO "ge-core".geologicunit_composition(ogc_fid, ogr_pkid, parent_id, compositionpart_material_href, compositionpart_material_title, compositionpart_proportion_quantityrange_pkid, compositionpart_role_href, compositionpart_role_title)
SELECT ogc_fid, ogr_pkid, parent_ogr_pkid, compositionpart_material_href, compositionpart_material_title, compositionpart_proportion_quantityrange_pkid, compositionpart_role_href, compositionpart_role_title
FROM "ge".geologicunit_composition

-- geologicevent
INSERT INTO "ge-core".geologicevent(ogc_fid, id, eventenvironment_href, eventenvironment_title, oldernamedage_href, oldernamedage_title, youngernamedage_href, youngernamedage_title)
SELECT ogc_fid, id, eventenvironment_href, eventenvironment_title, oldernamedage_href, oldernamedage_title, youngernamedage_href, youngernamedage_title
FROM "ge".geologicevent

-- geologicevent_eventprocess
INSERT INTO "ge-core".geologicevent_eventprocess(ogc_fid, ogr_pkid, parent_id, href, title)
SELECT ogc_fid, ogr_pkid, parent_ogr_pkid, href, title
FROM "ge".geologicevent_eventprocess

-- geologichistory
INSERT INTO "ge-core".geologichistory(ogc_fid, ogr_pkid, geologicevent_pkid)

SELECT ogc_fid, ogr_pkid, geologicevent_pkid
FROM "ge".geologichistory

-- geologicunit_geologichistory_geologichistory;
INSERT INTO "ge-core".geologicunit_geologichistory_geologichistory(ogc_fid, occurrence, parent_pkid, child_pkid)
SELECT ogc_fid, occurrence, parent_pkid, child_pkid
FROM "ge".geologicunit_geologichistory_geologichistory

-- inspireid;
 INSERT INTO "ge-core".inspireid(ogc_fid, ogr_pkid, identifier_localid, identifier_namespace)
SELECT ogc_fid, ogr_pkid, identifier_localid, identifier_namespace
FROM "ge".inspireid

 -- quantityrange
INSERT INTO "ge-core".quantityrange(ogc_fid, ogr_pkid, uom_code, uom_href, uom_title, value)
SELECT ogc_fid, ogr_pkid, uom_code, uom_href, uom_title, value
FROM "ge".quantityrange
```

Comments:

- In geologicunit_composition table :
  - parent_id column in ge schema <> parent_ogr_pkid in ge-core schema
- Necessary adjustments to do to get a proper result:
  - Geologicunit_composition: parent_id must be equal to geologicunit.id
  - Geologicunit_geologichistory_geologichistory: parent_id must be equal to geologicunit.id
  - Geologicevent_eventprocess: parent_id must be equal to geologicevent.id
  - Geologichistory: geologiceventpkid must be equal to geologicevent.id

### Export to GML

```bash
ogr2ogr -f GMLAS geolunit2.gml \
   PG:'host=localhost user=qgis password=qgis dbname=inspire' \
   geologicunit \
   -oo ACTIVE_SCHEMA=ge-core \
   -dsco INPUT_XSD=http://inspire.ec.europa.eu/schemas/ge-core/3.0/GeologyCore.xsd
```
