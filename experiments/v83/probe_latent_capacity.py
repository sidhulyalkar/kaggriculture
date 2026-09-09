from __future__ import annotations

import argparse
import importlib.util
import json
from collections import Counter
from pathlib import Path


def load(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod.agent


def run(base_path: str, opp_path: str, seed: int, seat: int):
    import kagsim
    a = load(base_path, f'a{seed}{seat}')
    b = load(opp_path, f'b{seed}{seat}')
    g = kagsim.Game(seed)
    row = None
    while not g.done:
        o0 = dict(g.observe(0)); o1 = dict(g.observe(1))
        mine = o0 if seat == 0 else o1
        if int(mine.get('step') or 0) == 313:
            act = a(mine)
            farms = list(mine.get('farms') or [])
            farm = farms[seat]
            tiles = farm.get('tiles') or []
            tile = tiles[3][5] if len(tiles)>3 and len(tiles[3])>5 else None
            pos = [tuple(farm.get('farmer') or ())] + [tuple(x or ()) for x in (farm.get('hands') or [])]
            cross = Counter(p for p in pos if p in {(4,4),(5,4),(4,5),(5,5)})
            private = mine.get('private') or {}
            shed = dict(private.get('shed') or {})
            buys = [x for x in (act.get('market') or []) if x and x[0]=='BUY_ANIMAL']
            hires = sum(x == ['HIRE'] for x in (act.get('market') or []))
            row = {
                'seed':seed,'seat':seat,'money':farm.get('money'),'hires_today':farm.get('hires_today'),
                'n_positions':len(pos),'cross':{str(k):v for k,v in cross.items()},
                'target_tile':tile,'shed_total':sum(max(0,int(v or 0)) for v in shed.values()),
                'market':act.get('market'),'buys':buys,'hires_in_action':hires,
                'farmer':farm.get('farmer'),'hands':farm.get('hands'),
            }
            # finish action for this step without double-call
            opp = b(o1 if seat==0 else o0)
            if seat==0: g.step(act,opp)
            else: g.step(opp,act)
            continue
        x=a(mine); y=b(o1 if seat==0 else o0)
        if seat==0: g.step(x,y)
        else: g.step(y,x)
    return row


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--base',required=True); ap.add_argument('--opp',required=True)
    ap.add_argument('--out',required=True); ap.add_argument('--start-seed',type=int,default=120001); ap.add_argument('--seeds',type=int,default=4)
    args=ap.parse_args()
    rows=[]
    for seed in range(args.start_seed,args.start_seed+args.seeds):
        for seat in (0,1): rows.append(run(args.base,args.opp,seed,seat))
    Path(args.out).write_text(json.dumps(rows,indent=2)+'\n')
    for r in rows: print(json.dumps(r,sort_keys=True))

if __name__=='__main__': main()
