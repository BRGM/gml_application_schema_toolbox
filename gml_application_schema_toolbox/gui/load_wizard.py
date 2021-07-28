#! python3  # noqa: E265

# ############################################################################
# ########## Imports ###############
# ##################################

# Standard library
import os
from tempfile import NamedTemporaryFile

# PyQGIS
from qgis.PyQt import uic
from qgis.PyQt.QtCore import pyqtSlot
from qgis.PyQt.QtWidgets import QFileDialog, QVBoxLayout, QWizard, QWizardPage

# project
from gml_application_schema_toolbox.gui.import_gmlas_panel import ImportGmlasPanel
from gml_application_schema_toolbox.gui.load_wizard_wfs import LoadWizardWFS
from gml_application_schema_toolbox.gui.load_wizard_xml import LoadWizardXML
from gml_application_schema_toolbox.gui.wait_cursor_context import WaitCursor
from gml_application_schema_toolbox.toolbelt import PlgLogger, PlgOptionsManager
from gml_application_schema_toolbox.toolbelt.file_downloader import get_from_http

# ############################################################################
# ########## Globals ###############
# ##################################

PAGE_1_W, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "..", "ui", "load_wizard_data_source.ui")
)

PAGE_2_W, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "..", "ui", "load_wizard_load.ui")
)

PAGE_ID_DATA_SOURCE = 0
PAGE_ID_GMLAS = 4
PAGE_ID_LOADING = 2
PAGE_ID_WFS = 1
PAGE_ID_XML = 3


# ############################################################################
# ########## Classes ###############
# ##################################


class LoadWizardDataSource(QWizardPage, PAGE_1_W):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.log = PlgLogger().log
        self.setupUi(self)
        self.plg_settings_mngr = PlgOptionsManager()
        self.plg_settings = self.plg_settings_mngr.get_plg_settings()

        # set last choosen source
        last_source = self.plg_settings.last_source
        self.sourceFromWFS.setChecked(last_source == "wfs")
        self.sourceFromFile.setChecked(last_source == "file")

        self.gmlPathLineEdit.setText(
            self.plg_settings.last_file or self.plg_settings.last_path
        )
        if __debug__:
            self.log(message=f"DEBUG {__name__} loaded.", log_level=5)

    def nextId(self):
        if self.sourceFromWFS.isChecked():
            return PAGE_ID_WFS
        return PAGE_ID_LOADING

    def validatePage(self):
        self.plg_settings_mngr.set_value_from_key(
            key="last_source", value="wfs" if self.sourceFromWFS.isChecked() else "file"
        )
        self.plg_settings_mngr.set_value_from_key(
            key="last_file", value=self.gmlPathLineEdit.text()
        )
        return super().validatePage()

    @pyqtSlot()
    def on_gmlPathButton_clicked(self):
        gml_path = self.plg_settings.last_file or self.plg_settings.last_path

        filepath, suffix_filter = QFileDialog.getOpenFileName(
            parent=self,
            caption=self.tr("Open GML file"),
            directory=gml_path,
            filter=self.tr("GML files or XSD (*.gml *.xml *.xsd)"),
        )
        if filepath:
            self.plg_settings_mngr.set_value_from_key(
                key="last_path", value=os.path.dirname(filepath)
            )
            self.plg_settings_mngr.set_value_from_key(key="last_file", value=filepath)

            self.gmlPathLineEdit.setText(filepath)

    def download(self, output_path: str):
        """Download (if gmlPath is a HTTP URL) or copy a local file to tha output path.

        :param output_path: output filepath
        :type output_path: str
        """
        input_path = self.gmlPathLineEdit.text()
        if input_path.startswith("http://") or input_path.startswith("https://"):
            # URL
            get_from_http(uri=input_path, output_path=output_path)
        else:
            # copy file
            with open(input_path, "rb") as inp:
                with open(output_path, "wb") as out:
                    out.write(inp.read())


