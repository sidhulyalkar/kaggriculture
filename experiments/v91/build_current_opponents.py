from __future__ import annotations

import ast
import base64
import hashlib
import json
import pathlib
import re
import urllib.request
import zlib

UA = {"User-Agent": "Mozilla/5.0 V91-opponents"}
REFS = {
    "shape": "tetsutani/shape-the-shop-work-the-pasture-kaggriculture",
    "conditional_memory": "kaitofukami/177-180-fresh-top-30-v21-1-conditional-memory",
    "adaptive_guard": "reyhanksatria/kaggriculture-adaptive-shop-guard",
    "smart_lab": "flexonafft/kaggriculture-smart-farm-strategy-lab",
    "harvestforge": "salemali7/kaggriculture-2900",
}


def pull(ref: str) -> dict:
    req = urllib.request.Request(f"https://www.kaggle.com/api/v1/kernels/pull/{ref}", headers=UA)
    with urllib.request.urlopen(req, timeout=90) as r:
        outer = json.load(r)
    src = (outer.get("blob") or {}).get("source")
    if not src:
        raise RuntimeError(f"missing source for {ref}")
    return json.loads(src)


def texts(nb):
    for c in nb.get("cells", []):
        s=c.get("source","")
        yield "".join(s) if isinstance(s,list) else str(s)


def assignment(nb, name):
    for src in texts(nb):
        if name not in src: continue
        try: tree=ast.parse(src)
        except SyntaxError: continue
        for node in tree.body:
            if not isinstance(node,(ast.Assign,ast.AnnAssign)): continue
            ts=node.targets if isinstance(node,ast.Assign) else [node.target]
            if any(isinstance(t,ast.Name) and t.id==name for t in ts):
                return ast.literal_eval(node.value)
    raise RuntimeError(f"{name} not found")


def shape(nb):
    payload=assignment(nb,"MAIN_B64")
    return base64.b64decode(payload)


def conditional(nb):
    parts=assignment(nb,"_AGENT_B85_PARTS")
    return zlib.decompress(base64.b85decode("".join(parts).encode("ascii")))


def adaptive_guard(nb):
    blob=assignment(nb,"BLOB")
    return zlib.decompress(base64.b85decode(blob.encode("ascii")))


def smart_lab(nb):
    return assignment(nb,"AGENT_SOURCE").encode()


def harvestforge(nb):
    for src in texts(nb):
        if "%%writefile main.py" in src and "def agent" in src and "_ACTIONS" in src:
            src=re.sub(r"^%%writefile\s+main\.py\s*\n","",src,count=1)
            return src.encode()
    raise RuntimeError("harvestforge main cell not found")


def main():
    root=pathlib.Path("experiments/v91/opponents"); root.mkdir(parents=True,exist_ok=True)
    builders={"shape":shape,"conditional_memory":conditional,"adaptive_guard":adaptive_guard,"smart_lab":smart_lab,"harvestforge":harvestforge}
    report={}
    for name,ref in REFS.items():
        try:
            data=builders[name](pull(ref))
            compile(data.decode(),name+".py","exec")
            p=root/(name+".py"); p.write_bytes(data)
            report[name]={"ref":ref,"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}
            print(name,len(data),report[name]["sha256"])
        except Exception as e:
            report[name]={"ref":ref,"error":repr(e)}
            print("ERROR",name,repr(e))
    (root/"manifest.json").write_text(json.dumps(report,indent=2)+"\n")
    if len(list(root.glob("*.py"))) < 4:
        raise SystemExit("insufficient independent opponent families")

if __name__=="__main__": main()
