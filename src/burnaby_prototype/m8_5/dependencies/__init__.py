"""Legal dependency graph modules for M8.5."""

from .cross_reference_index import CrossReferenceIndex, CrossReferenceTarget
from .definition_linker import DefinitionLinker, DefinitionRecord
from .dependency_graph import DependencyGraph, RuleDependency
from .dependency_resolver import DependencyResolution, DependencyResolver
from .exception_linker import ExceptionLinker

__all__ = [
    "CrossReferenceIndex",
    "CrossReferenceTarget",
    "DefinitionLinker",
    "DefinitionRecord",
    "DependencyGraph",
    "DependencyResolution",
    "DependencyResolver",
    "ExceptionLinker",
    "RuleDependency",
]

