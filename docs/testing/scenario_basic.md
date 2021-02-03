# Basic scenarios

## XML Mode - local test scenario

This scenario uses files stored on GitHub to avoid potential content negociation issues (network issues) with data servers

1. add a WMS background image

   Whatever suits you, provided the entire world is visible (will help detect X/Y Axis being flipped :) )

2. initial information seed
   <https://raw.githubusercontent.com/BRGM/gml_application_schema_toolbox/master/tests/basic_test_scenario/0_BoreholeView.xml>

   Load wizard > 'File/Url' > Load in XML Mode > XML Options : None > expected result : 1 new QGIS layer (BoreholeView (shape))

   ![information_seed_displayed](../static/img/testing/1.information_seed_displayed.PNG)

   Then QGIS 'Identify Features' on the point added ->  expected result : features attributes from the GML SHALL be displayed

3. dereferencing vocabulary
    * on INSPIRE registry
  
    `gsmlp:purpose/@xlink:href` (right click) > `Resolve external` > `Embedded` -> expected result : the content of the attribute SHALL be enriched with content coming from the INSPIRE registry ![INSPIRE-registry-response](../static/img/testing/2.de_rereferencing_vocabulary_filled.PNG)

    * on OGC definition server
    proceed as above on attributes having xlink:href starting with <http://www.opengis.net/def/>...

    * on EU geological surveys linked data registry
    proceed as above on attributes having  @xlink:href starting with <http://data.geoscience.earth/ncl/>...

4. dereferencing a 1st feature (a geological log )
    gsmlp:geologicalDescription/@xlink:href > (right click) 'Resolve external' > 'Embedded' -> expected result : the content of the attribute SHALL be enriched with sos:observationData.
    Open one of them and expand the om:OM_Observation then the om:result -> the Geology log viewer icon SHALL be proposed
    
    ![sos:observationData](../static/img/testing/3.sos_observationData.PNG)
    
    Clicking on the icon next to GW_GeologyLog SHALL launch the Geology log viewer (preconfigured to render OGC:GroundWaterML2.0 GeologyLogCoverage compliant content)
    
    ![GeologyLogViewer](../static/img/testing/3.Geology_log_viewer.PNG)

5. dereferencing another Feature (a GroundWater Quantity Monitoring Facility) 
    gsmlp:groundWaterLevel/@xlink:href > (right click) 'Resolve external' > 'As a new Layer' (ticking 'Swap X/Y) -> expected result : two new QGIS layers  (EnvironmentalMonitoringFacility (geometry) and EnvironmentalMonitoringFacility (representativePoint))

    QGIS 'Identify Features' on one of them -> expected result : features attributes from the GML SHALL be displayed

6. from the Monitoring facility access groundwater observation
    dereferencing hasObservation (the one which title is "6512X0037 groundwater quantity observation collection (SOS and WaterML 2.0 format)")
    ef:hasObservation/@xlink:href > (right click ) 'Resolve external' > 'Embedded' -> expected result : the content of the attribute SHALL be enriched with sos:GetObservationResponse

    Expending the om:OM_Observation then the om:result -> the Timeseries viewer icon SHALL be proposed

    ![sos:GetObservationResponse](../static/img/testing/5_sos_GetObservationResponse.PNG)
 
    Clicking on the icon next to wml2:MeasurementTimeseries SHALL launch the TimeSeries viewer (preconfigured to render OGC:WaterML2.0 Part 1 Timeseries compliant content)

    ![Timeseries_viewer](../static/img/testing/5.Timeseries_viewer.PNG)
  
7. from the Monitoring Facility add the GroundWater ressource monitored 
   ef:observingCapability/ef:ObservingCapability/ef:ultimateFeatureOfInterest/xlink@href > (right click) 'Resolve external' > 'As a new Layer' -> expected result : 1 new QGIS layer GW_ConfiningBed (shape).

   Position it under the other features using the 'Layers Panel' for better visibility

   ![GWML2_ressource](../static/img/testing/6.GWML2_ressource_added.PNG)

   
8. interrogate the GroundWater ressource monitored 
   Then QGIS 'Identify Features' on the point added ->  expected result : features attributes from the GML SHALL be displayed according to OGC GWML2 Model

## Relational mode (GMLAS) scenario - Local test scenario

This scenario uses files stored on GitHub to avoid potential content negociation issues (network issues) with data servers

1. add a WMS background image

   Whatever suits you, provided the entire world is visible (will help detect X/Y Axis being flipped :) )

2. initial information seed
   <https://raw.githubusercontent.com/BRGM/gml_application_schema_toolbox/master/tests/basic_test_scenario/0_BoreholeView.xml>

   Load wizard > 'File/Url' > Load in relational mode (GMLAS)  > GMLAS Options
   - all default options EXCEPT
   - "Load layer list' : click and keep both 'boreholeview' and 'boreholeview_name'
   - Target database > SQLite (write mode : Create)
   ![GMLAS-Load-layer-list](../static/img/testing/1.GMLAS_load_layer.PNG)

   Expected result :  1 new QGIS layer (boreholeview) and 1 table

   ![information_seed_displayed](../static/img/testing/1.GMLAS_information_seed_displayed.PNG)

   Then QGIS 'Identify Features' on the point added ->  expected result : features attributes from the GML SHALL be displayed

