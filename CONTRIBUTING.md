# Contributing Guidelines

First off, thanks for considering to contribute to this project!

These are mostly guidelines, not rules. Use your best judgment, and feel free to propose changes to this document in a pull request.

## Git hooks

We use git hooks through [pre-commit](https://pre-commit.com/) to enforce and automatically check some "rules". Please install it before to push any commit.

See the relevant configuration file: `.pre-commit-config.yaml`.

## Code Style

Make sure your code *roughly* follows [PEP-8](https://www.python.org/dev/peps/pep-0008/) and keeps things consistent with the rest of the code:

- docstrings: [sphinx-style](https://sphinx-rtd-tutorial.readthedocs.io/en/latest/docstrings.html#the-sphinx-docstring-format) is used to write technical documentation.
- formatting: [black](https://black.readthedocs.io/) is used to automatically format the code without debate.
- static analisis: [flake8](https://flake8.pycqa.org/en/latest/) is used to catch some dizziness and keep the source code healthy.
- static typing: following [PEP-484](https://www.python.org/dev/peps/pep-0484/) type annotations are used to improve code readability and reliability.

----

## Git flow

### Branches naming pattern

The pattern is: `{category}/{issue-code}_-_{slugified-description}`. Where:

- `category` is the type of work. Can be: `feature`, `bug`, `tooling`, `refactor`, `test`, `chore`, `release`, `hotfix`, `docs`, `ci`, `deploy` or `release-candidate`.
- `issue-code` is the GitHub issue number followed by an underscore. If it's not relevant, ignore this.
- `slugified-description` is the description of the work, slugified.

Example: `feature/137_content_negociation`
