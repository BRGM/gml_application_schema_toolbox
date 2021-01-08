# Local test - Basic scenario
This scenario uses files stored on GitHub to avoid potential content negociation issues (network issues) with data servers
# Local test - Complete scenario
This scenario uses files stored on GitHub to avoid potential content negociation issues (network issues) with data servers
# Content negociation scenario
This scenario uses URI as opposed to files stored on GitHub thus involves content negociation with data servers
## XML Mode
0. add a WMS background image

   Whatever suits you, provided the entire world is visible (will help detect X/Y Axis being flipped :) )

1. initial information seed
   https://forge.brgm.fr/svnrepository/epos/trunk/instances/BoreholeView.xml
   TODO SG add screenshot

   Load wizard > 'File/Url' > Load in XML Mode

   XML Options : None 

   Then QGIS 'Identify Features' on the point added ->  expected result : features attributes from the GML SHALL be displayed

2. dereferencing vocabulary
    * on INSPIRE registry
  
    gsmlp:purpose/@xlink:href > (right click) 'Resolve external' > 'Embedded' -> expected result : the content of the attribute SHALL be enriched with content coming from the INSPIRE registry ![INSPIRE-registry-response](../static/img/testing/2.de_rereferencing_vocabulary_filled.PNG)

    * on OGC definition server
    proceed as above on attributes having xlink:href starting with http://www.opengis.net/def/...

    * on EU geological surveys linked data registry
    proceed as above on attributes having  @xlink:href starting with http://data.geoscience.earth/ncl/...


3. dereferencing a 1st feature (a geological log )
    gsmlp:geologicalDescription/@xlink:href > (right click) 'Resolve external' > 'Embedded' -> expected result : the content of the attribute SHALL be enriched with sos:observationData.
    Open one of them and expand the om:OM_Observation then the om:result -> the Geology log viewer icon SHALL be proposed
    
    ![sos:observationData](../static/img/testing/3.sos_observationData.PNG)
    
    Clicking on the icon SHALL launch the viewer 
    
    ![sos:GeologyLogViewer](../static/img/testing/3.Geology_log_viewer.PNG)

4. dereferencing another Feature (a GroundWater Quantity Monitoring Facility) 
    gsmlp:groundWaterLevel/@xlink:href > (right click) 'Resolve external' > 'As a new Layer' (ticking 'Swap X/Y) -> expected result : two new QGIS layers  (EnvironmentalMonitoringFacility (geometry) and EnvironmentalMonitoringFacility (representativePoint))

    QGIS 'Identify Features' on one of them -> expected result : features attributes from the GML SHALL be displayed

5. from the Monitoring facility access groundwater observation
    dereferencing hasObservation WML2 (http://ressource.brgm-rec.fr/obs/RawOfferingPiezo/06512X0037/STREMY.2&responseFormat=http://www.opengis.net/waterml/2.0) - testing TimeSeries widget 

6. from the Monitoring Facility add the GroundWater ressource monitored 
   ef:observingCapability/ef:ObservingCapability/ef:ultimateFeatureOfInterest/xlink@href > (right click) 'Resolve external' > 'As a new Layer' -> expected result : 1 new QGIS layer GW_ConfiningBed (shape) 
   
7. interrogate the GroundWater ressource monitored 
   Then QGIS 'Identify Features' on the point added ->  expected result : features attributes from the GML SHALL be displayed according to OGC GWML2 Model
