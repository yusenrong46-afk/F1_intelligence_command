"""Resolve rule-level legal dependencies into graph artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cross_reference_index import CrossReferenceIndex
from .definition_linker import DefinitionLinker
from .dependency_graph import DependencyGraph, RuleDependency
from .exception_linker import ExceptionLinker


@dataclass(frozen=True)
class DependencyResolution:
    rule_id: str
    base_status: str
    recommended_status: str
    dependencies: tuple[RuleDependency, ...]

    @property
    def graph(self) -> DependencyGraph:
        return DependencyGraph(self.dependencies)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "base_status": self.base_status,
            "recommended_status": self.recommended_status,
            "dependencies": [dependency.to_dict() for dependency in self.dependencies],
        }


class DependencyResolver:
    def __init__(
        self,
        *,
        cross_reference_index: CrossReferenceIndex | None = None,
        definition_linker: DefinitionLinker | None = None,
        exception_linker: ExceptionLinker | None = None,
    ) -> None:
        self.cross_reference_index = cross_reference_index or CrossReferenceIndex()
        self.definition_linker = definition_linker or DefinitionLinker()
        self.exception_linker = exception_linker or ExceptionLinker()

    def resolve_rule(self, rule: dict[str, Any]) -> DependencyResolution:
        rule_id = str(rule.get("rule_id") or rule.get("candidate_id") or "")
        base_status = str(rule.get("verification_decision") or rule.get("status") or "review_needed")
        text = _rule_text(rule)
        dependencies: list[RuleDependency] = []
        dependencies.extend(self._cross_reference_dependencies(rule_id, text))
        dependencies.extend(self._definition_dependencies(rule_id, text))
        dependencies.extend(self._exception_dependencies(rule_id, text))
        graph = DependencyGraph(dependencies)
        return DependencyResolution(
            rule_id=rule_id,
            base_status=base_status,
            recommended_status=graph.status_for_rule(rule_id, base_status=base_status),
            dependencies=tuple(dependencies),
        )

    def resolve_rules(self, rules: list[dict[str, Any]]) -> DependencyGraph:
        dependencies: list[RuleDependency] = []
        for rule in rules:
            dependencies.extend(self.resolve_rule(rule).dependencies)
        return DependencyGraph(dependencies)

    def _cross_reference_dependencies(self, rule_id: str, text: str) -> list[RuleDependency]:
        dependencies = []
        for reference in self.cross_reference_index.extract(text):
            target = self.cross_reference_index.lookup(reference)
            if target is None:
                dependencies.append(
                    RuleDependency(
                        source_rule_id=rule_id,
                        dependency_type="cross_reference",
                        target_reference=reference,
                        status="unresolved",
                        reason="Referenced section was not found in the source index.",
                        resolver_confidence=0.85,
                    )
                )
                continue
            status = "conflicting" if target.status == "conflicting" else "resolved"
            dependencies.append(
                RuleDependency(
                    source_rule_id=rule_id,
                    dependency_type="cross_reference",
                    target_reference=reference,
                    status=status,
                    evidence_ids=target.evidence_ids,
                    reason=(
                        "Referenced section contradicts the candidate."
                        if status == "conflicting"
                        else "Referenced section was found and attached."
                    ),
                    resolver_confidence=0.9,
                    metadata={"text": target.text},
                )
            )
        return dependencies

    def _definition_dependencies(self, rule_id: str, text: str) -> list[RuleDependency]:
        dependencies = []
        for term in self.definition_linker.find_terms(text):
            record = self.definition_linker.lookup(term)
            if record is None:
                dependencies.append(
                    RuleDependency(
                        source_rule_id=rule_id,
                        dependency_type="definition",
                        target_reference=term,
                        status="unresolved",
                        reason="Definition term was detected but no definition record was attached.",
                        resolver_confidence=0.65,
                    )
                )
                continue
            dependencies.append(
                RuleDependency(
                    source_rule_id=rule_id,
                    dependency_type="definition",
                    target_reference=record.term,
                    status="resolved",
                    evidence_ids=record.evidence_ids,
                    reason="Definition record was found and attached.",
                    resolver_confidence=0.9,
                    metadata={"text": record.text},
                )
            )
        return dependencies

    def _exception_dependencies(self, rule_id: str, text: str) -> list[RuleDependency]:
        return [
            RuleDependency(
                source_rule_id=rule_id,
                dependency_type="exception",
                target_reference=reference,
                status="unresolved",
                reason="Exception or override wording requires reviewer or source-context resolution.",
                resolver_confidence=0.8,
            )
            for reference in self.exception_linker.extract_exceptions(text)
        ]


def _rule_text(rule: dict[str, Any]) -> str:
    parts = [
        rule.get("rule_sentence"),
        rule.get("condition"),
        rule.get("exception"),
        rule.get("applies_to"),
        rule.get("constraint_scope"),
        " ".join(str(gap) for gap in rule.get("support_gaps", []) or []),
    ]
    return " ".join(str(part or "") for part in parts)

