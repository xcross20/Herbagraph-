"""Pure risk classifier. Fail closed to founder-gate. Does not merge or deploy."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

POLICY_PATH = Path(__file__).resolve().parents[2] / "docs" / "agent-workflow" / "risk-tiers.yml"

TIER_AUTONOMOUS = "autonomous-uat"
TIER_GUARDED = "autonomous-uat-guarded"
TIER_FOUNDER = "founder-gate"
TIER_BLOCKED = "agent-blocked"

REQUIRED_DESCRIPTOR_FIELDS = (
    "target_environment",
    "deployment_action",
    "data_operation",
    "contract_compatible",
    "security_privacy_safety_effect",
    "reasoning_integrity_effect",
    "autonomous_permission_effect",
    "medical_posture_effect",
    "rollback_documented",
    "tests_present",
    "phi_introduced",
    "reversible",
    "change_class",
)


@dataclass(frozen=True)
class ChangeDescriptor:
    target_environment: str | None
    deployment_action: str | None
    data_operation: str | None
    contract_compatible: bool | None
    security_privacy_safety_effect: str | None
    reasoning_integrity_effect: str | None
    autonomous_permission_effect: str | None
    medical_posture_effect: str | None
    rollback_documented: bool | None
    tests_present: bool | None
    phi_introduced: bool | None
    reversible: bool | None
    change_class: str | None
    adr_present: bool | None = None
    feature_flagged: bool | None = None
    routine_blocker: str | None = None


@dataclass(frozen=True)
class RiskDecision:
    tier: str
    label: str
    founder_interrupt: bool
    reason: str


def load_policy(path: Path = POLICY_PATH) -> dict:
    if not path.is_file():
        raise ValueError("missing_risk_policy")
    return _parse_simple_yaml(path.read_text(encoding="utf-8"))


def _parse_simple_yaml(text: str) -> dict:
    """Constrained YAML: top maps, one nested map, string/bool/list values."""
    root: dict = {}
    current: dict | None = None
    current_key = ""
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        if indent == 0 and line.endswith(":"):
            current_key = line[:-1]
            root[current_key] = {}
            current = root[current_key]
            continue
        if indent == 0 and ":" in line:
            key, value = line.split(":", 1)
            root[key.strip()] = _scalar(value)
            current = None
            continue
        if current is None:
            raise ValueError("malformed_risk_policy")
        if indent == 2 and line.endswith(":") and not line.startswith("-"):
            name = line[:-1]
            current[name] = {}
            continue
        if indent == 2 and line.startswith("- "):
            current.setdefault("_list", []).append(_scalar(line[2:]))
            continue
        if indent >= 4 and ":" in line:
            parent_name = list(current)[-1]
            if not isinstance(current.get(parent_name), dict):
                raise ValueError("malformed_risk_policy")
            key, value = line.split(":", 1)
            current[parent_name][key.strip()] = _scalar(value)
    for key, value in list(root.items()):
        if isinstance(value, dict) and set(value) == {"_list"}:
            root[key] = value["_list"]
    return root


def _scalar(value: str):
    text = value.strip()
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        if not inner:
            return []
        return [item.strip() for item in inner.split(",")]
    if text in {"true", "false"}:
        return text == "true"
    return text


def classify(descriptor: ChangeDescriptor | None, *, policy: dict | None = None) -> RiskDecision:
    loaded = policy or load_policy()
    tiers = loaded.get("tiers") or {}
    if descriptor is None:
        return _decision(TIER_FOUNDER, tiers, "malformed_descriptor")
    missing = [name for name in REQUIRED_DESCRIPTOR_FIELDS if getattr(descriptor, name) is None]
    if missing:
        return _decision(TIER_FOUNDER, tiers, "missing_fields:" + ",".join(missing))

    if descriptor.routine_blocker:
        if _founder_door(descriptor):
            return _decision(TIER_FOUNDER, tiers, "founder_gate_overrides_routine_blocker")
        return _decision(TIER_BLOCKED, tiers, "routine_blocker:" + descriptor.routine_blocker)

    door = _founder_door(descriptor)
    if door:
        return _decision(TIER_FOUNDER, tiers, door)

    if descriptor.change_class == "schema_additive":
        if descriptor.adr_present and descriptor.rollback_documented and descriptor.tests_present:
            return _decision(TIER_GUARDED, tiers, "guarded_additive_schema")
        return _decision(TIER_FOUNDER, tiers, "guarded_change_missing_evidence")

    if (
        descriptor.target_environment == "uat"
        and descriptor.deployment_action in {"none", "uat_deploy"}
        and descriptor.reversible is True
        and descriptor.rollback_documented is True
        and descriptor.tests_present is True
        and descriptor.phi_introduced is False
    ):
        return _decision(TIER_AUTONOMOUS, tiers, "reversible_uat_change")

    return _decision(TIER_FOUNDER, tiers, "unclassified_fail_closed")


def _founder_door(descriptor: ChangeDescriptor) -> str:
    if descriptor.target_environment in {"main", "production"}:
        return "promote_or_deploy_main_production"
    if descriptor.deployment_action in {"promote_main", "production_deploy"}:
        return "promote_or_deploy_main_production"
    if descriptor.data_operation in {"destructive_production", "identity_rewrite", "irreversible"}:
        return "destructive_or_irreversible_production_data"
    if descriptor.contract_compatible is False:
        return "breaking_public_contract_without_compat"
    if descriptor.security_privacy_safety_effect in {"weaken", "redesign"}:
        return "weaken_or_redesign_auth_privacy_safety"
    if descriptor.medical_posture_effect not in {"none"}:
        return "medical_or_regulatory_posture"
    if descriptor.reasoning_integrity_effect not in {"none"}:
        return "reasoning_integrity_semantics"
    if descriptor.autonomous_permission_effect not in {"none"}:
        return "expand_autonomous_permissions"
    if descriptor.phi_introduced is True:
        return "weaken_or_redesign_auth_privacy_safety"
    if descriptor.reversible is False and descriptor.rollback_documented is False:
        return "unknown_blast_radius_or_unproven_rollback"
    return ""


def _decision(tier: str, tiers: dict, reason: str) -> RiskDecision:
    meta = tiers.get(tier) or {}
    return RiskDecision(
        tier=tier,
        label=str(meta.get("stop_label") or tier),
        founder_interrupt=bool(meta.get("founder_interrupt")),
        reason=reason,
    )
