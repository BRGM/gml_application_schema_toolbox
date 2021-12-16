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
    QgsProcessing,
    QgsProcessingException,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterDefinition,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterString,
    QgsProcessingParameterVectorDestination,
)


class ogr2ogr_3_24(GdalAlgorithm):
    INPUT = "INPUT"
    CONVERT_ALL_LAYERS = "CONVERT_ALL_LAYERS"
    OPTIONS = "OPTIONS"
    OUTPUT = "OUTPUT"

    def __init__(self):
        super().__init__()

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT, self.tr("Input layer"), types=[QgsProcessing.TypeVector]
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
        ogrLayer, layerName = self.getOgrCompatibleSource(
            self.INPUT, parameters, context, feedback, executing
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
