"""Execute the guided notebook without live model or payment calls."""

from pathlib import Path

import nbformat
from nbclient import NotebookClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = PROJECT_ROOT / "notebooks" / "pay_for_research.ipynb"


def main() -> None:
    notebook = nbformat.read(NOTEBOOK, as_version=4)
    NotebookClient(notebook, timeout=120, kernel_name="python3").execute(cwd=NOTEBOOK.parent)
    print("Notebook offline execution passed.")


if __name__ == "__main__":
    main()
