# M8 Stakeholder Report

Date: 2026-06-29
Project: Burnaby R1 Zoning Verification System
Version covered: M8 MVP

## One-Line Message

M8 turns the M7 safety-ready zoning verifier into a more explainable, repair-aware, dashboard-ready system while preserving the core guarantee: unsupported rules do not become verified.

## Executive Summary

M7 established the project's most important foundation: a benchmark-driven, verification-first pipeline for Burnaby R1 zoning rules. It achieved zero false verified rules, zero false approvals, strong extraction coverage, adversarial safety, and verified-only GIS output.

M8 is an additive upgrade beside M7. It does not replace the verifier. Instead, it adds structured rule contracts, source-span tracking, hybrid retrieval, bounded repair attempts, dependency-aware status separation, M7-vs-M8 analytics, dashboard data providers, and an artifact-backed analytic chatbot.

The result is a system that is more transparent and more useful for debugging. M8 can now distinguish between a rule that is unsupported, a rule that needs review, and a rule that is blocked by missing context such as conditions, exceptions, covenants, heritage constraints, or cross-references.

The most important measured result is that M8 preserved M7 safety:

| Safety metric | M8 result |
|---|---:|
| False verified rules | 0 |
| False approvals | 0 |
| M7 safety preserved | true |
| GIS verified-only boundary preserved | true |
| Repair can promote directly | false |

M8 also reduced the broad review bucket by separating context issues from generic review work:

| Metric | M7 | M8 |
|---|---:|---:|
| Verified-like rules | 87 | 87 |
| Generic review-needed rules | 57 | 48 |
| Context-required rules | n/a | 9 |
| Repaired-successfully rules | n/a | 2 |

The key limitation is also clear: M8 improved diagnosis and safety structure, but it did not yet create new independent repair promotions from the new M8 repair loop. The repair loop recorded 171 attempts, but the two repaired-successfully rules are verifier-backed guarded bundle promotions inherited from the existing M7 path. In practical terms, M8 now explains why rules are blocked, but it is not yet strong enough to solve most blocked legal rules automatically.

## Why M8 Was Needed

M7 was safety-ready, but it still had three practical limitations:

1. Too many rules landed in a broad `review_needed` bucket.
2. It was difficult to tell whether a blocked rule was missing evidence, missing context, affected by a definition, or affected by an exception.
3. The dashboard and chatbot could show outputs, but they did not yet have a strong analytic layer for repair history, dependency gaps, evidence spans, and M7-vs-M8 comparison.

M8 addresses those limitations without weakening the M7 verifier.

## The Core Operating Principle

M8 keeps the same trust boundary as M7:

```text
Extraction proposes.
Retrieval finds missing context.
Repair patches weak candidates.
Verification proves or rejects.
Dashboard explains.
Chatbot analyzes.
GIS consumes only verified rules.
```

This matters because zoning rules are high-stakes. A model-generated rule should never become usable for GIS or proposal approval just because it sounds plausible. It must be supported by source evidence and pass deterministic checks.

## M7 to M8 Architecture Shift

### M7 Flow

```text
PDF/source corpus
-> source discovery and evidence packs
-> extraction candidates
-> source repair and matrix anchoring
-> deterministic verification
-> verified/review/rejected/not-used buckets
-> verified-only GIS/dashboard exports
```

### M8 Flow

```text
M7 artifacts or source blocks
-> structured rule contracts with source spans
-> hybrid retrieval and evidence bundles
-> bounded repair loop for weak candidates
-> dependency-aware verification wrapper
-> M7 vs M8 analytics
-> dashboard data providers
-> artifact-backed analytic chatbot
```

The architectural change is that M8 adds a reasoning and observability layer between extraction and final reporting. It gives the system better memory of what was tried, what evidence was found, why a rule is blocked, and what kind of human or automated follow-up is needed.

## What Was Built In M8

### 1. Structured Rule Contracts

M8 creates typed, serializable rule contracts. Instead of treating a zoning rule as loose text, it models the rule as fields:

| Field type | Purpose |
|---|---|
| Rule ID | Stable identity for traceability |
| Rule type | Height, setback, lot area, dwelling units, coverage, etc. |
| Value | Numeric or text value being claimed |
| Unit | Metres, square metres, percent, storeys, units, etc. |
| Operator | Maximum, minimum, equal, range, conditional |
| Scope | Zone, building type, lot condition, row/column context |
| Evidence pointers | Source-span support for the claim |
| Status | verified, repaired_successfully, context_required, review_needed, rejected, not_used |

