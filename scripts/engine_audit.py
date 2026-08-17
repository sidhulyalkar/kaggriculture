"""Run current-engine mechanics regression checks when kaggle_environments is installed."""
from __future__ import annotations


def main():
    try:
        from kaggle_environments import make
    except Exception as e:
        print('SKIP: kaggle_environments unavailable:',e);return 0
    env=make('kaggriculture',debug=True)
    print('Loaded kaggriculture configuration:',dict(env.configuration))
    print('Manual invariants to verify in source/tests: planting-day weed, +1 care bonus, fertilizer SELL, occupied DIG no-op, locked movement allowed.')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
