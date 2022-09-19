from qgis.core import QgsFieldFormatter
from qgis.gui import (
    QgsEditorConfigWidget,
    QgsEditorWidgetFactory,
    QgsEditorWidgetWrapper,
)
from qgis.PyQt.QtWidgets import QWidget


class XMLCustomWidgetWrapper(QgsEditorWidgetWrapper):
    def __init__(self, vl, fieldIdx, editor, parent):
        super(XMLCustomWidgetWrapper, self).__init__(vl, fieldIdx, editor, parent)
        self._xml_widget = editor

    def createWidget(self, parent):
        self._xml_widget = QWidget(parent)
        self._xml_widget.hide()
        return self._xml_widget

    def value(self):
        return None

    def setValue(self, v):
        pass

    def initWidget(self, editor):
        pass

    def valid(self):
        return isinstance(self._xml_widget, QWidget)


class XMLWidgetConfigDlg(QgsEditorConfigWidget):
    def __init__(self, vl, fieldIdx, parent):
        super(XMLWidgetConfigDlg, self).__init__(vl, fieldIdx, parent)

    def config(self):
        return {}

    def setConfig(self, cfg):
        pass


class XMLWidgetFactory(QgsEditorWidgetFactory):
    def __init__(self):
        super(XMLWidgetFactory, self).__init__("XML")

    def create(self, vl, fieldIdx, editor, parent):
        # QgsVectorLayer* vl, int fieldIdx, QWidget* editor, QWidget* parent
        self.wrapper = XMLCustomWidgetWrapper(vl, fieldIdx, editor, parent)
        return self.wrapper

    def configWidget(self, vl, fieldIdx, parent):
        self.dlg = XMLWidgetConfigDlg(vl, fieldIdx, parent)
        return self.dlg


class XMLWidgetFormatter(QgsFieldFormatter):
    def id(self):
        return "XML"

    def representValue(self, layer, fieldIdx, config, cache, value):
        return "<... XML data ...>"
