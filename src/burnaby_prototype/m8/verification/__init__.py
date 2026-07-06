"""M8 dependency-aware verification wrappers."""

from .dependency_checker import dependency_report
from .m8_verifier import verify_candidate_with_m7, verify_structured_rule

__all__ = ["dependency_report", "verify_candidate_with_m7", "verify_structured_rule"]