class LoadWizardLoading(QWizardPage, PAGE_2_W):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.plg_settings_mngr = PlgOptionsManager()
        self.plg_settings = self.plg_settings_mngr.get_plg_settings()

        # prefreed import method
        method = self.plg_settings.import_method_as_str
        self.loadInXMLRadio.setChecked(method == "xml")
        self.loadInRelationalRadio.setChecked(method == "gmlas")

        # download to a temporary file by default
        last_path = (
            self.plg_settings.last_downloaded_file
            or self.plg_settings.last_downloaded_file
        )
        if last_path is None:
            with NamedTemporaryFile(suffix=".gml") as out:
                last_path = out.name

        self.outputPathLineEdit.setText(last_path)

    def nextId(self):
        if self.loadInXMLRadio.isChecked():
            return PAGE_ID_XML
        elif self.loadInRelationalRadio.isChecked():
            return PAGE_ID_GMLAS
        return -1

    def validatePage(self):
        self.plg_settings_mngr.set_value_from_key(
            key="impex_import_method",
            value=2 if self.loadInXMLRadio.isChecked() else 1,
        )

        return super().validatePage()

    @pyqtSlot()
    def on_outputPathButton_clicked(self):
        path, suffix_filter = QFileDialog.getSaveFileName(
            self,
            self.tr("Select output file"),
            self.plg_settings.last_downloaded_path or ".",
            self.tr("GML Files (*.gml *.xml)"),
        )
        if path:
            if os.path.splitext(path)[1] == "":
                path = "{}.gml".format(path)
            self.outputPathLineEdit.setText(path)
            self.plg_settings_mngr.set_value_from_key(
                key="last_downloaded_file",
                value=path,
            )
            self.plg_settings_mngr.set_value_from_key(
                key="last_downloaded_path",
                value=os.path.dirname(path),
            )

    @pyqtSlot()
    def on_downloadButton_clicked(self):
        with WaitCursor():
            self.wizard().download_to(self.outputPathLineEdit.text())


class LoadWizardGMLAS(QWizardPage):
    def __init__(self, parent):
        super().__init__(parent)
        self._panel = ImportGmlasPanel(self)
        self._layout = QVBoxLayout()
        self._layout.addWidget(self._panel)
        self.setLayout(self._layout)
        self.setTitle("GMLAS Options")

    def gml_path(self):
        return self.wizard().gml_path()

    def validatePage(self):
        self._panel.do_load()
        return True


class LoadWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Load wizard")
        self._data_source_page = LoadWizardDataSource(self)
        self._wfs_page = LoadWizardWFS(self, PAGE_ID_LOADING)
        self._loading_page = LoadWizardLoading(self)
        self._xml_page = LoadWizardXML(self)
        self._gmlas_page = LoadWizardGMLAS(self)

        self.setPage(PAGE_ID_DATA_SOURCE, self._data_source_page)
        self.setPage(PAGE_ID_WFS, self._wfs_page)
        self.setPage(PAGE_ID_LOADING, self._loading_page)
        self.setPage(PAGE_ID_XML, self._xml_page)
        self.setPage(PAGE_ID_GMLAS, self._gmlas_page)
        self._gml_path = None

    def initializePage(self, page_id):
        # reset gml_path when on the "loading" page
        if page_id == PAGE_ID_LOADING:
            self._gml_path = None

    def sizeHint(self):
        return self._gmlas_page._layout.minimumSize()

    def gml_path(self):
        if self._gml_path is None:
            if self._data_source_page.nextId() == PAGE_ID_WFS:
                with WaitCursor():
                    # if WFS features, download them first
                    with NamedTemporaryFile(suffix=".gml") as out:
                        gml_path = out.name
                    self._wfs_page.download(gml_path)

                self._gml_path = gml_path
            elif self._data_source_page.nextId() == PAGE_ID_LOADING:
                self._gml_path = self._data_source_page.gmlPathLineEdit.text()
        return self._gml_path

    def download_to(self, output_path):
        if self._data_source_page.nextId() == PAGE_ID_WFS:
            self._wfs_page.download(output_path)
        elif self._data_source_page.nextId() == PAGE_ID_LOADING:
            self._data_source_page.download(output_path)
        # use the downloaded file as source
        self._gml_path = output_path
