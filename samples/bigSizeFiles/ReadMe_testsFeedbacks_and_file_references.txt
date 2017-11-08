GMLAS Driver succesfully tested on 'some' big files

#####
1°/ Grand Lyon (100 MB) CityGML 1.0
https://download.data.grandlyon.com/files/grandlyon/localisation/bati3d/LYON_1ER_2012.zip
 
#####
2°/ 3d geoinformation group - TU Delft - tests
Stelios Vitalis <steliosvitalis@gmail.com> during and after FOSS4G-E 2017 workshop
https://3d.bk.tudelft.nl/svitalis/citygml/gdal/2017/07/24/messing-around-with-citygml-on-gdal-2.2.html
 
Test on open datafiles created by 3d geoinformation group - TU Delft.

Stelios Vitalis: """You may use the files as you want. You can also use this huge file (3,25 GB) which I have used with GDAL trunk and works great:
https://www.dropbox.com/s/l3ssom0pfxy7a6x/3DMassing_2016_MTM3.gml?dl=0
 
The driver scales to enormous sizes. Today, I was messing with a NYC dataset of 31GB (!) and the driver was working (ogr2ogr failed after a few hours when saving to PostGIS due
to my disk getting full, but this is not GDAL's issue).
"""
  
Given 3DMassing_2016_MTM3.gml does not contain xsi:schemaLocation, the file has to be open explictly pointing to the following schemas.
 
-oo XSD=http://schemas.opengis.net/citygml/landuse/2.0/landUse.xsd,http://schemas.opengis.net/citygml/cityfurniture/2.0/cityFurniture.xsd,http://schemas.opengis.net/citygml/texturedsurface/2.0/texturedSurface.xsd,http://schemas.opengis.net/citygml/transportation/2.0/transportation.xsd,http://schemas.opengis.net/citygml/building/2.0/building.xsd,http://schemas.opengis.net/citygml/waterbody/2.0/waterBody.xsd,http://schemas.opengis.net/citygml/relief/2.0/relief.xsd,http://schemas.opengis.net/citygml/vegetation/2.0/vegetation.xsd,http://schemas.opengis.net/citygml/cityobjectgroup/2.0/cityObjectGroup.xsd,http://schemas.opengis.net/citygml/generics/2.0/generics.xsd
 
