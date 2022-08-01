from __future__ import print_function

from poetry.core.factory import Factory
from poetry.core.masonry.builders.sdist import SdistBuilder
from poetry.core.utils._compat import Path


def build_setup_py() -> bytes:
    """Create the setup.py from the pyproject.toml file."""
    return SdistBuilder(Factory().create_poetry(Path(".").resolve())).build_setup()


def main() -> None:
    """Echo the completed file to stdout."""
    print(build_setup_py().decode("utf8"))


if __name__ == "__main__":
    main()
