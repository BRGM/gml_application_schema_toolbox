# Tests

## Requirements

QGIS must be installed. Then:

```bash
python -m pip install -U -r requirements/testing.txt
```

## Run tests

Run all tests:

```bash
pytest
```

Run a specific test module:

```bash
python -m unittest tests.test_plg_metadata
```

Run a specific test:

```bash
python -m unittest tests.test_plg_metadata.TestPluginMetadata.test_version_semver
```

## Using Docker

Alternatively, you can run unit tests using Docker:

```bash
docker build -f tests/tests_qgis.dockerfile -t qgis-plugin-testing .
```
