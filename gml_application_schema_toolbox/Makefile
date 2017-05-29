# global

PLUGINNAME = gml_application_schema_toolbox

PY_FILES = main.py __init__.py creation_dialog.py model_dialog.py core/*.py gui/*.py

EXTRAS = Changelog *.svg metadata.txt extlibs gml2relational/*.py gml2relational/testdata/* viewers/*.py viewers/*.svg conf/*.xml logo_oslandia.png

UI_FILES = creation_dialog.ui ui/*.ui

VERSION=$(shell grep "version=" metadata.txt | cut -d'=' -f 2)

%.qm : %.ts
	lrelease $<

# The deploy  target only works on unix like operating system where
# the Python plugin directory is located at:
# $HOME/.qgis2/python/plugins
deploy: transcompile
	mkdir -p $(HOME)/.qgis3/python/plugins/$(PLUGINNAME)
	cp --parents -vfR $(PY_FILES) $(HOME)/.qgis3/python/plugins/$(PLUGINNAME)
	cp --parents -vfR $(UI_FILES) $(HOME)/.qgis3/python/plugins/$(PLUGINNAME)
	cp --parents -vfRa $(EXTRAS) $(HOME)/.qgis3/python/plugins/$(PLUGINNAME)

# The dclean target removes compiled python files from plugin directory
# also delets any .svn entry
dclean:
	find $(HOME)/.qgis3/python/plugins/$(PLUGINNAME) -iname "*.pyc" -delete
	find $(HOME)/.qgis3/python/plugins/$(PLUGINNAME) -iname ".svn" -prune -exec rm -Rf {} \;

# The derase deletes deployed plugin
derase:
	rm -Rf $(HOME)/.qgis3/python/plugins/$(PLUGINNAME)

# The zip target deploys the plugin and creates a zip file with the deployed
# content. You can then upload the zip file on http://plugins.qgis.org
zip: deploy dclean
	echo $(VERSION)
	rm -f $(PLUGINNAME)*.zip
	cd $(HOME)/.qgis3/python/plugins; zip -9r $(CURDIR)/$(PLUGINNAME)-$(VERSION).zip $(PLUGINNAME)

upload: zip
	sed s/_VERSION_/$(VERSION)/g < plugins.xml.tmpl > plugins.xml
	scp plugins.xml hekla:~/brgm_gml
	scp $(PLUGINNAME)-$(VERSION).zip hekla:~/brgm_gml/plugins

# transup
# update .ts translation files
transup:
	pylupdate4 Makefile

# transcompile
# compile translation files into .qm binary format
transcompile: $(TRANSLATIONS:.ts=.qm)

# transclean
# deletes all .qm files
transclean:
	rm -f i18n/*.qm

clean:
	rm $(UI_FILES) $(RESOURCE_FILES)

