from __future__ import annotations

import argparse
import ast
import base64
import hashlib
import json
import pathlib
import re
import urllib.request

SOURCES = {
    "shape": "tetsutani/shape-the-shop-work-the-pasture-kaggriculture",
    "three_day": "yhay81/three-day-shop-router",
    "adaptive_v2": "reyhanksatria/adaptive-route-agent-v2",
    "farming_v3": "tetsutani/farming-score-v3-replay-revised",
}


def pull(ref: str) -> tuple[dict, dict]:
    url = f"https://www.kaggle.com/api/v1/kernels/pull/{ref}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 V89"})
    with urllib.request.urlopen(req, timeout=60) as r:
        outer = json.load(r)
    source = (outer.get("blob") or {}).get("source")
    if not source:
        raise RuntimeError(f"missing notebook source for {ref}")
    return outer, json.loads(source)


def cell_text(cell: dict) -> str:
    src = cell.get("source", "")
    return "".join(src) if isinstance(src, list) else str(src)


def b64_assignments(src: str) -> list[tuple[str, bytes]]:
    out=[]
    try: tree=ast.parse(src)
    except SyntaxError: return out
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)): continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = node.value
        for target in targets:
            if not isinstance(target, ast.Name): continue
            name=target.id
            if "B64" not in name.upper() and "BASE64" not in name.upper(): continue
            try: payload=ast.literal_eval(value)
            except Exception: continue
            if not isinstance(payload, str) or len(payload) < 100: continue
            try: data=base64.b64decode(payload, validate=False)
            except Exception: continue
            out.append((name,data))
    return out


def score_text(src: str) -> dict:
    pats={
      "agent_defs": r"\bdef\s+agent\s*\(",
      "agent_classes": r"\bclass\s+Agent\b",
      "main_py_mentions": r"main\.py",
      "action_mentions": r"\bmarket\b|\bfarmer\b|\bhands\b",
      "route_mentions": r"route|decision|checkpoint|branch",
      "tape_mentions": r"tape|replay|trajectory|actions",
    }
    return {k:len(re.findall(p,src,re.I)) for k,p in pats.items()}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",default="experiments/v89/harvest")
    args=ap.parse_args()
    root=pathlib.Path(args.out); root.mkdir(parents=True,exist_ok=True)
    report={}
    for name,ref in SOURCES.items():
        d=root/name; d.mkdir(parents=True,exist_ok=True)
        try:
            outer,nb=pull(ref)
        except Exception as exc:
            report[name]={"ref":ref,"error":repr(exc)}
            print(name,ref,"ERROR",repr(exc))
            continue
        (d/"notebook.ipynb").write_text(json.dumps(nb,indent=1))
        texts=[cell_text(c) for c in nb.get("cells",[])]
        (d/"all_code.txt").write_text("\n\n# ===== CELL =====\n\n".join(texts))
        candidates=[]
        for i,src in enumerate(texts):
            s=score_text(src)
            if sum(s.values()):
                candidates.append({"cell":i,"chars":len(src),**s})
            for var,data in b64_assignments(src):
                ext="py" if data.lstrip().startswith((b"from ",b"import ",b"#",b"def ",b"class ")) else "bin"
                p=d/f"decoded_cell{i}_{var}.{ext}"
                p.write_bytes(data)
                if ext=="py":
                    try: compile(data.decode(),str(p),"exec")
                    except Exception: pass
        report[name]={
          "ref":ref,"cells":len(texts),"outer_keys":sorted(outer.keys()),
          "source_sha256":hashlib.sha256(json.dumps(nb,sort_keys=True).encode()).hexdigest(),
          "candidate_cells":sorted(candidates,key=lambda x:(x["agent_defs"]+x["agent_classes"],x["main_py_mentions"],x["chars"]),reverse=True)[:20],
          "decoded_files":[p.name for p in sorted(d.glob("decoded_*"))],
        }
        print(name,ref,"cells",len(texts),"candidates",report[name]["candidate_cells"][:5],"decoded",report[name]["decoded_files"])
    (root/"report.json").write_text(json.dumps(report,indent=2)+"\n")

if __name__=="__main__": main()
