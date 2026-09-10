from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import tarfile


def load(p): return json.load(open(p))["summary"]

def key(s): return (s["bt"],s["worst_opponent_bt"],s["mean_margin"])

def package(src:pathlib.Path,dst:pathlib.Path):
    with tarfile.open(dst,"w:gz") as tf: tf.add(src,arcname="main.py")
    with tarfile.open(dst,"r:gz") as tf:
        assert tf.getnames()==["main.py"]
        got=tf.extractfile("main.py").read()
    assert got==src.read_bytes()
    return {"bytes":dst.stat().st_size,"sha256":hashlib.sha256(dst.read_bytes()).hexdigest(),"main_sha256":hashlib.sha256(src.read_bytes()).hexdigest(),"members":["main.py"]}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--discovery',required=True); ap.add_argument('--holdout',required=True); ap.add_argument('--generated',required=True); ap.add_argument('--out',required=True); a=ap.parse_args()
    d=load(a.discovery); h=load(a.holdout); base='c95_clock'
    names=[n for n in d if n!=base]
    best=max(names,key=lambda n:(key(d[n]),key(h[n])))
    db, hb=d[base],h[base]; ds,hs=d[best],h[best]
    checks={
      'discovery_bt_gain': ds['bt']-db['bt'] >= 0.01,
      'holdout_bt_gain': hs['bt']-hb['bt'] >= 0.01,
      'discovery_worst_preserved': ds['worst_opponent_bt'] >= db['worst_opponent_bt']-0.025,
      'holdout_worst_preserved': hs['worst_opponent_bt'] >= hb['worst_opponent_bt']-0.025,
      'holdout_rescue_balance': hs['rescued_base_nonwins'] >= hs['sacrificed_base_wins'],
      'meaningful_intervention': ds['paired_changed'] >= 3 and hs['paired_changed'] >= 3,
      'zero_errors': ds['errors']==0 and hs['errors']==0,
    }
    promote=all(checks.values())
    root=pathlib.Path(a.generated); out=pathlib.Path(a.out); out.mkdir(parents=True,exist_ok=True)
    p1=out/'Kaggriculture_V91_1_C95_FEED_FIRST_CONTROL.tar.gz'
    control_pkg=package(root/base/'main.py',p1)
    p2=out/'Kaggriculture_V91_2_C95_MEMORY_PROMOTED.tar.gz'
    selected_pkg=package(root/best/'main.py',p2)
    report={'promote_memory':promote,'selected_memory_variant':best,'checks':checks,'discovery':{'base':db,'selected':ds},'holdout':{'base':hb,'selected':hs},p1.name:control_pkg,p2.name:selected_pkg}
    (out/'promotion.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__': main()
