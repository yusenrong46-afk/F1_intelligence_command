"""M8.5 dependency graph metrics."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


def dependency_metrics(graph_or_dependencies: Any) -> dict[str, Any]:
    dependencies = _dependencies(graph_or_dependencies)
    status_counts = Counter(_field(dependency, "status") or "unknown" for dependency in dependencies)
    type_metrics: dict[str, Counter[str]] = defaultdict(Counter)
    for dependency in dependencies:
        dependency_type = _field(dependency, "dependency_type") or "unknown"
        status = _field(dependency, "status") or "unknown"
        type_metrics[dependency_type]["total"] += 1
        type_metrics[dependency_type][status] += 1
    return {
        "dependency_total_count": len(dependencies),
        "dependency_resolved_count": status_counts.get("resolved", 0),
        "dependency_unresolved_count": status_counts.get("unresolved", 0),
        "dependency_conflicting_count": status_counts.get("conflicting", 0),
        "dependency_not_applicable_count": status_counts.get("not_applicable", 0),
        "dependency_blocking_count": status_counts.get("unresolved", 0) + status_counts.get("conflicting", 0),
        "dependency_status_counts": dict(sorted(status_counts.items())),
        "dependency_type_metrics": {
            dependency_type: dict(sorted(counter.items()))
            for dependency_type, counter in sorted(type_metrics.items())
        },
    }


def _dependencies(graph_or_dependencies: Any) -> list[Any]:
    if graph_or_dependencies is None:
        return []
    if isinstance(graph_or_dependencies, dict):
        return list(graph_or_dependencies.get("dependencies") or [])
    if isinstance(graph_or_dependencies, (list, tuple)):
        return list(graph_or_dependencies)
    return list(getattr(graph_or_dependencies, "dependencies", ()) or [])


def _field(row: Any, name: str) -> Any:
    if isinstance(row, dict):
        return row.get(name)
    return getattr(row, name, None)