This makes verification more auditable because each rule can be checked field by field.

### 2. Source-Span Tracking

M8 records source spans for evidence. A source span keeps the city, document, page, section, block type, character range, and supporting text.

This is important because a rule should not be verified only because a nearby page mentions a number. The source span needs to support the exact rule claim: value, unit, operator, and scope.

### 3. Hybrid Retrieval And Evidence Bundles

M8 adds local retrieval over source blocks. It supports exact lexical search, BM25-style ranking when available, deterministic fallback ranking, metadata filters, query planning, and evidence bundle construction.

The practical effect is that M8 can search for missing support when a candidate rule fails verification. It can produce an evidence bundle that says: this is the query, these are the retrieved spans, these were the ranking signals, and this is the source provenance.

### 4. Bounded Repair Loop

M8 added a repair loop, but with a strict safety boundary.

The repair loop does this:

```text
judge why the candidate failed
-> plan retrieval query
-> retrieve evidence
-> generate a minimal patch
-> apply patch to a copy of the candidate
-> rerun verification
-> record the outcome
```

The repair loop cannot directly promote a rule. It only proposes changes. Verification remains the only authority.

Measured repair activity:

| Repair category | Attempts |
|---|---:|
| General review | 87 |
| Missing scope | 63 |
| Missing condition | 18 |
| Missing exception | 3 |
| Total repair attempts | 171 |

Current measured outcome:

| Repair metric | Value |
|---|---:|
| M8 repair attempts | 171 |
| New M8-loop-generated successful repairs | 0 |
| Verifier-backed repaired-successfully rules preserved | 2 |

This is a conservative but correct result. M8 records useful repair work, but it does not claim successful repair unless verification proves it.

### 5. Dependency-Aware Verification

M8 adds more precise status separation. M7 could mark many uncertain cases as `review_needed`. M8 can now identify `context_required` when the candidate appears blocked by missing dependencies.

Measured unresolved dependency counts:

| Dependency type | Count |
|---|---:|
| Condition dependency | 6 |
| Covenant dependency | 4 |
| Cross-reference dependency | 4 |
| Exception or override dependency | 7 |
| Heritage dependency | 2 |

This helps future work because these rules require a different fix than simple evidence retrieval. They need legal context resolution.

### 6. M7-vs-M8 Analytics

M8 produces comparison artifacts between M7 and M8:

| Metric | M7 | M8 |
|---|---:|---:|
| Verified count | 87 | 85 |
| Repaired-successfully count | n/a | 2 |
| Verified-like count | 87 | 87 |
| Review-needed count | 57 | 48 |
| Context-required count | n/a | 9 |
| False verified count | 0 | 0 |
| False approval count | 0 | 0 |

The correct comparison is verified-like count, not just verified count. M8 separates two formerly verified-like cases as `repaired_successfully`, so verified plus repaired_successfully remains 87.

### 7. Dashboard And Chatbot Support

M8 added data providers and optional Streamlit pages for:

| Area | Purpose |
|---|---|
| M8 overview | Summarize status counts, safety, and run health |
| Rule explorer | Inspect structured rules and status reasons |
| Repair inspector | Show repair attempts, categories, and outcomes |
| Benchmark compare | Compare M7 and M8 metrics |
| M8 chatbot | Ask artifact-backed questions about the M8 run |

The chatbot is intentionally artifact-backed. It answers from generated M8 JSON outputs rather than free-form speculation.

M8 chatbot benchmark:

| Metric | Result |
|---|---:|
| Gold cases | 3 |
| Passed | 3 |
| Hard failures | 0 |

## M8 Measured Output

Generated output path:

```text
outputs/m8_runs/burnaby_r1/local_m8/
```

Main artifacts:

```text
source_spans.json
structured_rules.json
verification_decisions.json
repair_attempts.json
evidence_bundles.json
verification_report.json
m7_m8_comparison.json
m8_summary.json
m8_chatbot_context.json
m8_chatbot_eval.json
```

Measured M8 summary:

| Metric | Value |
|---|---:|
| Structured rules | 144 |
| Verified | 85 |
| Repaired successfully | 2 |
| Verified-like total | 87 |
| Context required | 9 |
| Review needed | 48 |
| Rejected | 0 |
| False verified | 0 |
| False approvals | 0 |
| Repair attempts | 171 |
| M7 safety preserved | true |

## Rule-Type Coverage

M8 coverage by rule type:

| Rule type | Verified-like / total | Coverage |
|---|---:|---:|
| automatic_sprinkler | 2 / 2 | 100.00% |
| building_separation | 14 / 22 | 63.64% |
| dwelling_units | 6 / 26 | 23.08% |
| fire_access_corridor | 2 / 4 | 50.00% |
| height | 20 / 26 | 76.92% |
| impervious_surface | 4 / 6 | 66.67% |
| lot_area | 4 / 10 | 40.00% |
| lot_coverage | 5 / 7 | 71.43% |
| permitted_use | 0 / 2 | 0.00% |
| setback | 18 / 27 | 66.67% |
| storeys | 12 / 12 | 100.00% |

Strong areas:

- Storeys
- Automatic sprinkler rules
- Height
- Lot coverage
- Setbacks and impervious surface rules, with remaining review cases

Weak areas:

- Permitted use
- Dwelling units
- Lot area
- Fire access corridor
- Rules that depend on exceptions, conditions, covenants, heritage constraints, or cross-references

## Validation Evidence

M8 was validated with a release check that ran both M7 and M8 gates.

Release check result:

| Check | Result |
|---|---:|
| Compile active code | Pass |
| M7 status | Pass |
| M7 Burnaby benchmark | Pass |
| M7 adversarial benchmark | Pass |
| M7 chatbot gold | Pass |
| M8 unit tests | Pass |
| M8 pipeline smoke | Pass |
| M8 chatbot gold | Pass |
| M8 summary exists | Pass |

Full test suite:

| Test run | Result |
|---|---:|
| Full repository tests | 609 passed, 3 subtests passed |

## What Improved

### Improvement 1: Better Safety Structure

M8 keeps the M7 proof gate intact. Repair and retrieval can propose, but they cannot approve. This prevents plausible but unsupported model outputs from flowing into GIS or proposal decisions.

### Improvement 2: More Useful Review Routing

M8 separates `context_required` from generic `review_needed`. This is important because context-required rules need a different workflow. They often require resolving a definition, exception, overlay, covenant, heritage condition, or cross-reference.

### Improvement 3: Evidence Is More Traceable

M8 uses source spans and evidence bundles. A reviewer can trace a decision back to the page, block, section, evidence ID, and retrieved span.

### Improvement 4: Debugging Is Much Easier

M8 records repair attempts. Instead of only seeing that a rule failed, we can see what the system tried, what evidence it retrieved, what patch it proposed, and why the verifier still rejected or held the rule.

### Improvement 5: Dashboard And Chatbot Can Become Analytical

M8 gives the dashboard and chatbot structured data. They can now answer questions like:

- How many rules are verified-like?
- Which rules were repaired successfully?
- Which rule types have weakest coverage?
- What dependency types block verification?
- Which rules should a reviewer inspect first?

## The Significant Gap

The biggest gap is that M8 is not yet independently solving the hardest legal-rule repair cases.

M8 is now better at diagnosis, evidence tracking, status separation, and review routing. But the new M8 repair loop did not generate new successful repairs on its own. It recorded 171 attempts, but the successful repaired rules came from verifier-backed guarded bundle promotions already supported by the M7 path.

Plain-language interpretation:

```text
M8 can now explain why many rules are blocked.
M8 cannot yet safely resolve most blocked legal rules automatically.
```

The remaining bottleneck is legal dependency completeness:

- Definitions
- Exceptions
- Cross-references
- Conditional clauses
- Table row and column context
- Covenants and heritage constraints
- Rule-family dependencies
- City-specific wording patterns

That is why 48 rules still remain in `review_needed`.

## Recommended M8.5 Direction

M8.5 should focus on turning M8 from a diagnostic scaffold into a stronger verification workbench.

Priority upgrades:

| Priority | Upgrade | Why it matters |
|---|---|---|
| 1 | Table-aware parsing and row/column lineage | Many zoning values depend on table context |
| 2 | Legal dependency graph | Conditions, definitions, exceptions, and cross-references need explicit links |
| 3 | Reviewer workbench | Human review should approve evidence-backed fixes without weakening automation |
| 4 | Repair evaluator | The system should prove what changed and why the patch is safe |
| 5 | Multi-city stress test | Burnaby success must generalize to Vancouver, Calgary, Surrey, and other formats |
| 6 | Artifact-grounded LLM chatbot | LLM wording can improve usability, but answers must stay bounded by verified artifacts |

## Recommended M9 Direction

M9 should move toward a city-scale regulatory intelligence system:

