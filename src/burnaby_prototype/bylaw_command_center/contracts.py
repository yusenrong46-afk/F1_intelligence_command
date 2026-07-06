"""F1 artifact contracts and fail-closed validation helpers.

These dataclasses are deliberately dependency-light. They establish the stable
shape of the F1 product layer without importing model, RAG, verifier, dashboard,
or GIS code. Promotion remains verifier-only: constructors reject unsafe states
instead of trying to repair them implicitly.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, ClassVar


ARTIFACT_SCHEMA_VERSION = "f1.artifacts.v0"

CANONICAL_ARTIFACT_NAMES: tuple[str, ...] = (
    "source_registry.json",
    "document_blocks.json",
    "source_spans.json",
    "retrieval_report.json",
    "candidate_rules.json",
    "verification_decisions.json",
    "verified_rules.json",
    "review_queue.json",
    "repair_attempts.json",
    "repair_rerun_report.json",
    "gis_rule_contract.json",
    "compliance_decisions.json",
    "chatbot_eval.json",
    "f1_summary.json",
)

RULE_STATUSES = {"candidate", "verified", "review_needed", "context_required", "rejected", "not_used"}
DECISION_STATUSES = {"verified", "repaired_successfully", "review_needed", "context_required", "rejected", "not_used"}
COMPLIANCE_STATUSES = {"approved", "rejected", "needs_review"}


@dataclass(frozen=True)
class ContractMixin:
    schema_version: str = ARTIFACT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SourceDocument(ContractMixin):
    source_id: str = ""
    city: str = ""
    title: str = ""
    bylaw_version: str = ""
    source_url: str = ""
    sha256: str = ""
    fetched_at: str = ""
    local_path: str = ""
    bytes: int | None = None
    page_count: int | None = None
    scoped_pages: list[Any] = field(default_factory=list)
    pages_rationale: str = ""
    target_concept: str = ""
    hash_verified: bool = False
    status: str = "registered"

    def __post_init__(self) -> None:
        _require(self.source_id, "source_id is required")
        _require(self.city, "city is required")
        _require(self.title, "title is required")
        if self.bytes is not None and self.bytes < 0:
            raise ValueError("bytes must be non-negative")
        if self.page_count is not None and self.page_count < 0:
            raise ValueError("page_count must be non-negative")


@dataclass(frozen=True)
class DocumentBlock(ContractMixin):
    block_id: str = ""
    source_id: str = ""
    city: str = ""
    page: int | None = None
    block_type: str = "text"
    section_id: str = ""
    heading: str = ""
    text: str = ""
    parent_block_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require(self.block_id, "block_id is required")
        _require(self.source_id, "source_id is required")
        _require(self.city, "city is required")
        if self.page is not None and self.page < 0:
            raise ValueError("page must be non-negative")


@dataclass(frozen=True)
class SourceSpan(ContractMixin):
    span_id: str = ""
    source_id: str = ""
    block_id: str = ""
    city: str = ""
    page: int | None = None
    section_id: str = ""
    block_type: str = "text"
    char_start: int = 0
    char_end: int = 0
    text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require(self.span_id, "span_id is required")
        _require(self.source_id, "source_id is required")
        _require(self.city, "city is required")
        _require(self.text, "source span text is required")
        if self.page is not None and self.page < 0:
            raise ValueError("page must be non-negative")
        if self.char_start < 0 or self.char_end < self.char_start:
            raise ValueError("source span offsets are invalid")


@dataclass(frozen=True)
class TableCellSpan(ContractMixin):
    cell_id: str = ""
    source_id: str = ""
    table_id: str = ""
    row_index: int = 0
    column_index: int = 0
    row_header: str = ""
    column_header: str = ""
    text: str = ""
    source_span_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require(self.cell_id, "cell_id is required")
        _require(self.table_id, "table_id is required")
        _require(self.source_span_id, "source_span_id is required")
        if self.row_index < 0 or self.column_index < 0:
            raise ValueError("table cell coordinates must be non-negative")


@dataclass(frozen=True)
class VisualRegion(ContractMixin):
    region_id: str = ""
    source_id: str = ""
    page: int = 0
    region_type: str = "figure"
    bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    caption: str = ""
    linked_span_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require(self.region_id, "region_id is required")
        _require(self.source_id, "source_id is required")
        if self.page < 0:
            raise ValueError("page must be non-negative")
        if len(self.bbox) != 4:
            raise ValueError("bbox must have four coordinates")


@dataclass(frozen=True)
class RetrievalEvidence(ContractMixin):
    evidence_id: str = ""
    query: str = ""
    span_id: str = ""
    rank: int = 0
    score: float = 0.0
    retrieval_method: str = "hybrid"
    reranker: str = ""
    quote: str = ""
    supports_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require(self.evidence_id, "evidence_id is required")
        _require(self.span_id, "span_id is required")
        if self.rank < 0:
            raise ValueError("rank must be non-negative")


@dataclass(frozen=True)
class CandidateRule(ContractMixin):
    rule_id: str = ""
    city: str = ""
    zone: str = ""
    rule_type: str = ""
    rule_object: str = ""
    constraint_scope: str = ""
    applies_to: str = ""
    operator: str = ""
    value: str = ""
    unit: str = ""
    condition: str = ""
    exception: str = ""
    evidence_ids: tuple[str, ...] = ()
    status: str = "review_needed"
    raw: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require(self.rule_id, "rule_id is required")
        _require(self.city, "city is required")
        if self.status not in RULE_STATUSES:
            raise ValueError(f"unknown rule status: {self.status}")
        if self.status == "verified" and not self.evidence_ids:
            raise ValueError("verified candidate rules require evidence_ids")


@dataclass(frozen=True)
class VerificationDecision(ContractMixin):
    PROMOTED_STATUSES: ClassVar[set[str]] = {"verified", "repaired_successfully"}

    rule_id: str = ""
    status: str = "review_needed"
    reason: str = ""
    evidence_ids: tuple[str, ...] = ()
    support_gaps: tuple[str, ...] = ()
    unresolved_dependencies: tuple[str, ...] = ()
    risk_flags: tuple[str, ...] = ()
    repair_history: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require(self.rule_id, "rule_id is required")
        if self.status not in DECISION_STATUSES:
            raise ValueError(f"unknown verification status: {self.status}")
        if self.status in self.PROMOTED_STATUSES:
            if not self.evidence_ids:
                raise ValueError("promoted decisions require evidence_ids")
            if self.support_gaps or self.unresolved_dependencies or self.risk_flags:
                raise ValueError("promoted decisions cannot have gaps, dependencies, or risk flags")


@dataclass(frozen=True)
class RepairPatch(ContractMixin):
    patch_id: str = ""
    rule_id: str = ""
    changed_fields: dict[str, Any] = field(default_factory=dict)
    field_proofs: dict[str, dict[str, Any]] = field(default_factory=dict)
    action: str = "review_only"
    risk_flags: tuple[str, ...] = ()
    model: str = ""

    def __post_init__(self) -> None:
        _require(self.patch_id, "patch_id is required")
        _require(self.rule_id, "rule_id is required")
        if self.action in {"mark_verified", "approve", "verified"}:
            raise ValueError("repair patches cannot promote or approve rules")
        for field_name in self.changed_fields:
            proof = self.field_proofs.get(field_name)
            if not proof or not proof.get("evidence_id") or not proof.get("quote"):
                raise ValueError(f"changed field lacks proof: {field_name}")


@dataclass(frozen=True)
class ReviewPacket(ContractMixin):
    packet_id: str = ""
    rule_id: str = ""
    status: str = "review_needed"
    question: str = ""
    evidence_ids: tuple[str, ...] = ()
    suggested_actions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require(self.packet_id, "packet_id is required")
        _require(self.rule_id, "rule_id is required")
        if self.status in {"verified", "repaired_successfully"}:
            raise ValueError("review packets cannot carry promoted statuses")


@dataclass(frozen=True)
class ComplianceScenario(ContractMixin):
    scenario_id: str = ""
    city: str = ""
    zone: str = ""
    proposal: dict[str, Any] = field(default_factory=dict)
    source_rule_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require(self.scenario_id, "scenario_id is required")
        _require(self.city, "city is required")


@dataclass(frozen=True)
class ComplianceDecision(ContractMixin):
    scenario_id: str = ""
    status: str = "needs_review"
    reason: str = ""
    verified_rule_ids: tuple[str, ...] = ()
    review_rule_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require(self.scenario_id, "scenario_id is required")
        if self.status not in COMPLIANCE_STATUSES:
            raise ValueError(f"unknown compliance status: {self.status}")
        if self.status == "approved" and not self.verified_rule_ids:
            raise ValueError("approved compliance decisions require verified_rule_ids")
        if self.status == "approved" and self.review_rule_ids:
            raise ValueError("approved compliance decisions cannot depend on review rules")


@dataclass(frozen=True)
class ChatAnswer(ContractMixin):
    answer_id: str = ""
    question: str = ""
    answer: str = ""
    cited_evidence_ids: tuple[str, ...] = ()
    uncertainty: str = ""
    can_answer: bool = True

    def __post_init__(self) -> None:
        _require(self.answer_id, "answer_id is required")
        _require(self.question, "question is required")
        if self.can_answer and not self.cited_evidence_ids:
            raise ValueError("answerable chatbot responses require cited evidence")


def artifact_manifest(*, city: str, run_id: str, source_id: str = "", bylaw_version: str = "") -> dict[str, Any]:
    """Return the standard F1 artifact manifest for a run."""
    _require(city, "city is required")
    _require(run_id, "run_id is required")
    return {
        "schema_version": ARTIFACT_SCHEMA_VERSION,
        "city": city,
        "run_id": run_id,
        "source_id": source_id,
        "bylaw_version": bylaw_version,
        "artifact_names": list(CANONICAL_ARTIFACT_NAMES),
    }


def _require(value: Any, message: str) -> None:
    if value is None or value == "":
        raise ValueError(message)
