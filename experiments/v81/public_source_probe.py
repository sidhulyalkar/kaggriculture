from __future__ import annotations

import json
import pathlib
import urllib.error
import urllib.request

TARGETS = [
    ("shape_top10", "indarkarhana", "shape-the-shop-work-the-pasture-top-10"),
    ("shape_tetsu", "tetsutani", "shape-the-shop-work-the-pasture-kaggriculture"),
    ("farming_v3", "lynnsakurai", "farming-score-v3-replay-revised"),
    ("farming_math", "lynnsakurai", "farming-score-a-mathematical-approach"),
    ("adaptive_route_v2", "reyhanksatria", "adaptive-route-agent-v2"),
]

OUT = pathlib.Path("experiments/v81/harvest")
OUT.mkdir(parents=True, exist_ok=True)


def fetch(url: str) -> tuple[int, str, bytes]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 Kaggriculture-V81-research",
            "Accept": "*/*",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            return int(r.status), str(r.headers.get("content-type", "")), r.read()
    except urllib.error.HTTPError as e:
        return int(e.code), str(e.headers.get("content-type", "")), e.read()


rows = []
for label, owner, slug in TARGETS:
    endpoints = {
        "pull_path": f"https://www.kaggle.com/api/v1/kernels/pull/{owner}/{slug}",
        "pull_query": f"https://www.kaggle.com/api/v1/kernels/pull?userName={owner}&kernelSlug={slug}",
        "output_path": f"https://www.kaggle.com/api/v1/kernels/output/{owner}/{slug}",
        "output_query": f"https://www.kaggle.com/api/v1/kernels/output?userName={owner}&kernelSlug={slug}",
        "page": f"https://www.kaggle.com/code/{owner}/{slug}",
    }
    for kind, url in endpoints.items():
        status, ctype, body = fetch(url)
        suffix = ".json" if "json" in ctype else ".bin"
        path = OUT / f"{label}__{kind}{suffix}"
        path.write_bytes(body)
        rows.append(
            {
                "label": label,
                "kind": kind,
                "url": url,
                "status": status,
                "content_type": ctype,
                "bytes": len(body),
                "file": str(path),
                "head": body[:160].decode("utf-8", "replace"),
            }
        )
        print(label, kind, status, ctype, len(body), rows[-1]["head"].replace("\n", " ")[:120])

(OUT / "probe_manifest.json").write_text(json.dumps(rows, indent=2) + "\n")
