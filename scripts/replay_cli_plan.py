"""Generate reproducible Kaggle CLI commands for top-team replay acquisition."""
from __future__ import annotations
import argparse

p=argparse.ArgumentParser()
p.add_argument('--submission-id',action='append',default=[])
p.add_argument('--out',default='replays')
a=p.parse_args()
for sid in a.submission_id:
    print(f'kaggle competitions episodes {sid} -v > episodes-{sid}.csv')
    print(f'# then: kaggle competitions replay <EPISODE_ID> -p {a.out}')
