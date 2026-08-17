from __future__ import annotations

"""Build a controlled panel of Kaggriculture leaderboard submissions.

All variants use byte-identical runtime code.  Only ``runtime_flags`` inside the
learned artifact change, making ladder A/B results easier to attribute.

Usage:
    python scripts/build_experiment_submissions.py \
        --model artifacts/learned_model.json \
        --meta artifacts/meta_artifact.json

Outputs live under ``artifacts/experiments/`` together with a manifest that
records the flags and SHA-256 digest for every archive.
"""

import argparse
import copy
import hashlib
import io
import json
from pathlib import Path
import tarfile

ROOT=Path(__file__).resolve().parents[1]
SUB=ROOT/'submission'
RUNTIME_FILES=['main.py','predictive_agent.py','parametric_agent.py','base_controller.py','runtime_model.py','meta_runtime.py']


def _sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''): h.update(chunk)
    return h.hexdigest()


def _best_fixed_policy(model: dict) -> str | None:
    meta=model.get('meta') or {}
    names=list(meta.get('policy_names') or [])
    mix=list(meta.get('policy_mixture') or [])
    if not names:return None
    if 'cem_robust' in names:return 'cem_robust'
    if mix and len(mix)==len(names):return names[max(range(len(mix)),key=mix.__getitem__)]
    return meta.get('default_policy') or names[0]


def _write_tar(path: Path, model: dict) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    payload=json.dumps(model,indent=2,sort_keys=True).encode('utf-8')
    with tarfile.open(path,'w:gz') as tar:
        for name in RUNTIME_FILES:
            tar.add(SUB/name,arcname=name)
        ti=tarfile.TarInfo('learned_model.json')
        ti.size=len(payload)
        tar.addfile(ti,io.BytesIO(payload))


def build_panel(model: dict, out_dir: Path) -> list[dict]:
    fixed=_best_fixed_policy(model)
    variants=[
        ('S0_control', {'meta_selection':False,'predictive_selling':False,'fixed_policy':None},
         'Deterministic parametric control; learned components disabled.'),
        ('S1_robust_fixed', {'meta_selection':False,'predictive_selling':False,'fixed_policy':fixed},
         'Best promoted robust macro policy fixed for the whole episode.'),
        ('S2_market_only', {'meta_selection':False,'predictive_selling':True,'fixed_policy':None},
         'Default macro policy plus future-supply predictive selling.'),
        ('S3_meta_only', {'meta_selection':True,'predictive_selling':False,'fixed_policy':None},
         'Opponent-belief/meta policy selection without predictive selling.'),
        ('S4_full', {'meta_selection':True,'predictive_selling':True,'fixed_policy':None},
         'Full promoted V2: meta selector plus predictive market timing.'),
    ]
    rows=[]
    for name,flags,description in variants:
        obj=copy.deepcopy(model)
        obj['runtime_flags']=flags
        obj.setdefault('provenance',{})
        obj['provenance']['experiment_variant']=name
        out=out_dir/f'{name}.tar.gz'
        _write_tar(out,obj)
        rows.append({'variant':name,'description':description,'runtime_flags':flags,
                     'archive':out.name,'bytes':out.stat().st_size,'sha256':_sha256(out)})
    (out_dir/'experiment_manifest.json').write_text(json.dumps(rows,indent=2,sort_keys=True))
    return rows


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--model',type=Path,default=ROOT/'submission'/'learned_model.json')
    ap.add_argument('--meta',type=Path,default=None)
    ap.add_argument('--out-dir',type=Path,default=ROOT/'artifacts'/'experiments')
    args=ap.parse_args()
    model=json.loads(args.model.read_text()) if args.model.exists() else {'version':2}
    if args.meta and args.meta.exists():model['meta']=json.loads(args.meta.read_text())
    rows=build_panel(model,args.out_dir)
    print(json.dumps(rows,indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
