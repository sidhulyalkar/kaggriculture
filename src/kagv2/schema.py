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
    "reward": ["reward","final_reward","score","coins","money","bank"],
    "rating": ["rating","publicscore","public_score","skill","mu"],
    "created_at": ["created_at","create_time","createtime","createTime","date","timestamp"],
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
    needle=logical_name.replace("_","")
    for c in cols:
        nc = _norm(c)
        if needle in nc.replace("_",""):
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
        # Wide two-player episode tables are particularly useful even though
        # they do not have a single submission_id/rating column.
        cols={str(c).lower() for c in df.columns}
        score += 4*int({"sub_0","sub_1"}.issubset(cols))
        score += 3*int({"bank_0","bank_1"}.issubset(cols))
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

def normalize_wide_episodes(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize a public one-row-per-match Kaggriculture episode table.

    Public replay datasets commonly expose ``sub_0/sub_1``, ``team_0/team_1``,
    ``bank_0/bank_1`` and ``rating_0/rating_1``.  Preserve the wide columns and
    add stable derived matchup labels without pretending they are online
    features.
    """
    out=normalize_index(df)
    for c in ["bank_0","bank_1","rating_0","rating_1"]:
        if c in out:
            out[c]=pd.to_numeric(out[c],errors="coerce")
    if {"bank_0","bank_1"}.issubset(out.columns):
        out["margin_0"]=out["bank_0"]-out["bank_1"]
        out["winner"]=(out["bank_0"]>out["bank_1"]).astype(float)
        ties=out["bank_0"].eq(out["bank_1"])
        out.loc[ties,"winner"]=0.5
    if {"rating_0","rating_1"}.issubset(out.columns):
        out["rating_diff_0"]=out["rating_0"]-out["rating_1"]
        out["rating_mean"]=(out["rating_0"]+out["rating_1"])/2
    return out

def wide_to_player_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Convert a normalized wide episode table into one row per player."""
    d=normalize_wide_episodes(df)
    rows=[]
    common=[c for c in ["episode_id","created_at","create_time","state","type"] if c in d]
    for seat in (0,1):
        z=d[common].copy() if common else pd.DataFrame(index=d.index)
        z["seat"]=seat
        mapping={
            f"sub_{seat}":"submission_id", f"team_{seat}":"team_id",
            f"bank_{seat}":"reward", f"rating_{seat}":"rating",
            f"sub_{1-seat}":"opponent_submission_id", f"team_{1-seat}":"opponent_team_id",
            f"bank_{1-seat}":"opponent_reward", f"rating_{1-seat}":"opponent_rating",
        }
        for src,dst in mapping.items():
            if src in d: z[dst]=d[src].to_numpy()
        if {"reward","opponent_reward"}.issubset(z.columns):
            z["win_target"]=(z.reward>z.opponent_reward).astype(float)
            z.loc[z.reward.eq(z.opponent_reward),"win_target"]=0.5
            z["margin"]=z.reward-z.opponent_reward
        rows.append(z)
    return pd.concat(rows,ignore_index=True)
