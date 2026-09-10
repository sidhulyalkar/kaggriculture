from __future__ import annotations

import pathlib

BASE = pathlib.Path("experiments/v86/current_shape.py")
OUT = pathlib.Path("experiments/v86/generated")

MODES = (
    "suppress_226",
    "force_226",
    "suppress_360",
    "force_360",
    "suppress_433",
    "force_433",
)

HELPER = r'''

# ---- V86 public-structure mirror detector ----
def _v86_public_mirror(obs, me):
    """Detect a same-geometry opponent using only public state.

    Money is deliberately excluded because same-turn market ordering can introduce
    seat-dependent cash differences even when both farms execute the same physical
    program.  We require the complete public farm geometry, workers, hands and land
    state to match at the checkpoint.
    """
    try:
        farms = obs.get("farms") or []
        if len(farms) != 2:
            return False
        a, b = farms[me], farms[1 - me]
        return (
            a.get("farmer") == b.get("farmer")
            and a.get("hands") == b.get("hands")
            and a.get("tiles") == b.get("tiles")
            and a.get("unlocked_land") == b.get("unlocked_land")
        )
    except Exception:
        return False
'''

OLD_LOOP = '''        for (turn, feat, thr, target) in DECISIONS:\n            if turn == step and target != self.cur and self._switch_ok(target, turn):\n                if _feature(obs, feat) >= thr:\n                    self.cur = target\n'''

NEW_LOOP = '''        mirror = _v86_public_mirror(obs, me)\n        for (turn, feat, thr, target) in DECISIONS:\n            if turn != step or target == self.cur or not self._switch_ok(target, turn):\n                continue\n            if mirror and V86_MODE == f"force_{turn}":\n                self.cur = target\n                continue\n            if mirror and V86_MODE == f"suppress_{turn}":\n                continue\n            if _feature(obs, feat) >= thr:\n                self.cur = target\n'''


def make(mode: str, source: str) -> str:
    if source.count("class Agent:") != 1:
        raise RuntimeError("unexpected Agent class count")
    if source.count(OLD_LOOP) != 1:
        raise RuntimeError("decision loop changed upstream")
    patched = source.replace("class Agent:", f'V86_MODE = "{mode}"\n' + HELPER + "\n\nclass Agent:")
    patched = patched.replace(OLD_LOOP, NEW_LOOP)
    compile(patched, f"v86_{mode}.py", "exec")
    return patched


def main() -> None:
    src = BASE.read_text()
    OUT.mkdir(parents=True, exist_ok=True)
    for mode in MODES:
        out = OUT / f"v86_{mode}.py"
        out.write_text(make(mode, src))
        print(mode, out.stat().st_size)


if __name__ == "__main__":
    main()
