# F1 Constitution

F1 is the product generation after the M-series research track. Its product name
is the Bylaw Intelligence Command Center.

F1 turns municipal bylaw documents into source-backed rules, review workflows,
GIS-ready constraints, compliance decisions, and an open-ended RAG chatbot. The
system is not allowed to trade safety for coverage.

## Core Law

1. Source documents are ground truth.
2. Extraction proposes candidate rules.
3. RAG retrieves evidence, not truth.
4. Repair proposes patches, never approval.
5. Verification is the only promotion authority.
6. Chatbot explains and navigates, but cannot verify or approve.
7. GIS and compliance consume verified-only rules.
8. No dry-run result may be described as a real measured result.
9. Every upgrade must be proven by benchmark or clearly labeled exploratory.
10. A city without a gold benchmark is exploratory only.

## Safety Gates

F1 inherits the M-series safety targets:

```text
false_verified_count = 0
false_approval_count = 0
verified_precision = 1.00
```

A rule can be promoted only when deterministic verification proves the required
fields against cited source evidence:

```text
rule_object
constraint_scope
applies_to
operator
value
unit
condition
exception
```

If evidence is incomplete, ambiguous, contradicted, or outside the current
contract, the rule goes to review, context required, rejected, or not used.

## Source Provenance Gate

F1 must know which official document it is reading before it can extract,
retrieve, verify, repair, chat, or export GIS constraints.

The source registry must preserve:

- official source URL;
- local cached path;
- SHA-256 hash;
- fetch timestamp;
- page count;
- scoped pages when a city uses a bylaw subsection;
- validation status.

If the cached PDF hash does not match provenance, the source is not safe for a
release claim.

## Product Boundaries

- Extraction confidence is not verification.
- RAG relevance is not verification.
- Repair confidence is not verification.
- Reviewer packet readiness is not verification.
- Chatbot fluency is not verification.
- Dashboard visibility is not verification.
- GIS export is downstream of verification only.

## Upgrade Gate

Before moving from F1 to any F1.x upgrade, the owner must be able to explain:

1. What the current version solves.
2. Current inputs and outputs.
3. Where hallucination or overfitting can enter.
4. What prevents false verification.
5. Which benchmark proves the next upgrade is better.
6. What should be removed or simplified before adding more.
7. What would make the upgrade unsafe.
