"""
Load YAML configuration files.
"""

import yaml
from pathlib import Path


def load_config(path: str) -> dict:
    """Load a YAML config file."""
    config_path = Path(__file__).parent.parent / path
    with open(config_path) as f:
        return yaml.safe_load(f)
