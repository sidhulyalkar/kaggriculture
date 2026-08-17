# V3 Frontier Transplant Lab

Phase 2 showed that the current controller is far below the public economic frontier and that the frontier has real matchup structure. V3 therefore tests **mechanism transplants** rather than adding another generic ML layer.

## Candidate panel

- Pure: Soil, Adaptive, 3094, V16, Ranker, Melon, Strict Future, Findings.
- Split: Soil `farmer` + `hands` with another policy's `market`.
- Reverse controls: another policy's micro with Soil market.
- Phase switches at day 7 or 11. Both policies are called every turn so stateful logic remains initialized.

## Family-balanced meta

The lab groups near-related public strategies before scoring:

- Soil family
- Adaptive/3094 family
- V16 premium family
- Ranker/Melon family
- Strict Future family
- Findings family

Each family contributes equally, preventing duplicate public lineages from dominating the objective.

## Robust objective

`0.55 * mean_family_win + 0.25 * worst_family_win + 0.20 * lower40_CVaR`

## Promotion gate

A hybrid must have zero invalid games, improve held-out robust score by at least 0.03 over Soil, and retain at least 90% of Soil passive cash. Otherwise exact Soil is selected.

## Outputs

- `v3_screen_scores.csv`
- `v3_heldout_scores.csv`
- `v3_family_matrix.csv`
- `frontier_source_provenance.csv`
- `NEXT_SUBMIT_manifest.json`
- `NEXT_SUBMIT_v3_frontier.tar.gz`
- `RUNNER_UP_v3_frontier.tar.gz`

## Live ladder sequence

1. Run `notebooks/13_v3_frontier_transplant_lab.ipynb` on Kaggle CPU.
2. Submit `NEXT_SUBMIT_v3_frontier.tar.gz`.
3. Keep the runner-up packaged, but wait for the first hosted result before spending another slot.
4. Diagnose the first live result by opponent family and replay behavior, then promote the runner-up or a targeted repair.
