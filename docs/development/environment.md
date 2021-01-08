# Development environment setup

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
