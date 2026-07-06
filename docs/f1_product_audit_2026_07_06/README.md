# F1 Product Audit Screenshots

Captured from the live local Streamlit app at:

```text
http://localhost:8631/
```

## Captured Steps

| Step | Screenshot | Health |
|---|---|---|
| 1 | `01-overview-chat.png` | Final overview and chatbot surface render without errors. |
| 2 | `02-human-review.png` | Human review workbench renders with safe draft-action workflow. |
| 3 | `03-gis-handoff.png` | GIS handoff renders with verified-only scenario builder. |
| 4 | `04-quality-audit.png` | Quality audit renders benchmark and operations trace. |

## Audit Notes

- No active M8/M8.5 route labels appeared in the F1 product navigation.
- Checkpoint 16 is visible as the current run.
- The overview makes verified count, review count, precision, and false
  verified count visible before the user drills into tables.
- Chat answers render as structured cards with a direct answer, supporting
  facts, next step, and citations.
- Operator actions are explicitly framed as drafts, not promotions.
