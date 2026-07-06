# M7 Presentation Note — Zoning Bylaw Rule Verifier

*Meeting talking-notes with structure + code illustrations. One sentence to anchor the whole thing:*

> **Propose with AI. Decide with deterministic rules. Let nothing else be the authority.**

---

## 1. The 30-second pitch

Canadian cities publish **zoning bylaws** — long legal PDFs (Calgary's is **1,053 pages**) that bury
rules like *"minimum side setback is 1.2 m"* in both prose **and** dimensional tables. Planners and GIS
teams need those as clean data (`setback ≥ 1.2 m, side`).

We built a system that:
1. **Reads** the bylaw and asks an LLM to **propose** candidate rules (job: *recall* — find everything).
2. Runs every candidate through a **deterministic verifier** that accepts a rule **only if** its exact
   value, unit, direction, and scope are literally in the cited source text (job: *precision* — admit
   only what's proven).

**The AI suggests; only the verifier decides.**

**Headline result (M7, audited against the actual PDFs):**

| City | Verified rules | Verified precision | False-verifies |
|---|---:|---:|---:|
| Burnaby R1 | **87** | 1.00 | **0** |
| Vancouver RS | **10** | 1.00 | **0** |
| Calgary R-CG | **29** | 1.00 | **0** |

`485 tests green · adversarial poison ALL BLOCKED · 0 false-verifies across all 3 cities.`

---

## 2. Why it's hard (the "so what")

- **Bylaws are long and messy** — rules hide in prose *and* in tables (dwelling-type × value matrices).
- **The same number means different things** — "1.2 m" could be a side setback, an easement width, or a
  fence height. Wrong *association* = a false published rule.
- **LLMs hallucinate** — 2025 studies show legal AI still hallucinates **17–33% of citations** even with
  retrieval. You cannot ship raw LLM output as law.
- **A wrong rule is expensive** — a bad "verified" setback could mis-approve a building. So the system's
  #1 job is to **never verify something the bylaw doesn't say** — even if that means parking some true
  rules in a human-review queue.

---

## 3. Architecture — the pipeline (one trust boundary)

```
   ┌──────────────┐
   │  Bylaw PDF   │  full document, page-scoped to the zone
   │ (1,053 pp.)  │
   └──────┬───────┘
          │
          ▼
   ┌──────────────────────────────────────────┐
   │  PROPOSER TIER  (allowed to be wrong)      │
   │                                            │
   │   Discovery / RAG ──► Matrix-table parser  │   ← deterministic table
   │        │                     │             │     cells, cell-by-cell
   │        ▼                     ▼             │
   │   Native LLM extraction (gemini-3.1)       │   ← prose candidates
   │        │                                   │
   │        ▼                                   │
   │   Source repair (re-anchor evidence)       │
   └──────────────────┬─────────────────────────┘
                      │
            rule_candidates + evidence_units      ← the ONE internal contract
                      │                              (every intake path normalizes to this)
                      ▼
   ╔════════════════════════════════════════════╗
   ║  AUTHORITY TIER — DETERMINISTIC VERIFIER     ║   ← no AI here. Same input
   ║                                              ║     → same output, always.
   ║   verification.py   (trust-gate loop)        ║
   ║   support_checks.py (value/unit/op/scope)    ║
   ║   decision_policy.py(gaps → bucket)          ║
   ╚════════════════════┬═════════════════════════╝
                        │
        ┌───────────┬───┴────┬───────────┐
        ▼           ▼        ▼           ▼
   ┌─────────┐ ┌─────────┐ ┌────────┐ ┌──────────┐
   │VERIFIED │ │ REVIEW  │ │REJECTED│ │ NOT_USED │
   │ (trust) │ │(needs   │ │(poison │ │(artifact │
   │         │ │ human)  │ │ /wrong)│ │ /out of  │
   └────┬────┘ └─────────┘ └────────┘ │  scope)  │
        │                              └──────────┘
        ▼
   ┌──────────────────────────────────────────────┐
   │  CONSUMERS (verified-only)                     │
   │  • GIS contract  • Felt/map export             │
   │  • Streamlit dashboard  • grounded chatbot     │
   └──────────────────────────────────────────────┘
```

**Key line for the room:** *Extraction proposes. Verification proves. GIS consumes only verified rules.*
Everything left of the double border is allowed to be creative; everything inside it is plain, auditable
code that is never wrong in the dangerous direction.

---

## 4. The code that *is* the trust boundary

The whole safety story reduces to one small, auditable function. A candidate collects `support_gaps`
(every deterministic check that failed). The decision is pure precedence over those gaps:

```python
# src/burnaby_prototype/decision_policy.py
def verification_decision_from_gaps(support_gaps: list[str]) -> str:
    """Return the verifier decision from BLOCKING support gaps only.

    Advisory upstream labels are excluded from the blocking set, but this
    does NOT relax any gate — value/unit/operator/scope/direction/exception
    checks are unchanged. It only stops a non-deterministic upstream label
    from vetoing the verifier.
    """
    gaps = set(support_gaps)
    blocking = gaps - ADVISORY_GAPS
    if not blocking:                          # every gate passed
        return VERIFIED
    if CRITICAL_REJECTION_GAPS & blocking:    # poisoned / contradicted
        return REJECTED
    if NOT_USED_GAPS & blocking:              # real artifact, not a rule
        return NOT_USED
    return REVIEW_NEEDED                       # plausible, needs a human
```

Why this is the heart of the design:
- **`if not blocking: return VERIFIED`** — a rule is trusted *only* when **zero** deterministic gates
  failed. There is no "confidence score," no "the model was pretty sure." Proven or not.
- **Precedence `CRITICAL > NOT_USED > REVIEW`** — when in doubt, fail *toward* safety (reject/review),
  never toward verified.
- **Deterministic** — same candidate + same evidence → same bucket, every run. That's what makes it
  auditable and testable (the 485-test suite pins exactly this).

The "gates" themselves live in `support_checks.py` (value, unit, operator **direction**, rule-object,
scope, applies-to, local evidence window, parent-clause context) and `table_natural_logic.py`
(table title × row header × column header × cell value).

---

## 5. What "verified" actually checks (a worked example)

Candidate the LLM proposed:  `side setback ≥ 1.2 m`

The verifier will only accept it if **all** of these are literally true in the cited clause:

| Gate | Question | Fail → |
|---|---|---|
| value | Is `1.2` in the quoted text? | reject |
| unit | Is it `m` (not ft, not %)? | reject |
| operator **direction** | Is it a **minimum** (≥), not a max? | reject (this inversion is the classic false-verify) |
| rule_object | Is the clause about a **setback**? | reject |
| scope / applies_to | Side line? this zone? this dwelling type? | review |
| evidence window | Is `1.2` in the *local* span, not just somewhere on the page? | review |

The real bug this caught in Calgary: a **1.2 m easement width** was being proposed as a **1.2 m side
setback** — same number, wrong rule object. The verifier's rule-object + parent-clause gates blocked it.
That's why Calgary is 29 verified, not 30.

---

## 6. What M7 added (the generational release)

| Area | Before | M7 |
|---|---|---|
| Table rules | prose-only, missed matrix cells | **matrix-aware extraction** — deterministic cell-by-cell binding |
| Calgary input | a 7-page slice | **full 1,053-page bylaw, page-scoped** to the zone (honest denominator) |
| Models | multi-model bakeoff noise | **single strongest model** (`gemini-3.1-flash-lite`) on the matrix pipeline |
| Recall (Calgary) | 16 verified, recall 0.84 | **29 verified, recall 1.00** — at precision 1.0, fv 0 |
| Chatbot | single retrieval pass | **two-stage retrieval + cross-encoder rerank** (fixes "what's the max height?") |

**Critical caveat we state honestly:** the recall gains come **entirely from better extraction**, not
from loosening the verifier. We even tried a verifier-side "rescue" to lift recall — it injected real
false-verifies, so we **reverted it**. The verifier sits at its *safe recall ceiling*.

---

## 7. Why it can be trusted (the proof)

1. **Separation of powers** — the creative part (LLM) literally *cannot* promote a rule; only the
   deterministic code in the authority tier can. Enforced by a boundary test (the verify path never
   imports extraction/LLM modules).
2. **Adversarial battery** — deliberately poisoned candidates (wrong value, inverted direction, foreign
   unit, easement-as-setback) are run every build and must be **ALL BLOCKED**.
3. **Ground-truth audit** — verified rules were checked against the **actual bylaw PDFs**, not just the
   gold set (that's how the Calgary easement bug surfaced).
4. **Gold is eval-only** — runtime verification never imports the answer key; no leakage.
5. **485 tests** pin the gates, the bucket precedence, the GIS export drift, and the dashboard.

---

## 8. The product surface (what a reviewer sees)

- **Dashboard** (Streamlit, read-only): per-city Summary · Review Queue · GIS Handoff · *Ask the Bylaw*
  chatbot. Every count tile drills down to the exact rules behind it; verified rules render as numbered
  plain-English sentences; review rules highlight the missing gap in red.
- **GIS contract** (`gis_rule_contract.json`): deduplicated, verified-only rules for downstream maps.
- **Grounded chatbot**: retrieves bylaw sections first, then the LLM reasons over *only* those and cites
  `(§section, p.page)`. Advisory — it never verifies, approves, or writes outputs.
- **Live cloud demo**: deployed on Streamlit Cloud (auto-redeploys from `main`).

---

## 9. Speaker cheat-sheet (if asked)

- *"Why not just use GPT/Gemini to read the bylaw?"* → It hallucinates 17–33% of citations. We use it as
  a proposer and gate every output deterministically. The AI is never the authority.
- *"Why is Vancouver only 10?"* → Conservative by design. Recall is *verified-or-review against a curated
  in-contract gold set*, not full-bylaw completeness. Anything not provable goes to review, not verified.
- *"How do you know it's safe?"* → Zero false-verifies under a ground-truth PDF audit + adversarial
  poison all blocked + 485 tests. And we reverted a recall boost because it leaked false-verifies.
- *"What's deterministic mean here?"* → No AI in the decision layer. Same input → same bucket, always.
  You can read the function (§4) and re-derive every verdict by hand.

---

*Structure reference: `docs/M7_PROJECT_STRUCTURE.md`. Full technical write-up: `docs/M7_TECH_DOC.md`
(and `.html`). Numbers reproduce via `scripts/run_consolidated_prototype.py status`.*
