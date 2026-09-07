from __future__ import annotations

import argparse
import base64
import hashlib
import textwrap
import zlib
from pathlib import Path


def build(source_path: Path, output_path: Path, name: str, clock_harden: bool = True):
    raw = source_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    packed = base64.b85encode(zlib.compress(raw, 9)).decode("ascii")
    chunks = "\n".join(repr(packed[i:i+100]) for i in range(0, len(packed), 100))

    clock = """
    # Kaggle's live seat-1 observation has historically exposed an unset `step`
    # while day/hour remain valid.  Canonicalize from public clock fields.  On a
    # normal observation this is deliberately a no-op.
    if o.get("step") is None:
        o["step"] = int(o.get("day", 0) or 0) * 24 + int(o.get("hour", 0) or 0)
""" if clock_harden else ""

    out = f'''# SPDX-License-Identifier: Apache-2.0
# V79 isolated wrapper around Kaito Fukami's public Kaggriculture v58 policy.
# Original: "238/238 Known Streams | v58 Minimax Closed Loop"
# Source: https://www.kaggle.com/code/kaitofukami/238-238-known-streams-v58-minimax-closed-loop
# Upstream redistributable fork: sota1111/erl-kaggriculture
# Upstream SHA-256: {digest}
# Modification: outer runtime wrapper only; upstream bytes execute unchanged in
# an isolated namespace.  The wrapper canonicalizes the public game clock when
# Kaggle omits seat-1 `step`.  Apache-2.0 attribution is preserved here.

import base64 as _b64
import zlib as _zlib

_UPSTREAM_SHA256 = {digest!r}
_UPSTREAM_PACKED = (
{chunks}
)
_ns = {{"__name__": "_v79_upstream_{name}", "__file__": "<embedded-v58>"}}
exec(_zlib.decompress(_b64.b85decode(_UPSTREAM_PACKED)).decode("utf-8"), _ns)
_BASE_AGENT = _ns["agent"]

def agent(obs, configuration=None):
    o = dict(obs or {{}})
{textwrap.indent(textwrap.dedent(clock).strip(), '    ') if clock.strip() else ''}
    return _BASE_AGENT(o, configuration)
'''
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(out)
    print("built", output_path, "upstream_sha256", digest, "bytes", output_path.stat().st_size)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("output")
    ap.add_argument("--name", default="v58")
    ap.add_argument("--no-clock-harden", action="store_true")
    a = ap.parse_args()
    build(Path(a.source), Path(a.output), a.name, not a.no_clock_harden)

if __name__ == "__main__":
    main()
