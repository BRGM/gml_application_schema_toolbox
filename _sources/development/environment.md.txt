# Development environment setup

## Requirements

- Python 3.7 or later
- QGIS LTR
- PostgreSQL with PostGIS extension (or Docker)
- GDAL

----

## Code and software

Clone the repository, then follow these steps.

It's strongly recomended to develop into a virtual environment:

```bash
python3 -m venv --system-site-packages .venv
```

```{note}
We link to system packages to keep the link with installed QGIS Python libraries: PyQGIS, PyQT, etc.
```

In your virtual environment:

```bash
# use the latest pip version
python -m pip install -U pip setuptools wheel
# install development tools
python -m pip install -U -r requirements/development.txt
# install pre-commit to respect common development guidelines
pre-commit install
```

----

## Data

A PostGIS database is required. A dead simple [docker compose file](https://github.com/BRGM/gml_application_schema_toolbox/blob/master/tests/dev/docker-compose_postgis.yml) is provided into the `tests/dev/` subfolder. You can run it with:

```bash
docker-compose -f "tests/dev/docker-compose_postgis.yml" up -d --build
```

Look at the `tests/samples` and `tests/fixtures` subfolders for sample data. You can find some useful commands into the [Testing GDAL section](../usecases/index).
