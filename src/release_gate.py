"""Explicit production release guard for autonomous EDGE publishing.

This is a governance control, not a scoring rule. It prevents shadow-only
interpretation from reaching persistence until the user has separately approved
the shadow validation and the expected-price-zone implementation.

No thresholds, weights, probabilities, recommendation mappings, or execution
rules are changed here.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReleaseApproval:
    shadow_validation_accepted: bool = False
    zone_method_validated: bool = False
    autonomous_publishing_approved: bool = False


@dataclass(frozen=True)
class ReleaseGateResult:
    ready: bool
    blockers: tuple[str, ...]


def evaluate_release_gate(
    approval: ReleaseApproval,
    *,
    recommendation_text: str,
) -> ReleaseGateResult:
    blockers: list[str] = []

    if not approval.shadow_validation_accepted:
        blockers.append("live shadow validation has not been explicitly accepted")
    if not approval.zone_method_validated:
        blockers.append("expected-price-zone method has not been validated")
    if not approval.autonomous_publishing_approved:
        blockers.append("autonomous publishing has not been explicitly approved")
    if recommendation_text.strip().upper().startswith("SHADOW ONLY"):
        blockers.append("shadow-only recommendation cannot be published")

    return ReleaseGateResult(ready=not blockers, blockers=tuple(blockers))