```text
multi-city ingestion
-> canonical legal rule graph
-> verified zoning rule registry
-> reviewer approval workflow
-> GIS/proposal compliance engine
-> dashboard and chatbot interface
-> continuous benchmark monitoring
```

The frontier opportunity is not just extraction. The stronger idea is a verification-first legal AI system that can explain, prove, repair, and operationalize zoning rules safely.

## Canva-Ready Slide Deck

### Slide 1: Title

Title:
M8: Verification-First AI for Zoning Rule Intelligence

Subtitle:
From safe extraction to explainable repair, review routing, dashboard analytics, and artifact-grounded chatbot support.

Visual:
Pipeline image with M7 as the safety core and M8 as the explainability and repair layer around it.

### Slide 2: The Problem

Headline:
Zoning rules are not normal text extraction.

Bullets:

- A plausible model answer is not enough.
- GIS and proposal decisions need exact source support.
- Rules depend on tables, exceptions, conditions, definitions, and cross-references.
- Unsafe automation can approve the wrong building proposal.

Visual:
Two-column contrast: "looks plausible" vs "verified by source evidence".

### Slide 3: What M7 Already Proved

Headline:
M7 established the safety foundation.

Metrics:

- False verified rules: 0
- False approvals: 0
- Burnaby verified precision: 1.00
- Adversarial cases blocked: 24/24
- M7 chatbot gold: 15/15

Visual:
Safety scorecard.

### Slide 4: Why M8 Was Added

Headline:
M7 was safe, but the system needed better diagnosis.

Bullets:

- Too many rules were broadly marked `review_needed`.
- The system needed to separate missing evidence from missing legal context.
- Repair attempts needed audit history.
- Dashboard and chatbot needed structured analytics.

Visual:
Funnel from `review_needed` into `context_required`, `repair_attempted`, and `human_review`.

### Slide 5: M8 Architecture

Headline:
M8 adds structure, retrieval, repair, and analytics without replacing the verifier.

Flow:

```text
M7 artifacts
-> structured rule contracts
-> source spans
-> hybrid retrieval
-> bounded repair attempts
-> dependency-aware verifier
-> dashboard and chatbot analytics
```

Visual:
Horizontal architecture diagram.

### Slide 6: What M8 Built

Headline:
The M8 layer makes every rule more traceable.

Bullets:

- Structured rule schema
- Source-span evidence tracking
- Evidence bundle retrieval
- Bounded repair loop
- Dependency-aware status separation
- M7-vs-M8 comparison analytics
- Dashboard pages and chatbot benchmark

Visual:
Seven capability tiles.

### Slide 7: Measured M8 Results

Headline:
M8 preserved safety while improving review clarity.

Metrics:

- Structured rules: 144
- Verified: 85
- Repaired successfully: 2
- Verified-like total: 87
- Context required: 9
- Review needed: 48
- False verified: 0
- False approvals: 0

Visual:
Bar chart for status distribution.

Chart data:

| Status | Count |
|---|---:|
| Verified | 85 |
| Repaired successfully | 2 |
| Context required | 9 |
| Review needed | 48 |

### Slide 8: M7 vs M8

Headline:
M8 did not chase more approvals. It created clearer review intelligence.

Comparison:

| Metric | M7 | M8 |
|---|---:|---:|
| Verified-like | 87 | 87 |
| Review needed | 57 | 48 |
| Context required | n/a | 9 |
| False verified | 0 | 0 |

Visual:
Before/after comparison chart.

### Slide 9: Repair Findings

Headline:
M8 records repair attempts, but keeps verification authoritative.

Metrics:

- Total repair attempts: 171
- General review: 87
- Missing scope: 63
- Missing condition: 18
- Missing exception: 3
- New M8-loop-generated successful repairs: 0

Message:
This is a safety-positive result. The system tried repairs, but did not promote unsupported patches.

Visual:
Repair attempt breakdown chart.

### Slide 10: Dependency Gaps

Headline:
The hard cases are legal-context problems.

Dependency counts:

- Exception or override dependency: 7
- Condition dependency: 6
- Covenant dependency: 4
- Cross-reference dependency: 4
- Heritage dependency: 2

Visual:
Dependency network diagram.

### Slide 11: The Significant Gap

Headline:
M8 explains blocked rules, but does not yet resolve most of them.

Main point:
The frontier problem is not extraction alone. It is verified legal reasoning across tables, definitions, exceptions, and context dependencies.

Bullets:

