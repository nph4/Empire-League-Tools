from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"No config file at {path}. Copy config.example.yaml to config.yaml and fill in your league details."
        )
    with path.open() as f:
        return yaml.safe_load(f)
