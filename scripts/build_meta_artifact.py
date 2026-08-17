"""Build a robust live meta-policy artifact from policy-zoo matchup results."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd

from kagv2.equilibrium import payoff_from_results,robust_population_mix


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("results",help="CSV/Parquet with policy, opponent_archetype, score in {0,.5,1}")
    ap.add_argument("--policy-params",default="",help="JSON mapping policy name -> ParametricMind parameters")
    ap.add_argument("--out",default="artifacts/meta_artifact.json")
    ap.add_argument("--bundle",default="",help="Optional learned_model.json to update in-place")
    ap.add_argument("--equilibrium-weight",type=float,default=.40)
    ap.add_argument("--shrink",type=float,default=8.0)
    ap.add_argument("--default-policy",default="")
    args=ap.parse_args()

    p=Path(args.results);df=pd.read_parquet(p) if p.suffix.lower()==".parquet" else pd.read_csv(p)
    policies,opponents,A,N=payoff_from_results(df,shrink=args.shrink)
    counts=df.groupby("opponent_archetype").size().reindex(opponents,fill_value=0).to_numpy(float)
    prior=(counts/counts.sum()).tolist() if counts.sum()>0 else None
    r=robust_population_mix(A,opponent_prior=prior,equilibrium_weight=args.equilibrium_weight)
    params={}
    if args.policy_params:params=json.loads(Path(args.policy_params).read_text())
    meta={
        "policy_names":policies,"archetype_names":opponents,"payoff":A.tolist(),"match_counts":N.tolist(),
        "policy_params":params,"default_policy":args.default_policy or (policies[0] if policies else None),
        "min_archetype_confidence":.62,"switch_margin":.025,"prior_strength":.018,
        **r,
    }
    out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(meta,indent=2,sort_keys=True))
    print(out)
    print(json.dumps({k:meta[k] for k in ["policy_names","policy_mixture","expected_meta_value","worst_archetype_value"]},indent=2))

    if args.bundle:
        bp=Path(args.bundle);obj=json.loads(bp.read_text()) if bp.exists() else {"version":2}
        obj["version"]=max(2,int(obj.get("version",0)));obj["meta"]=meta
        bp.write_text(json.dumps(obj,indent=2,sort_keys=True));print("updated",bp)

if __name__=="__main__":main()
