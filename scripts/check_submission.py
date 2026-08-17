"""Validate a Kaggriculture submission tarball without requiring Kaggle."""
from __future__ import annotations
import argparse
import importlib.util
import os
from pathlib import Path
import sys
import tarfile
import tempfile


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("archive", nargs="?", default="artifacts/submission_v2.tar.gz")
    args = ap.parse_args()
    archive = Path(args.archive)
    if not archive.exists():
        raise FileNotFoundError(archive)

    with tarfile.open(archive, "r:gz") as tf:
        names = tf.getnames()
        if "main.py" not in names:
            raise AssertionError("main.py must be at the archive root")
        if any(n.startswith("/") or ".." in Path(n).parts for n in names):
            raise AssertionError("unsafe archive path")
        with tempfile.TemporaryDirectory() as td:
            # Member names were vetted above, so this remains compatible with Python 3.11 CI.
            tf.extractall(td)
            sys.path.insert(0, td)
            try:
                spec = importlib.util.spec_from_file_location("kag_submission_main", os.path.join(td, "main.py"))
                mod = importlib.util.module_from_spec(spec)
                assert spec and spec.loader
                spec.loader.exec_module(mod)
                if not callable(getattr(mod, "agent", None)):
                    raise AssertionError("main.py must expose callable agent")
            finally:
                sys.path.pop(0)
    print("OK", archive)
    print("files:", ", ".join(names))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
