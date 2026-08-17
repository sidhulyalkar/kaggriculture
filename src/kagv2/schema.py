from __future__ import annotations
import json
from pathlib import Path
from typing import Iterable
import pandas as pd

TABLE_EXTS = {".csv", ".parquet", ".json", ".jsonl", ".ndjson"}
ALIASES = {
    "episode_id": ["episode_id","episodeid","episode","id"],
    "submission_id": ["submission_id","submissionid","submission","agent_submission_id"],
    "team_id": ["team_id","teamid","team"],
    "team_name": ["team_name","teamname","name"],
    "agent_index": ["agent_index","agentindex","player","index"],
    "reward": ["reward","final_reward","score","coins","money"],
    "rating": ["rating","publicscore","public_score","skill","mu"],
    "created_at": ["created_at","createtime","create_time","date","timestamp"],
}

def discover_tables(root: str | Path) -> list[Path]:
    root = Path(root)
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in TABLE_EXTS)

def load_table(path: str | Path) -> pd.DataFrame:
    p = Path(path); s = p.suffix.lower()
    if s == ".csv": return pd.read_csv(p)
    if s == ".parquet": return pd.read_parquet(p)
    if s in {".jsonl", ".ndjson"}: return pd.read_json(p, lines=True)
    if s == ".json":
        try: return pd.read_json(p)
        except Exception:
            obj = json.loads(p.read_text())
            if isinstance(obj, list): return pd.json_normalize(obj)
            if isinstance(obj, dict):
                for _, v in obj.items():
                    if isinstance(v, list):
                        try: return pd.json_normalize(v)
                        except Exception: pass
                return pd.json_normalize([obj])
    raise ValueError(f"Unsupported table: {p}")

def _norm(c: str) -> str:
    return "".join(ch for ch in str(c).lower() if ch.isalnum() or ch == "_")

def infer_column(columns: Iterable[str], logical_name: str) -> str | None:
    cols = list(columns); norm = {_norm(c): c for c in cols}
    for a in ALIASES.get(logical_name, [logical_name]):
        if _norm(a) in norm: return norm[_norm(a)]
    for c in cols:
        nc = _norm(c)
        if logical_name.replace("_","") in nc.replace("_",""):
            return c
    return None

def audit_root(root: str | Path, sample_rows: int = 3) -> pd.DataFrame:
    rows=[]
    for p in discover_tables(root):
        try:
            df=load_table(p)
            inferred={k: infer_column(df.columns,k) for k in ALIASES}
            rows.append({"path":str(p),"rows":len(df),"cols":len(df.columns),
                         "columns":" | ".join(map(str,df.columns[:80])),
                         **{f"col_{k}":v for k,v in inferred.items()}})
        except Exception as e:
            rows.append({"path":str(p),"rows":None,"cols":None,"columns":"", "error":repr(e)})
    return pd.DataFrame(rows)

def choose_index_table(root: str | Path) -> tuple[Path, pd.DataFrame]:
    candidates=[]
    for p in discover_tables(root):
        try:
            df=load_table(p)
        except Exception:
            continue
        score=0
        for k,w in [("episode_id",5),("submission_id",3),("reward",2),("created_at",1),("rating",1)]:
            score += w * int(infer_column(df.columns,k) is not None)
        score += min(3, len(df)/10000)
        candidates.append((score,len(df),p,df))
    if not candidates: raise FileNotFoundError(f"No readable index-like table under {root}")
    _,_,p,df=max(candidates,key=lambda x:(x[0],x[1]))
    return p,df

def normalize_index(df: pd.DataFrame) -> pd.DataFrame:
    out=df.copy()
    for k in ALIASES:
        c=infer_column(out.columns,k)
        if c is not None and c != k and k not in out.columns: out[k]=out[c]
    if "created_at" in out:
        out["created_at"]=pd.to_datetime(out["created_at"],errors="coerce",utc=True)
    return out
