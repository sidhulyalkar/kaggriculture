from __future__ import annotations

import pathlib

BASE = pathlib.Path("experiments/v87/current_shape.py")
OUT = pathlib.Path("experiments/v87/experts")

LEAVES = ("MAIN", "YARN", "YARN_CARROT", "MILK_GLUT")

OLD_LOOP = '''        for (turn, feat, thr, target) in DECISIONS:\n            if turn == step and target != self.cur and self._switch_ok(target, turn):\n                if _feature(obs, feat) >= thr:\n                    self.cur = target\n'''

NEW_LOOP = '''        # V87 oracle expert: force one existing prefix-compatible leaf.\n        for (turn, feat, thr, target) in DECISIONS:\n            if turn != step or target == self.cur or not self._switch_ok(target, turn):\n                continue\n            take = (\n                (turn == 226 and V87_LEAF in ("YARN", "YARN_CARROT"))\n                or (turn == 360 and V87_LEAF == "YARN_CARROT")\n                or (turn == 433 and V87_LEAF == "MILK_GLUT")\n            )\n            if take:\n                self.cur = target\n'''


def make(leaf: str, source: str) -> str:
    if source.count(OLD_LOOP) != 1:
        raise RuntimeError("upstream Shape decision loop changed")
    patched = source.replace("class Agent:", f'V87_LEAF = "{leaf}"\n\nclass Agent:', 1)
    patched = patched.replace(OLD_LOOP, NEW_LOOP, 1)
    compile(patched, f"v87_expert_{leaf}.py", "exec")
    return patched


def main() -> None:
    source = BASE.read_text()
    OUT.mkdir(parents=True, exist_ok=True)
    for leaf in LEAVES:
        path = OUT / f"expert_{leaf.lower()}.py"
        path.write_text(make(leaf, source))
        print(leaf, path.stat().st_size)


if __name__ == "__main__":
    main()
