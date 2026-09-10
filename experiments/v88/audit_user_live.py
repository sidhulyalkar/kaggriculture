from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import time
from collections import Counter, defaultdict
from urllib.request import Request, urlopen

API = "https://www.kaggle.com/api/i/competitions.EpisodeService/ListEpisodes"
REPLAY = "https://www.kaggle.com/competitions/episodes/{eid}/replay.json"
HEADERS = {"User-Agent": "Mozilla/5.0 V88", "Content-Type": "application/json"}


def post(body: dict):
    req = Request(API, data=json.dumps(body).encode(), headers=HEADERS, method="POST")
    with urlopen(req, timeout=90) as r:
        return json.loads(r.read())


def get(url: str):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 V88"})
    with urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def completed_rows(d: dict, tid: int, sid: int):
    rows=[]
    for e in d.get("episodes") or []:
        if e.get("state") != "COMPLETED": continue
        agents=e.get("agents") or []
        for seat,a in enumerate(agents):
            if int(a.get("teamId") or -1)==tid and int(a.get("submissionId") or -1)==sid:
                opp=agents[1-seat] if len(agents)==2 else {}
                r=float(a.get("reward") or 0); ro=float(opp.get("reward") or 0)
                rows.append({
                    "episode_id":int(e["id"]),"create_time":e.get("createTime"),"seat":seat,
                    "reward":r,"opponent_reward":ro,"margin":r-ro,
                    "updated_score":a.get("updatedScore"),"initial_score":a.get("initialScore"),
                    "opponent_team_id":opp.get("teamId"),"opponent_submission_id":opp.get("submissionId"),
                    "opponent_score":opp.get("updatedScore"),
                })
    return sorted(rows,key=lambda x:str(x.get("create_time") or ""))


def action_prefix(replay, seat, n):
    acts=[]
    for step in (replay.get("steps") or [])[:n]:
        try: a=(step[seat] or {}).get("action") or {}
        except Exception: a={}
        acts.append(json.dumps(a,sort_keys=True,separators=(",",":")))
    import hashlib
    return hashlib.sha256("\n".join(acts).encode()).hexdigest()[:20]


def cp_state(replay, seat, cp):
    try: obs=(replay["steps"][cp][seat] or {}).get("observation") or {}
    except Exception: return {}
    farms=obs.get("farms") or []
    own=farms[seat] if len(farms)>seat else {}
    opp=farms[1-seat] if len(farms)>1-seat else {}
    def count(f, key):
        n=0
        for row in f.get("tiles") or []:
            for t in row or []:
                if isinstance(t,dict) and (t.get("kind")==key or t.get("animal")==key): n+=1
        return n
    market=obs.get("market") or {}; town=obs.get("town") or {}
    return {
      "own_money":own.get("money"),"opp_money":opp.get("money"),
      "own_hands":len(own.get("hands") or []),"opp_hands":len(opp.get("hands") or []),
      "own_cows":count(own,"COW"),"opp_cows":count(opp,"COW"),
      "own_sheep":count(own,"SHEEP"),"opp_sheep":count(opp,"SHEEP"),
      "own_pastures":count(own,"PASTURE"),"opp_pastures":count(opp,"PASTURE"),
      "shops":town.get("unlocked_shops") or [],
      "prices":market.get("prices") or {},"inventory":market.get("inventory") or {},
    }


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--seed-submission",type=int,default=55260568)
    ap.add_argument("--team-query",default="Sidharth Hulyalkar")
    ap.add_argument("--replays",type=int,default=30)
    ap.add_argument("--out",default="experiments/v88/results")
    args=ap.parse_args()
    out=pathlib.Path(args.out); out.mkdir(parents=True,exist_ok=True)

    seed=post({"submissionId":args.seed_submission})
    teams=seed.get("teams") or []
    q=args.team_query.lower()
    matches=[t for t in teams if q in str(t.get("teamName") or t.get("name") or "").lower()]
    if not matches:
        # fallback matching first or last token, useful if team display name changed
        toks=[x for x in q.split() if len(x)>3]
        matches=[t for t in teams if any(tok in str(t.get("teamName") or t.get("name") or "").lower() for tok in toks)]
    if not matches: raise SystemExit(f"team not found among {len(teams)} teams")
    t=matches[0]; tid=int(t["id"]); sid=int(t["publicLeaderboardSubmissionId"])
    d=post({"submissionId":sid})
    rows=completed_rows(d,tid,sid)
    if not rows: raise SystemExit(f"no current completed episodes tid={tid} sid={sid}")

    margins=[r["margin"] for r in rows]; wins=sum(x>0 for x in margins); ties=sum(x==0 for x in margins)
    seat={s:[r for r in rows if r["seat"]==s] for s in (0,1)}
    opp=defaultdict(list)
    for r in rows: opp[(r["opponent_team_id"],r["opponent_submission_id"])].append(r)
    opp_summary=[]
    for (ot,os),xs in opp.items():
        ms=[x["margin"] for x in xs]
        opp_summary.append({"opponent_team_id":ot,"opponent_submission_id":os,"games":len(xs),
                            "bt_score":(sum(x>0 for x in ms)+.5*sum(x==0 for x in ms))/len(ms),
                            "mean_margin":statistics.mean(ms),"last_opponent_score":xs[-1].get("opponent_score")})
    opp_summary.sort(key=lambda x:(x["bt_score"],x["mean_margin"]))

    details=[]
    for r in rows[-args.replays:]:
        try:
            rep=get(REPLAY.format(eid=r["episode_id"]))
            details.append({**r,"h72":action_prefix(rep,r["seat"],72),"h120":action_prefix(rep,r["seat"],120),
                            "h226":action_prefix(rep,r["seat"],226),"h360":action_prefix(rep,r["seat"],360),
                            "full":action_prefix(rep,r["seat"],720),
                            "cp226":cp_state(rep,r["seat"],226),"cp360":cp_state(rep,r["seat"],360),"cp433":cp_state(rep,r["seat"],433)})
            time.sleep(.15)
        except Exception as exc:
            details.append({**r,"replay_error":repr(exc)})

    summary={
      "team":t,"submission_id":sid,"episodes":len(rows),"latest_score":rows[-1].get("updated_score"),
      "wins":wins,"losses":sum(x<0 for x in margins),"ties":ties,
      "bt_score":(wins+.5*ties)/len(rows),"mean_margin":statistics.mean(margins),
      "median_margin":statistics.median(margins),
      "seat0_bt":(sum(r["margin"]>0 for r in seat[0])+.5*sum(r["margin"]==0 for r in seat[0]))/max(1,len(seat[0])),
      "seat1_bt":(sum(r["margin"]>0 for r in seat[1])+.5*sum(r["margin"]==0 for r in seat[1]))/max(1,len(seat[1])),
      "worst_opponents":opp_summary[:12],
    }
    (out/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    (out/"episodes.jsonl").write_text("".join(json.dumps(x,separators=(",",":"))+"\n" for x in rows))
    (out/"recent_replays.json").write_text(json.dumps(details,indent=2)+"\n")
    print(json.dumps(summary,indent=2))

if __name__=="__main__": main()
