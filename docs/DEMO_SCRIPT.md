# Demo script

Two versions: a 90-second demo and a 5-minute deep-dive. Both run offline from
committed artifacts with no API key. Status: `agent_draft_unreviewed`, a
draft for Thomas to adapt.

## Before you start (once)

```bash
make setup
make demo            # serves the command center on http://localhost:8631
```

In a second terminal, check it is up: `make demo-health` prints
`PASS http://127.0.0.1:8631/_stcore/health -> ok`. The screenshots in
`docs/demo/` show what each screen should look like.

Note: the dashboard opens on its Burnaby R1 demo run (38 verified rules from 51
checked). The benchmark numbers in the README (87 verified for Burnaby) come
from the full M7 run, scored by `make eval`. Say which one you are showing.

## 90-second demo

| Time | Show | Say |
|---|---|---|
| 0:00 | Command Center (`0 Command Center`) | "Zoning bylaws are long legal PDFs. Planners need the rules as data. An AI model reads the bylaw and proposes rules, but it never decides." |
| 0:15 | The Verified / Needs proof / Rejected tiles | "Every proposal goes through a deterministic verifier. Verified means the value, unit, direction and scope are all in the cited text. Anything uncertain is held for review." |
| 0:35 | `2 Verified Rules`, open a setback group | "Each verified rule shows its quoted source text and page, so you can check it against the bylaw yourself." |
| 0:55 | `3 Review Workbench` | "Review is not an error. It's the system refusing to guess. A planner sees why the rule is held and what to check." |
| 1:10 | README results table | "Across three cities: 126 verified rules, precision 1.00, zero false-verified rules, and all 34 poisoned test cases blocked. Run `make eval` to reproduce it offline." |
| 1:30 | End | |

## 5-minute deep-dive

1. **The trust boundary (0:00 to 0:45).** Open `src/burnaby_prototype/decision_policy.py`
   at `verification_decision_from_gaps`. "This short function is the whole
   authority. Gaps in, bucket out. Critical gap: rejected. Out of contract: not
   used. Anything else: review. No model output reaches it."
2. **A table trap (0:45 to 1:45).** Open `verification.py` at
   `_matrix_column_binding`. "A table cell can hold the right number for the
   wrong column, or only under a condition. 55% claimed for the wrong column is
   rejected; 45% without its transit-area condition is held."
3. **The range bug (1:45 to 2:45).** Show `_UNIT_RANGE_IN_TEXT_RE` and run
   `.venv/bin/python -m pytest -q tests/test_adversarial_hardening.py -k range`.
   "'1 to 3 Units; 4 to 6 Units' once let a 3 through as the lot maximum. The
   guard now holds it, and this test pins it."
4. **Poisoned inputs (2:45 to 3:30).** Run `make eval` and read the
   `poisoned 24/24 blocked` lines. "34 hand-written traps across three cities,
   plus three poisoned evidence bundles. CI fails if one leaks or if any count
   moves from its baseline."
5. **Use it from other code (3:30 to 4:15).** Run
   `.venv/bin/bylaw-verify --help`, then show `docs/ONBOARDING.md`. "A versioned
   CLI contract with JSON schemas and exit codes, and a one-command kit to add a
   city. A new city is exploratory until a person reviews its gold rules."
6. **Limits (4:15 to 5:00).** "Coverage is deliberately conservative: many real
   rules stay in review. A recall 'rescue' was tried, leaked false verifies and
   was reverted. Next work is better evidence assembly, not looser gates."

## Questions to expect

- *Why not let the model decide?* Because a plausible answer is not proof; the
  verifier needs the value in the cited text. (`docs/M7_PRESENTATION_NOTE.md` §9)
- *Why is Vancouver only 10?* Conservative by design: unproven rules go to review.
- *Is the cloud demo live?* Check before presenting; see `docs/DEPLOY_DEMO.md`.
