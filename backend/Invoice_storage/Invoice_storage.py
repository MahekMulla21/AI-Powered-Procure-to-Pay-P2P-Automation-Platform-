# Invoice_storage.py
import sys
from pathlib import Path
import json
from pathlib import Path

from Invoice_config.Invoice_config import OUTPUT_JSON_PATH


def save_result(result: dict, output_path: str = OUTPUT_JSON_PATH) -> str:
    """
    Serialise the extraction result dict to a JSON file.

    Args:
        result      : The complete extraction output dictionary.
        output_path : Destination file path (default from config).

    Returns:
        The resolved absolute path of the saved file as a string.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)

    print(f"[Storage] Result saved → {path.resolve()}")
    return str(path.resolve())


def load_result(output_path: str = OUTPUT_JSON_PATH) -> dict:
    """
    Load a previously saved extraction result from JSON.

    Args:
        output_path : Source file path (default from config).

    Returns:
        Parsed dict, or empty dict if the file does not exist.
    """
    path = Path(output_path)
    if not path.exists():
        print(f"[Storage] File not found: {path}")
        return {}

    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    print(f"[Storage] Result loaded ← {path.resolve()}")
    return data


def print_result(result: dict) -> None:
    """Pretty-print the extraction result to stdout."""
    print(json.dumps(result, indent=2, ensure_ascii=False))
