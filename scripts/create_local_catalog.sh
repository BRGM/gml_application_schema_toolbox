#!/bin/sh

# Reads in a list of xsd URI
# Download them in a 'cache' directory
# And outputs a catalog.xml

if [ -z "$1" ]; then
    echo "Arguments: input_xsd_list"
    exit 1
fi

mkdir -p cache
oldp=$(pwd)
cd cache
echo "<?xml version=\"1.0\"?>"
echo "<!DOCTYPE catalog PUBLIC \"-//OASIS//DTD Entity Resolution XML Catalog V1.0//EN\" \"http://www.oasis-open.org/committees/entity/release/1.0/catalog.dtd\">"
echo "<catalog xmlns=\"urn:oasis:names:tc:entity:xmlns:xml:catalog\" prefer=\"public\">"
for f in $(cat ../$1); do
    ff=$(echo $f | sed "s#http://##g")
    d=$(dirname $ff)
    mkdir -p $d
    wget -nc -q -O $ff $f
    echo "<uri name=\"$f\" uri=\"cache/$ff\"/>"
done
echo "</catalog>"
cd $oldp
