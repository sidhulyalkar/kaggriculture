# Experiment Ledger

Create one directory or Markdown entry per promoted experiment. Record enough information to reproduce every ladder submission.

Suggested fields:

```text
experiment_id:
git_commit:
engine_era:
change:
hypothesis:
dev_seeds:
holdout_seeds:
opponent_population:
both_seat_games:
win_rate:
mean_margin:
latency_p95:
regression_tests:
model_metrics:
submission_id:
ladder_rating_history:
replay_ids:
decision: KEEP | REVERT | INVESTIGATE
```

Do not overwrite old results when tuning. The objective is to turn the competition into an evidence chain rather than a sequence of leaderboard guesses.
