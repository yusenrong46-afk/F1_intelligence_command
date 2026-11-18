# Case study: verification-first zoning rules

> Status: `agent_draft_unreviewed`. Drafted from four project documents only:
> `docs/M7_SYSTEM_HANDOFF.md`, `docs/M7_FINAL_RELEASE.md`,
> `docs/M7_PRESENTATION_NOTE.md` and `docs/M8_CANVA_STAKEHOLDER_REPORT.md`.
> Each factual sentence cites one of them. Where those documents do not record
> something (client words, reactions, decisions), this page says "not recorded"
> instead of filling the gap. Thomas should review it before it is shared.

## 1. Problem

Canadian cities publish zoning bylaws as long legal PDFs; Calgary's runs to
1,053 pages. Rules such as a minimum side setback sit in prose and in
dimensional tables, and planners and GIS teams need them as clean data.
[source: docs/M7_PRESENTATION_NOTE.md §1]

A plausible model answer is not enough: GIS and proposal decisions need exact
source support, and rules depend on tables, exceptions, conditions, definitions
and cross-references. [source: docs/M8_CANVA_STAKEHOLDER_REPORT.md §Slide 2]
The presentation note cites 2025 studies finding that legal AI still
hallucinates 17 to 33% of citations. [source: docs/M7_PRESENTATION_NOTE.md §2]

## 2. Discovery

The documents name the audience as capstone evaluators, technical mentors,
planning-tech stakeholders and software engineering reviewers.
[source: docs/M8_CANVA_STAKEHOLDER_REPORT.md §Canva Generation Prompt]
What the client said in discovery sessions, and who said it, is not recorded in
these documents.

What the work itself surfaced: the same number can mean different things. In
Calgary, a 1.2 m easement width was being proposed as a 1.2 m side setback. An
audit of verified rules against the actual bylaw PDFs surfaced it, and the
verifier's rule-object and parent-clause gates now block it, which is why
Calgary has 29 verified rules, not 30. [source: docs/M7_PRESENTATION_NOTE.md §5]
[source: docs/M7_PRESENTATION_NOTE.md §7]

## 3. Scope

The trust boundary was fixed early: extractors propose, retrieval finds
context, source repair restores source-backed evidence, the deterministic
verifier decides, and GIS consumes only verified rules. No confidence score, LLM
response, retrieval rank or dashboard action can promote a rule.
[source: docs/M7_SYSTEM_HANDOFF.md §Trust Boundary]

Burnaby R1 is the product scope; Vancouver and Calgary are generalization checks,
not product scope. [source: docs/M7_FINAL_RELEASE.md §What M7 Is]
Calgary is always treated as the full 1,053-page bylaw unless a command says it
is testing a slice. [source: docs/M7_SYSTEM_HANDOFF.md §Source Inventory]

## 4. Build

M7 consolidated one matrix-aware extraction path on
`google/gemini-3.1-flash-lite`: table values are bound column by column before
the text checks run. [source: docs/M7_FINAL_RELEASE.md §The Consolidated Matrix-Aware Pipeline]
Extraction is scoped to the district's pages from `provenance.json`, which keeps
retrieval inside the right district while preserving official page numbers.
[source: docs/M7_FINAL_RELEASE.md §Page-scope fix]

The `range_bound_not_maximum` guard closed a real false-verify class, where a
lower range bound in "1 to 3 Units; 4 to 6 Units" could be read as the lot
maximum. [source: docs/M7_FINAL_RELEASE.md §The Range-Bound Leak Fix]
A verifier-side recall "rescue" (C5) was measured, found to inject false
verifies, and reverted. [source: docs/M7_FINAL_RELEASE.md §The C5 Finding: Verifier-Recall Rescue Reverted]

M8 added structured rule contracts, source spans, evidence bundles, bounded
repair attempts and a separate `context_required` status beside the M7 verifier,
without replacing it. [source: docs/M8_CANVA_STAKEHOLDER_REPORT.md §Executive Summary]

## 5. Demo-back

The product surface shown to reviewers is a read-only Streamlit dashboard with a
review queue, a GIS handoff and a grounded chatbot that cannot verify or approve.
[source: docs/M7_PRESENTATION_NOTE.md §8]
The release runbook lists what to show: the safety contract, per-city results,
scored coverage, the C5 finding, the GIS handoff and the review queue.
[source: docs/M7_FINAL_RELEASE.md §What To Show Reviewers]

How the client or evaluators reacted to the demo is not recorded in these
documents. Deploying the cloud dashboard is an open item on the M7 checklist.
[source: docs/M7_FINAL_RELEASE.md §M7 Finalization Checklist]

## 6. Result

| City | Verified | Verified precision | False verified |
|---|---:|---:|---:|
| Burnaby R1 | 87 | 1.00 | 0 |
| Vancouver RS | 10 | 1.00 | 0 |
| Calgary R-CG | 29 | 1.00 | 0 |

[source: docs/M7_PRESENTATION_NOTE.md §1]

Calgary grew from 16 to 29 verified rules, and verified-or-review recall from
0.84 to 1.00, with no verifier gate loosened.
[source: docs/M7_FINAL_RELEASE.md §Per-City Results]
All poisoned adversarial cases were blocked (24 of 24 Burnaby, 6 of 6 Calgary,
4 of 4 Vancouver, 3 of 3 Burnaby bundles).
[source: docs/M7_FINAL_RELEASE.md §Safety Contract Held Throughout]

M8 kept 0 false verified rules and 0 false approvals and moved 9 rules from the
generic review bucket (57 to 48) into `context_required`. Its repair loop
recorded 171 attempts but produced no new independent repairs.
[source: docs/M8_CANVA_STAKEHOLDER_REPORT.md §Executive Summary]

Scored coverage stays conservative: Calgary scored verified coverage rose from
0.129 to 0.161. [source: docs/M7_FINAL_RELEASE.md §Scored Coverage (M7 scored Denominator)]

## 7. What I would change

This section is opinion, not fact, and is for Thomas to rewrite in Thomas's own
words.

- Record client conversations and demo reactions as they happen, so a case study
  can quote them instead of saying "not recorded".
- Pin source PDFs by content hash from day one and keep a cached copy, because
  three of the four official PDFs have since changed upstream (see
  `upgrade/STATUS.md`, Findings).
- Spend the next effort on evidence assembly and table-proof completeness, which
  both release documents name as the bottleneck, rather than on more extraction.
