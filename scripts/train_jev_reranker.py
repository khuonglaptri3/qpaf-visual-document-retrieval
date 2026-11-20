"""Run the Jev train CLI directly from a clone."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qpaf.jev.cli import main


def windows_trainer():
    """Load the pinned trainer with scoped Windows support for local JSONL training."""
    import builtins
    import importlib.util
    from types import SimpleNamespace
    import psutil
    from qpaf.jev.backends import require_kev_source

    require_kev_source()

    def getrusage(who):
        if who != 0:
            raise ValueError("only this process's peak RSS is available")
        return SimpleNamespace(ru_maxrss=psutil.Process().memory_info().peak_wset // 1024)

    def flock(*_):
        raise RuntimeError("Kev suite file locking requires POSIX. Run suite orchestration on Linux.")

    def load_module(module_name, import_name, replacement):
        def scoped_import(name, *args, **kwargs):
            return replacement if name == import_name else builtins.__import__(name, *args, **kwargs)

        spec = importlib.util.find_spec(module_name)
        module = importlib.util.module_from_spec(spec)
        module.__dict__["__builtins__"] = {**vars(builtins), "__import__": scoped_import}
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        setattr(sys.modules[spec.parent], module_name.rsplit(".", 1)[1], module)
        return module

    # kev.suite imports fcntl for orchestration locks. Local --data training never takes those locks.
    load_module("kev.suite", "fcntl", SimpleNamespace(LOCK_EX=2, flock=flock))
    resource = SimpleNamespace(RUSAGE_SELF=0, getrusage=getrusage)
    module = load_module("kev.train", "resource", resource)
    sys.argv = ["kev.train", *sys.argv[3:]]
    return module.main()


if __name__ == "__main__":
    if sys.platform == "win32" and sys.argv[1:3] == ["--windows-trainer", "kev.train"]:
        raise SystemExit(windows_trainer())
    raise SystemExit(main(["train", *sys.argv[1:]]))
