"""Tests for package exports, module imports, and version metadata."""

import re

import spicetify


def test_all_exports_exist():
    """Ensure all symbols defined in __all__ are properly exported."""
    for export_name in spicetify.__all__:
        assert hasattr(spicetify, export_name), f"Export '{export_name}' is missing in __init__.py"


def test_version_format():
    """Ensure __version__ exists and follows Semantic Versioning format."""
    assert hasattr(spicetify, "__version__")
    assert isinstance(spicetify.__version__, str)

    # Validates semantic versioning strings
    semver_pattern = r"^\d+\.\d+\.\d+.*$"
    assert re.match(semver_pattern, spicetify.__version__), (
        f"__version__ '{spicetify.__version__}' does not follow SemVer format"
    )
