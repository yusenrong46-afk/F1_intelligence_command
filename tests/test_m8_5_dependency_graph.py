from __future__ import annotations

from burnaby_prototype.m8_5.dependencies.dependency_graph import DependencyGraph, RuleDependency


def test_dependency_graph_exports_json_and_supports_rule_lookup() -> None:
    dependency = RuleDependency(
        source_rule_id="burnaby_r1_010",
        dependency_type="cross_reference",
        target_reference="Section 6.4",
        status="unresolved",
        reason="Referenced section was not found in the source index.",
    )
    graph = DependencyGraph([dependency])

    exported = graph.to_dict()
    restored = DependencyGraph.from_dict(exported)

    assert exported["dependency_count"] == 1
    assert restored.for_rule("burnaby_r1_010")[0].dependency_id == dependency.dependency_id
    assert restored.for_rule("missing") == []


def test_dependency_graph_supports_dependency_type_metrics() -> None:
    graph = DependencyGraph(
        [
            RuleDependency(
                source_rule_id="rule_1",
                dependency_type="cross_reference",
                target_reference="Section 6.4",
                status="unresolved",
            ),
            RuleDependency(
                source_rule_id="rule_2",
                dependency_type="cross_reference",
                target_reference="Section 7.1",
                status="resolved",
                evidence_ids=("ev_7_1",),
            ),
            RuleDependency(
                source_rule_id="rule_3",
                dependency_type="exception",
                target_reference="unless lane access is unavailable",
                status="unresolved",
            ),
        ]
    )

    assert graph.status_counts() == {"resolved": 1, "unresolved": 2}
    assert graph.type_metrics() == {
        "cross_reference": {"total": 2, "resolved": 1, "unresolved": 1},
        "exception": {"total": 1, "unresolved": 1},
    }


def test_conflicting_dependency_prevents_verified_status() -> None:
    graph = DependencyGraph(
        [
            RuleDependency(
                source_rule_id="rule_conflict",
                dependency_type="cross_reference",
                target_reference="Section 6.4",
                status="conflicting",
                evidence_ids=("ev_6_4",),
                reason="Referenced section contradicts the candidate.",
            )
        ]
    )

    assert graph.status_for_rule("rule_conflict", base_status="verified") == "review_needed"
    assert graph.rule_has_blockers("rule_conflict") is True

