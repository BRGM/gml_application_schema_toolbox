# XML Mode - Content negociation test scenario

This scenario uses URI as opposed to files stored on GitHub thus involves content negociation with data servers

## 1. Set up project and make some checks

Same steps 1 to 4 as for the [XML Mode - Local test scenario](scenario_mode_xml_local)

## 2. dereferencing another Feature (a GroundWater Quantity Monitoring Facility)

Same steps as for the "XML Mode - Local test scenario"
TODO SG : tweak the resolver conf to make this work

## 3. from the Monitoring facility access groundwater observation

Step skipped for now as contrary to the "XML Mode - Local test scenario", the payload describing the GroundWater Quantity Monitoring Facility served via the URI does not provide a reference to a SOS XML endpoint anymore (SensorThings API instead)

## 4. from the Monitoring Facility add the GroundWater ressource monitored

Same steps as for the "XML Mode - Local test scenario"

## 5. interrogate the GroundWater ressource monitored

Same steps as for the "XML Mode - Local test scenario"
