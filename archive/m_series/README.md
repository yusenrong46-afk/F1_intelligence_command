# M-Series Research Archive Index

F1 is the current product generation. The M-series remains the reproducible
research and development record that F1 learns from.

This archive index does not move or delete runnable artifacts. It records where
the prior-generation evidence lives so F1 can keep a clean current surface while
the M-series remains reproducible.

## M7

M7 established the verification-first product baseline:

- extraction proposes;
- RAG/discovery finds source context;
- source repair restores evidence context;
- deterministic verification decides;
- GIS consumes verified-only rules.

Key records:

```text
docs/M7_SYSTEM_HANDOFF.md
docs/M7_VERIFICATION_HANDOFF.md
docs/M7_OUTPUT_GUIDE.md
docs/M7_TEXTBOOK.html
outputs/m7_runs/<city>/google_gemini_3_1_flash_lite/
```

## M8

M8 added structured source spans, deterministic hybrid retrieval, bounded
repair attempts, dependency-aware status separation, dashboard pages, analytics,
and an artifact-backed analytic chatbot.

Key records:

```text
M8_PLAN.md
M8_RESULTS.md
docs/M8_TECHNICAL_HANDOFF_REPORT.md
outputs/m8_runs/
src/burnaby_prototype/m8/
```

## M8.5

M8.5 added repair evaluation, table lineage, dependency graph improvements,
review packets, repair reruns, guarded repair promotions, chatbot grounding
tests, and cross-city stress runs.

Key records:

```text
M8_5_PLAN.md
M8_5_RESULTS.md
outputs/m8_5_runs/
src/burnaby_prototype/m8_5/
```

## Pre-M7

Older records are physically archived under:

```text
archive/pre_m7_records/
```

## F1 Boundary

F1 may reuse ideas, metrics, and fixtures from the M-series, but active product
code and docs should use F1 names and contracts. Any M-series result used in F1
must be treated as historical evidence unless the F1 runner reproduces it.
