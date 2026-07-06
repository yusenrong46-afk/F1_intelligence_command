"""F1 Bylaw Intelligence Command Center contracts.

F1 is the product-facing layer after the M-series research track. The modules in
this package define the stable contracts that every ingestion, retrieval,
extraction, verification, repair, dashboard, chatbot, GIS, and compliance
component must share.
"""

from .contracts import (
    ARTIFACT_SCHEMA_VERSION,
    CANONICAL_ARTIFACT_NAMES,
    CandidateRule,
    ChatAnswer,
    ComplianceDecision,
    ComplianceScenario,
    DocumentBlock,
    RepairPatch,
    RetrievalEvidence,
    ReviewPacket,
    SourceDocument,
    SourceSpan,
    TableCellSpan,
    VerificationDecision,
    VisualRegion,
    artifact_manifest,
)
from .benchmark_eval import build_benchmark_eval_outputs, evaluate_benchmark_outputs, write_benchmark_eval_outputs
from .chatbot import (
    OpenRouterChatClient,
    build_chatbot_eval_outputs,
    build_model_chatbot_eval_outputs,
    build_model_chatbot_redteam_outputs,
    load_openrouter_api_key,
    write_chatbot_eval_outputs,
)
from .command_center import (
    build_command_center_app_outputs,
    build_command_center_outputs,
    write_command_center_app_outputs,
    write_command_center_outputs,
)
from .document_intelligence import (
    build_document_intelligence,
    build_document_intelligence_from_intermediate,
    write_document_intelligence,
)
from .gis_compliance import build_gis_compliance_outputs, evaluate_compliance_scenario, write_gis_compliance_outputs
from .multi_city import DEFAULT_MULTI_CITY_KEYS, run_multi_city_checkpoint, write_multi_city_report
from .proof_rag import DEFAULT_RETRIEVAL_QUERIES, build_retrieval_report, write_retrieval_report
from .product_operations import (
    build_product_operations_outputs,
    write_product_operations_outputs,
)
from .repair_review import build_guarded_repair_rerun_outputs, build_repair_review_outputs, write_repair_review_outputs
from .source_registry import build_source_registry, write_source_registry
from .structured_extraction import build_candidate_rules_from_retrieval, write_candidate_rules
from .verification import build_verification_outputs, write_verification_outputs

__all__ = [
    "ARTIFACT_SCHEMA_VERSION",
    "CANONICAL_ARTIFACT_NAMES",
    "DEFAULT_MULTI_CITY_KEYS",
    "DEFAULT_RETRIEVAL_QUERIES",
    "CandidateRule",
    "ChatAnswer",
    "ComplianceDecision",
    "ComplianceScenario",
    "DocumentBlock",
    "OpenRouterChatClient",
    "RepairPatch",
    "RetrievalEvidence",
    "ReviewPacket",
    "SourceDocument",
    "SourceSpan",
    "TableCellSpan",
    "VerificationDecision",
    "VisualRegion",
    "artifact_manifest",
    "build_benchmark_eval_outputs",
    "build_chatbot_eval_outputs",
    "build_model_chatbot_eval_outputs",
    "build_model_chatbot_redteam_outputs",
    "build_command_center_outputs",
    "build_command_center_app_outputs",
    "build_product_operations_outputs",
    "build_document_intelligence",
    "build_document_intelligence_from_intermediate",
    "build_gis_compliance_outputs",
    "build_guarded_repair_rerun_outputs",
    "build_retrieval_report",
    "build_repair_review_outputs",
    "build_source_registry",
    "build_candidate_rules_from_retrieval",
    "build_verification_outputs",
    "evaluate_compliance_scenario",
    "evaluate_benchmark_outputs",
    "load_openrouter_api_key",
    "run_multi_city_checkpoint",
    "write_document_intelligence",
    "write_gis_compliance_outputs",
    "write_multi_city_report",
    "write_retrieval_report",
    "write_repair_review_outputs",
    "write_source_registry",
    "write_candidate_rules",
    "write_chatbot_eval_outputs",
    "write_command_center_outputs",
    "write_command_center_app_outputs",
    "write_product_operations_outputs",
    "write_benchmark_eval_outputs",
    "write_verification_outputs",
]
