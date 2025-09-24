"""MinuteOne (M1) core package."""
from importlib import resources
from pathlib import Path

__all__ = ["package_path", "asset_path", "__version__"]
__version__ = "0.1.0"


def package_path() -> Path:
    """Return the root path of the installed package."""
    return Path(__file__).resolve().parent


def asset_path(relative: str) -> Path:
    """Return a package-relative Path to an asset on disk."""
    return package_path() / relative
