# F1 Multi-City Report

Run: `checkpoint_13_multi_city`

Parser mode: `fallback`

| City | Status | Release label | Pages | Candidates | Verified | Review | GIS rules | False verified | False approvals | Runtime s |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| burnaby_r1 | completed | benchmark_with_proposals | 7 | 6 | 3 | 3 | 3 | 0 | 0 | 0.352 |
| vancouver_rs | completed | partial_benchmark_no_proposals | 22 | 3 | 0 | 3 | 0 | 0 | 0 | 0.68 |
| calgary_rcg | completed | partial_benchmark_no_proposals | 27 | 3 | 0 | 3 | 0 | 0 | 0 | 35.892 |
| surrey_r3 | completed | exploratory_no_gold | 12 | 5 | 0 | 5 | 0 | 0 | 0 | 19.345 |

## Totals

- Completed cities: `4`
- Failed cities: `0`
- Release-safe benchmark cities: `1`
- Exploratory or partial cities: `3`
- False verified total: `0`
- False approval total: `0`
- Runtime seconds: `56.274`

Cities without both gold rules and proposal cases are exploratory or partial, not release-safe.
