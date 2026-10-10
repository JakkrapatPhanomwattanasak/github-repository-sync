# Local verification

Validated on Windows with Python 3.12.0 during the October 2026 implementation session.

- `python -m pytest -q`: 14 tests passed.
- `ruff check .` and `ruff format --check .`: passed.
- `python -m build --wheel`: built successfully in an isolated build environment.
- A CI template is prepared for Python 3.11, 3.12, and 3.13; hosted CI is not activated.

Tested libraries: Flask 3.1.3, Pandas 2.3.3, scikit-learn 1.9.1, Requests 2.34.2, pytest 9.1.1, Ruff 0.17.0, as applicable to this project's dependencies. Requirements use compatible ranges; saved model artifacts should use the versions recorded in their metrics metadata.
