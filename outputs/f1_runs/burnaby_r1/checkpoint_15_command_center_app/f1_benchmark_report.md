# F1 Benchmark Report

City: `burnaby_r1`

Run: `checkpoint_15_command_center_app`

## Release Gates

Overall passed: `true`

Failed gates: none

| Gate | Passed |
|---|---:|
| `verified_precision_is_1` | `true` |
| `false_verified_is_0` | `true` |
| `false_approval_is_0` | `true` |
| `retrieval_recall_at_6_ge_0_95` | `true` |
| `candidate_recall_ge_0_90` | `true` |
| `verified_source_support_complete` | `true` |
| `gis_verified_only` | `true` |
| `proposal_decision_accuracy_is_1` | `true` |
| `proposal_case_accuracy_is_1` | `true` |

## Metrics

| Metric | Value |
|---|---:|
| Gold rules | `40` |
| Retrieval recall at 6 | `0.95` |
| Candidate recall | `0.975` |
| Verified precision | `1.0` |
| Verified recall | `0.85` |
| False verified | `0` |
| Verified source-support failures | `0` |
| GIS verified-only | `true` |
| GIS review leaks | `0` |
| Proposal cases | `10` |
| Proposal decision accuracy | `1.0` |
| Proposal case accuracy | `1.0` |
| False approvals | `0` |

The benchmark does not promote rules or approve proposals. Failed gates are
upgrade targets, not permission to weaken verification.
