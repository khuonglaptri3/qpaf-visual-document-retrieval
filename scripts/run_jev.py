"""Run the Jev toolkit directly from a clone."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qpaf.jev.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