3. dereferencing vocabulary
    * on INSPIRE registry
  
    `gsmlp:purpose/@xlink:href` ('Load' button click) > 'Options for xlink:href loading'
    - all default options EXCEPT
    - "Load layer list' : click and keep all
    - Target database > SQLite > same database as the one created in step 1 (write mode : Append)
    
    Expected results:
   - the content of the created database SHALL be enriched with content coming from the INSPIRE registry
    ![GMLAS-INSPIRE-registry-response](../static/img/testing/2.GMLAS_de_rereferencing_vocabulary_filled.PNG)
   - the Layer list SHALL be enriched with the new tables created from the import
   ![GMLAS-INSPIRE-registry-response_in_TOC](../static/img/testing/2.GMLAS_de_rereferencing_vocabulary_filled_and_displayed.PNG)
  
    * on OGC definition server
    proceed as above on attributes having xlink:href starting with <http://www.opengis.net/def/>...

    * on EU geological surveys linked data registry
    proceed as above on attributes having  @xlink:href starting with <http://data.geoscience.earth/ncl/>...

4. dereferencing a 1st feature (a geological log )
    gsmlp:geologicalDescription/@xlink:href >  ('Load' button click) > 'Options for xlink:href loading'
     - all default options EXCEPT
     - "Load layer list' : click and keep all
     - Target database > SQLite > same database as the one created in step 1 (write mode : Append)
     ![GMLAS-GeologyLog-Load-layer list](../static/img/testing/3.GMLAS_Geology_log_load_layer.PNG)

    
    Expected results:
   - the content of the created database SHALL be enriched with content of the geological log description
    ![GMLAS-GeologyLog-response](../static/img/testing/3.GMLAS_Geology_log_filled.PNG)
   - the Layer list SHALL be enriched with the new tables created from the import of the geological log description
   ![GMLAS-GeologyLog-response_in_TOC](../static/img/testing/3.GMLAS_Geology_log_filled_and_displayed.PNG)

   TODO SG : check whether it's normal with the current status of the dev that the LogViewer widget is not proposed in the GUI (1st compare with what happens for the TimeSeries viewer)

5. dereferencing another Feature (a GroundWater Quantity Monitoring Facility) 
    TODO SG : 
      - crashed under 3.10.13 when loading layers at the time of writing
      - add a 

6.  access groundwater observation
    workaround while point 5. is blocked
    
    On the following URL : <https://raw.githubusercontent.com/BRGM/gml_application_schema_toolbox/master/tests/basic_test_scenario/4_SOS_TimeSeries.xml>

   Load wizard > 'File/Url' > Load in relational mode (GMLAS)  > GMLAS Options
   - all default options EXCEPT
   - "Load layer list' : click and keep all
   - Target database > SQLite (write mode : Create)
   ![GMLAS-Load-layer-list-Time-Series](../static/img/testing/5.SOS_TimeSeries_load_layer.PNG)

   Expected result : 8 tables added in the Layer List
   - the content of the created database SHALL be enriched with content of the TimeSeries
    ![GMLAS-TimeSeries-response](../static/img/testing/5.SOS_TimeSeries_filled.PNG)
   - the Layer list SHALL be enriched with the new tables created from the import of the TimeSeries 
   ![GMLAS-TimeSeries-response_in_TOC](../static/img/testing/5.SOS_TimeSeries_filled_and_displayed.PNG)

   TODO SG : check why the TimeSeries viewer is not displayed

7. access  the GroundWater ressource monitored 
   workaround while point 5. is blocked

   On the following URL : <https://raw.githubusercontent.com/BRGM/gml_application_schema_toolbox/master/tests/basic_test_scenario/5_HydroGeoUnit.xml>

   Load wizard > 'File/Url' > Load in relational mode (GMLAS)  > GMLAS Options
   - all default options EXCEPT
   - "Load layer list' : click and keep all
   - Target database > SQLite (write mode : Create)
   ![GMLAS-Load-layer-list-HydroGeoUnit](../static/img/testing/6.GMLAS_HydroGeoUnit_load_layer.PNG)

   Expected result : 8 tables added in the Layer List
   - the content of the created database SHALL be enriched with content decribing the GroundWater ressource
    ![GMLAS-HydroGeoUnit-response](../static/img/testing/6.GMLAS_GWML2_filled.PNG)
   - the Layer list SHALL be enriched with the new tables created from the import of the TimeSeries 
   ![GMLAS-HydroGeoUnit-response_in_TOC](../static/img/testing/6.GMLAS_GWML2_filled_and_displayed.PNG)


### XML Mode - Content negociation test scenario

This scenario uses URI as opposed to files stored on GitHub thus involves content negociation with data servers

1. add a WMS background image
   
   Same as for the "XML Mode - Local test scenario"

2. initial information seed
   https://forge.brgm.fr/svnrepository/epos/trunk/instances/BoreholeView.xml

   Same steps as for the "XML Mode - Local test scenario"
   

3. dereferencing vocabulary

    Same steps as for the "XML Mode - Local test scenario"


4. dereferencing a 1st feature (a geological log )

   Same steps as for the "XML Mode - Local test scenario"

5. dereferencing another Feature (a GroundWater Quantity Monitoring Facility) 

   Same steps as for the "XML Mode - Local test scenario"
   TODO SG : tweak the resolver conf to make this work

6. from the Monitoring facility access groundwater observation

   Step skipped for now as contrary to the "XML Mode - Local test scenario", the payload describing the GroundWater Quantity Monitoring Facility served via the URI does not provide a reference to a SOS XML endpoint anymore (SensorThings API instead)

7. from the Monitoring Facility add the GroundWater ressource monitored 
   
   Same steps as for the "XML Mode - Local test scenario"
   
8. interrogate the GroundWater ressource monitored 
   
   Same steps as for the "XML Mode - Local test scenario"
