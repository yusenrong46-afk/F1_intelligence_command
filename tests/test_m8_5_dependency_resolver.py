from __future__ import annotations

from burnaby_prototype.m8_5.dependencies.cross_reference_index import CrossReferenceIndex
from burnaby_prototype.m8_5.dependencies.definition_linker import DefinitionLinker
from burnaby_prototype.m8_5.dependencies.dependency_resolver import DependencyResolver
from burnaby_prototype.m8_5.dependencies.exception_linker import ExceptionLinker


def test_unresolved_cross_reference_produces_context_required() -> None:
    resolver = DependencyResolver(cross_reference_index=CrossReferenceIndex())
    result = resolver.resolve_rule(
        {
            "rule_id": "rule_subject_to",
            "rule_sentence": "Maximum height is 10 m subject to Section 6.4.",
            "verification_decision": "verified",
        }
    )

    dependency = result.dependencies[0]

    assert dependency.dependency_type == "cross_reference"
    assert dependency.target_reference == "Section 6.4"
    assert dependency.status == "unresolved"
    assert result.recommended_status == "context_required"


def test_resolved_cross_reference_attaches_evidence() -> None:
    index = CrossReferenceIndex()
    index.add("Section 6.4", evidence_id="ev_6_4", text="Section 6.4 allows the height rule.")
    resolver = DependencyResolver(cross_reference_index=index)

    result = resolver.resolve_rule(
        {
            "rule_id": "rule_subject_to",
            "rule_sentence": "Maximum height is 10 m subject to Section 6.4.",
            "verification_decision": "verified",
        }
    )

    dependency = result.dependencies[0]

    assert dependency.status == "resolved"
    assert dependency.evidence_ids == ("ev_6_4",)
    assert result.recommended_status == "verified"


def test_resolved_definition_allows_verifier_to_continue() -> None:
    linker = DefinitionLinker({"principal building": ("ev_def_principal", "Principal building means the main building.")})
    resolver = DependencyResolver(definition_linker=linker)

    result = resolver.resolve_rule(
        {
            "rule_id": "rule_definition",
            "rule_sentence": "Maximum height for a principal building is 10 m.",
            "verification_decision": "verified",
        }
    )

    assert result.dependencies[0].dependency_type == "definition"
    assert result.dependencies[0].status == "resolved"
    assert result.recommended_status == "verified"


def test_exception_dependency_blocks_verification_until_resolved() -> None:
    resolver = DependencyResolver(exception_linker=ExceptionLinker())

    result = resolver.resolve_rule(
        {
            "rule_id": "rule_exception",
            "rule_sentence": "The rear setback is 9 m unless lane access is unavailable.",
            "verification_decision": "verified",
        }
    )

    assert result.dependencies[0].dependency_type == "exception"
    assert result.dependencies[0].status == "unresolved"
    assert result.recommended_status == "context_required"


def test_conflicting_cross_reference_prevents_verified_status() -> None:
    index = CrossReferenceIndex()
    index.add(
        "Section 6.4",
        evidence_id="ev_6_4",
        text="Section 6.4 says the candidate is not applicable.",
        status="conflicting",
    )
    resolver = DependencyResolver(cross_reference_index=index)

    result = resolver.resolve_rule(
        {
            "rule_id": "rule_conflict",
            "rule_sentence": "Maximum height is 10 m subject to Section 6.4.",
            "verification_decision": "verified",
        }
    )

    assert result.dependencies[0].status == "conflicting"
    assert result.recommended_status == "review_needed"
