"""Package which provides internationalization to the user interface."""
import os
from typing import Any, Dict

import yaml


def translation(lang: str = "en_US") -> Dict[Any, Any]:
    """Retrieve the messages in the provided language."""
    with open(os.path.join(os.path.dirname(__file__), f"{lang}.yaml"), "r") as file:
        return yaml.safe_load(file)
