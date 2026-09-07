#!/usr/bin/env python3
"""Build an eval agent that embeds an arbitrary base source and applies V80 overlay."""
from __future__ import annotations
import argparse, base64, zlib
from pathlib import Path

TEMPLATE = r'''# Auto-generated V80 shadow-market evaluation agent.
import base64 as _b64, zlib as _zl, types as _types, sys as _sys
from experiments.v80.shadow_market_overlay import ShadowMarketOverlay as _V80Overlay
_V80_SRC = _zl.decompress(_b64.b85decode({payload!r})).decode("utf-8")
_V80_MOD = _types.ModuleType("_v80_embedded_base")
_V80_MOD.__file__ = "<v80-embedded-base>"
_sys.modules[_V80_MOD.__name__] = _V80_MOD
exec(compile(_V80_SRC, _V80_MOD.__file__, "exec"), _V80_MOD.__dict__)
_V80_BASE = getattr(_V80_MOD, "agent", None)
if not callable(_V80_BASE):
    # A few public sources expose a named kaggle_agent_* wrapper instead.
    _candidates = [v for k,v in _V80_MOD.__dict__.items() if callable(v) and k.startswith("kaggle_agent")]
    if not _candidates:
        raise RuntimeError("base source exposes no callable agent")
    _V80_BASE = _candidates[-1]
_V80_CONTROLLER = _V80Overlay(_V80_BASE)
def agent(obs):
    return _V80_CONTROLLER(obs)
'''

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('base'); ap.add_argument('out')
    ns=ap.parse_args()
    src=Path(ns.base).read_text(encoding='utf-8')
    payload=base64.b85encode(zlib.compress(src.encode('utf-8'),9)).decode('ascii')
    out=TEMPLATE.format(payload=payload)
    Path(ns.out).write_text(out,encoding='utf-8')
    print('built',ns.out,'bytes',len(out),'base_bytes',len(src))
if __name__=='__main__': main()