- 48 rules still need review.
- New M8 repair loop has not yet generated independent verified promotions.
- Cross-city generalization is not yet proven.

Visual:
Gap bridge from "diagnosis" to "verified repair".

### Slide 12: M8.5 Roadmap

Headline:
Next step: turn M8 into a verification workbench.

Priorities:

- Table-aware parsing
- Legal dependency graph
- Human review workflow
- Repair evaluator
- Multi-city stress test
- Artifact-grounded LLM chatbot

Visual:
Roadmap timeline: M8 -> M8.5 -> M9.

### Slide 13: Final Takeaway

Headline:
M8 is a safer, more explainable foundation for regulatory AI.

Closing message:
M8 does not claim to solve legal automation end-to-end. It builds the infrastructure needed to do it responsibly: traceable evidence, bounded repair, deterministic verification, dashboard analytics, and honest measurement.

Visual:
Verified-only pathway ending in GIS and proposal compliance.

## Canva Visual Style Recommendation

Use a serious technical-report style:

- Background: white or very light neutral
- Accent colors: deep blue for verified, amber for context-required, red/orange for review-needed, green for safety metrics
- Typography: clean sans-serif
- Layout: dense but readable, like an engineering review deck
- Avoid decorative gradients or generic AI imagery
- Prefer diagrams, tables, scorecards, and pipeline visuals

Suggested visual motifs:

- Evidence spans as highlighted document snippets
- Verification gate as a locked checkpoint
- Repair loop as a bounded cycle
- Dashboard/chatbot as downstream analytic surfaces
- GIS as verified-only output

## Canva Generation Prompt

Use this prompt in Canva if generating a presentation:

```text
Create a polished 13-slide technical stakeholder presentation titled "M8: Verification-First AI for Zoning Rule Intelligence".

Audience: capstone evaluators, technical mentors, planning-tech stakeholders, and software engineering reviewers.

Tone: serious, credible, engineering-led, evidence-backed. Avoid marketing fluff. The story should show that M8 improves explainability and safety while honestly stating that independent legal repair remains the major frontier gap.

Visual style: clean white/light neutral background, deep blue verified metrics, amber context-required metrics, red/orange review-needed metrics, green safety metrics. Use architecture diagrams, scorecards, tables, funnel charts, and before/after comparisons. Avoid generic AI robot imagery.

Core message: M8 is an additive layer beside M7. It adds structured rule contracts, source-span tracking, hybrid retrieval, bounded repair attempts, dependency-aware verification, M7-vs-M8 analytics, dashboard pages, and artifact-backed chatbot support. It preserves M7 safety: false verified rules = 0 and false approvals = 0.

Key measured metrics:
- Structured rules: 144
- Verified: 85
- Repaired successfully: 2
- Verified-like total: 87
- Context required: 9
- Review needed: 48
- False verified: 0
- False approvals: 0
- Repair attempts: 171
- M8 chatbot gold: 3/3
- Full tests: 609 passed, 3 subtests passed

Slide plan:
1. Title
2. The problem: zoning rules are not normal text extraction
3. What M7 already proved
4. Why M8 was added
5. M8 architecture
6. What M8 built
7. Measured M8 results
8. M7 vs M8 comparison
9. Repair findings
10. Dependency gaps
11. Significant gap
12. M8.5 roadmap
13. Final takeaway
```

## Short Speaking Script

M8 is the next upgrade after the M7 safety-ready pipeline. M7 proved that the system could extract and verify Burnaby R1 zoning rules without false verified rules or false approvals. M8 keeps that safety boundary, but adds the missing infrastructure for explainability and repair.

The biggest change is that rules are no longer just candidate outputs. They now have structured fields, source spans, evidence bundles, dependency checks, repair history, and status explanations. This makes the system easier to debug, easier to review, and more useful for dashboard and chatbot interfaces.

The measured result is conservative but important. M8 preserved the zero-false-verified safety guarantee. It produced 144 structured rules, 87 verified-like rules, 9 context-required rules, and reduced the generic review-needed bucket from 57 to 48.

The honest gap is that M8 is not yet automatically solving the hardest legal cases. The repair loop recorded 171 attempts, but it did not independently create new successful repairs. That tells us the next frontier is not just better prompting. It is table-aware parsing, legal dependency graphs, human review workflows, and multi-city validation.

The takeaway is that M8 moves the project from extraction plus verification toward a true regulatory intelligence platform: evidence-aware, repair-aware, benchmark-driven, and safe by design.
