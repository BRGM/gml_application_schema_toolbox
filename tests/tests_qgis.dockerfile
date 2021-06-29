FROM qgis/qgis:release-3_16

ENV PYTHONDONTWRITEBYTECODE=1

RUN mkdir -p /tmp/plugin
WORKDIR /tmp/plugin

COPY gml_application_schema_toolbox gml_application_schema_toolbox
COPY requirements requirements
COPY tests tests
COPY setup.cfg setup.cfg

RUN python3 -m pip install -U pip
RUN python3 -m pip install -U setuptools wheel
RUN python3 -m pip install -U -r requirements/testing.txt

# RUN ls -a

RUN qgis --version
# RUN pytest
