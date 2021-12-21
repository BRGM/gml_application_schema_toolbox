"""
Customization of ogr2ogr processing to allow use convert format algortihm for GMLAS purposes.
See https://github.com/BRGM/gml_application_schema_toolbox/issues/187

This processing is used in GMLAS plugin and rougthly backported from QGIS 3.24
See https://github.com/qgis/QGIS/pull/45955
"""

__author__ = "Victor Olaya"
__date__ = "November 2012"
__copyright__ = "(C) 2012, Victor Olaya"

import os

from processing.algs.gdal.GdalAlgorithm import GdalAlgorithm
from processing.algs.gdal.GdalUtils import GdalUtils
from qgis.core import (
    QgsDataSourceUri,
    QgsProcessing,
    QgsProcessingException,
    QgsProcessingFeatureSourceDefinition,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterDefinition,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFile,
    QgsProcessingParameterString,
    QgsProcessingParameterVectorDestination,
    QgsProviderRegistry,
    QgsVectorFileWriter,
)


class ogr2ogr_3_24(GdalAlgorithm):
    INPUT = "INPUT"
    INPUT_FILE = "INPUT_FILE"
    CONVERT_ALL_LAYERS = "CONVERT_ALL_LAYERS"
    OPTIONS = "OPTIONS"
    OUTPUT = "OUTPUT"

    def __init__(self):
        super().__init__()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr("Input layer"),
                types=[QgsProcessing.TypeVector],
                optional=True,
            )
        )
        self.addParameter(
            QgsProcessingParameterFile(
                self.INPUT_FILE, self.tr("Input file"), optional=True
            )
        )
        convert_all_layers_param = QgsProcessingParameterBoolean(
            self.CONVERT_ALL_LAYERS,
            self.tr("Convert all layers from dataset"),
            defaultValue=False,
        )
        convert_all_layers_param.setHelp(
            self.tr(
                "Use convert all layers to convert a whole dataset. "
                "Supported output formats for this option are GPKG and GML."
            )
        )
        self.addParameter(convert_all_layers_param)

        options_param = QgsProcessingParameterString(
            self.OPTIONS,
            self.tr("Additional creation options"),
            defaultValue="",
            optional=True,
        )
        options_param.setFlags(
            options_param.flags() | QgsProcessingParameterDefinition.FlagAdvanced
        )
        self.addParameter(options_param)

        self.addParameter(
            QgsProcessingParameterVectorDestination(self.OUTPUT, self.tr("Converted"))
        )

    def name(self):
        return "convertformat_gmlas"

    def displayName(self):
        return self.tr("Convert format (Custom for GMLAS)")

    def group(self):
        pass

    def groupId(self):
        pass

    def commandName(self):
        pass

    def getConsoleCommands(self, parameters, context, feedback, executing=True):
        if self.INPUT in parameters and parameters[self.INPUT] is not None:
            ogrLayer, layerName = self.getOgrCompatibleSource(
                self.INPUT, parameters, context, feedback, executing
            )
        elif self.INPUT_FILE in parameters and parameters[self.INPUT_FILE] is not None:
            ogrLayer, layerName = self.getOgrCompatibleSource(
                self.INPUT_FILE, parameters, context, feedback, executing
            )
        convertAllLayers = self.parameterAsBoolean(
            parameters, self.CONVERT_ALL_LAYERS, context
        )
        options = self.parameterAsString(parameters, self.OPTIONS, context)
        outFile = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        self.setOutputValue(self.OUTPUT, outFile)

        output, outputFormat = GdalUtils.ogrConnectionStringAndFormat(outFile, context)

        if outputFormat in ("SQLite", "GPKG") and os.path.isfile(output):
            raise QgsProcessingException(
                self.tr('Output file "{}" already exists.'.format(output))
            )

        arguments = []
        # if outputFormat:
        #     arguments.append('-f {}'.format(outputFormat))

        if options:
            arguments.append(options)

        arguments.append(output)
        arguments.append(ogrLayer)
        if not convertAllLayers:
            arguments.append(layerName)

        return ["ogr2ogr", GdalUtils.escapeAndJoin(arguments)]

    def getOgrCompatibleSource(
        self, parameter_name, parameters, context, feedback, executing
    ):
        """
        Interprets a parameter as an OGR compatible source and layer name
        :param executing:
        """
        if (
            not executing
            and parameter_name in parameters
            and isinstance(
                parameters[parameter_name], QgsProcessingFeatureSourceDefinition
            )
        ):
            # if not executing, then we throw away all 'selected features only' settings
            # since these have no meaning for command line gdal use, and we don't want to force
            # an export of selected features only to a temporary file just to show the command!
            parameters = {parameter_name: parameters[parameter_name].source}

        if parameter_name == "INPUT_FILE":
            return self.parameterAsFile(parameters, parameter_name, context), None

        input_layer = self.parameterAsVectorLayer(parameters, parameter_name, context)
        ogr_data_path = None
        ogr_layer_name = None
        if input_layer is None or input_layer.dataProvider().name() == "memory":
            if executing:
                # parameter is not a vector layer - try to convert to a source compatible with OGR
                # and extract selection if required
                ogr_data_path = self.parameterAsCompatibleSourceLayerPath(
                    parameters,
                    parameter_name,
                    context,
                    QgsVectorFileWriter.supportedFormatExtensions(),
                    QgsVectorFileWriter.supportedFormatExtensions()[0],
                    feedback=feedback,
                )
                ogr_layer_name = GdalUtils.ogrLayerName(ogr_data_path)
            else:
                # not executing - don't waste time converting incompatible sources, just return dummy strings
                # for the command preview (since the source isn't compatible with OGR, it has no meaning anyway and can't
                # be run directly in the command line)
                ogr_data_path = "path_to_data_file"
                ogr_layer_name = "layer_name"
        elif input_layer.dataProvider().name() == "ogr":
            if (
                executing
                and (
                    isinstance(
                        parameters[parameter_name], QgsProcessingFeatureSourceDefinition
                    )
                    and parameters[parameter_name].selectedFeaturesOnly
                )
                or input_layer.subsetString()
            ):
                # parameter is a vector layer, with OGR data provider
                # so extract selection if required
                ogr_data_path = self.parameterAsCompatibleSourceLayerPath(
                    parameters,
                    parameter_name,
                    context,
                    QgsVectorFileWriter.supportedFormatExtensions(),
                    feedback=feedback,
                )
                parts = QgsProviderRegistry.instance().decodeUri("ogr", ogr_data_path)
                ogr_data_path = parts["path"]
                if "layerName" in parts and parts["layerName"]:
                    ogr_layer_name = parts["layerName"]
                else:
                    ogr_layer_name = GdalUtils.ogrLayerName(ogr_data_path)
            else:
                # either not using the selection, or
                # not executing - don't worry about 'selected features only' handling. It has no meaning
                # for the command line preview since it has no meaning outside of a QGIS session!
                ogr_data_path = GdalUtils.ogrConnectionStringAndFormatFromLayer(
                    input_layer
                )[0]
                ogr_layer_name = GdalUtils.ogrLayerName(
                    input_layer.dataProvider().dataSourceUri()
                )
        elif input_layer.dataProvider().name().lower() == "wfs":
            uri = QgsDataSourceUri(input_layer.source())
            baseUrl = uri.param("url").split("?")[0]
            ogr_data_path = "WFS:{}".format(baseUrl)
            ogr_layer_name = uri.param("typename")
        else:
            # vector layer, but not OGR - get OGR compatible path
            # TODO - handle "selected features only" mode!!
            ogr_data_path = GdalUtils.ogrConnectionStringFromLayer(input_layer)
            ogr_layer_name = GdalUtils.ogrLayerName(
                input_layer.dataProvider().dataSourceUri()
            )
        return ogr_data_path, ogr_layer_name

    def shortHelpString(self):
        return self.tr(
            "The algorithm converts simple features data between file formats.\n\n"
            "Use convert all layers to convert a whole dataset.\n"
            "Supported output formats for this option are:\n"
            "- GPKG\n"
            "- GML\n"
            "This processing is used in GMLAS plugin and rougthly backported from QGIS 3.24\n"
            "See https://github.com/qgis/QGIS/pull/45955"
        )
