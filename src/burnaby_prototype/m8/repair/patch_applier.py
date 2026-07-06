"""Apply M8 repair patches to candidate copies."""

from __future__ import annotations

from typing import Any

from ..extraction.rule_schema import RepairPatch


def apply_patch_to_candidate(candidate: dict[str, Any], patch: RepairPatch) -> dict[str, Any]:
    updated = dict(candidate)
    updated.update(patch.changes)
    history = list(updated.get("m8_repair_patches") or [])
    history.append(patch.to_dict())
    updated["m8_repair_patches"] = history
    updated["m8_repair_only"] = True
    return updated
