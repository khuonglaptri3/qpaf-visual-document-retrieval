"""Run the repository audit from a checkout without installing dependencies."""

from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from qpaf.audit import main


if __name__ == "__main__":
    raise SystemExit(main())
