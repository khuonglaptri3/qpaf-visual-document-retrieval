"""Plan a Modal Volume job offline, then submit explicitly with --execute before score/train.

Example: python scripts/modal_jev_rerank.py --volume jev --execute score --backend bge --pairs inputs/pairs.json --out runs/bge.json
Stage files on the named Volume first. Paths use forward slashes relative to the Volume root.
"""
import argparse
import json
from pathlib import Path, PureWindowsPath
import sys


ROOT = Path(__file__).resolve().parents[1]


def remote_worker(argv, volume_name):
    import os
    import sys
    import modal
    sys.path.insert(0, "/opt/jev/src")
    from qpaf.jev.cli import main

    os.chdir("/data")
    volume = modal.Volume.from_name(volume_name)
    try:
        return main(argv)
    finally:
        volume.commit()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--volume", required=True, help="Existing Modal Volume containing staged inputs")
    parser.add_argument("--gpu", default="A100-80GB")
    parser.add_argument("--execute", action="store_true", help="Submit the job to Modal")
    parser.add_argument("command", choices=("score", "train"))
    parser.add_argument("options", nargs=argparse.REMAINDER, help="Arguments for run_jev.py score or train")
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / "src"))
    from qpaf.jev.backends import validate_score_options
    from qpaf.jev.cli import build_parser
    from qpaf.jev.training import validate_train_options

    argv = [args.command, *args.options]
    options = build_parser()[0].parse_args(argv)
    if options.device != "cuda" or getattr(options, "backend", None) in ("baseline", "lexical"):
        parser.error("the Modal worker runs real CUDA models only")
    try:
        if args.command == "train":
            validate_train_options(options)
        else:
            validate_score_options(options)
    except ValueError as exc:
        parser.error(str(exc))
    for key, value in vars(options).items():
        if isinstance(value, Path) and (PureWindowsPath(value).anchor or ".." in PureWindowsPath(value).parts):
            parser.error(f"--{key} must be relative to the Volume root")
    if args.command == "train" and not options.execute:
        argv.append("--execute")
    requirements = "jev-kev.txt" if args.command == "train" or options.backend == "kev" else "jev-baselines.txt"
    plan = {"volume": args.volume, "gpu": args.gpu, "requirements": requirements, "worker_cwd": "/data", "argv": argv}
    if not args.execute:
        print(json.dumps(plan, indent=2))
        return 0

    import modal
    app = modal.App("qpaf-jev-rerank")
    volume = modal.Volume.from_name(args.volume)
    image = (modal.Image.debian_slim(python_version="3.13").apt_install("git")
             .pip_install_from_requirements(str(ROOT / "requirements" / requirements))
             .env({"HF_HOME": "/data/.huggingface"})
             .add_local_dir(ROOT / "src/qpaf/jev", "/opt/jev/src/qpaf/jev", ignore=["**/__pycache__/**", "*.pyc"])
             .add_local_file(ROOT / "configs/jev/models.json", "/opt/jev/configs/jev/models.json"))
    job = app.function(image=image, gpu=args.gpu, volumes={"/data": volume}, timeout=86400,
                       max_containers=1, serialized=True, include_source=False)(remote_worker)
    with modal.enable_output(), app.run():
        return job.remote(argv, args.volume)


if __name__ == "__main__":
    raise SystemExit(main())
