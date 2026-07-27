from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal


InteractionKind = Literal["REQ", "REP", "OBS", "DSP"]
NodeType = Literal["bot", "user"]
ACCOUNT_ID_PLACEHOLDERS = frozenset(
    {"qq_official", "unknown_selfid", "unknown_self_id"}
)


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def is_placeholder_account_id(value: Any) -> bool:
    return clean_text(value).casefold() in ACCOUNT_ID_PLACEHOLDERS


def usable_account_id(value: Any) -> str:
    account_id = clean_text(value)
    return "" if not account_id or is_placeholder_account_id(account_id) else account_id


def clean_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "是"}
    return bool(value)


def clean_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if math.isfinite(parsed) else default


@dataclass(frozen=True, slots=True)
class BotNode:
    bot_id: str
    display_name: str
    account_id: str
    persona_id: str = ""
    provider_id: str = ""
    description: str = ""
    capabilities: tuple[str, ...] = field(default_factory=tuple)
    aliases: tuple[str, ...] = field(default_factory=tuple)
    platform_id: str = ""
    node_type: NodeType = "bot"

    @classmethod
    def from_mapping(
        cls,
        data: dict[str, Any],
        *,
        node_type: NodeType | None = None,
    ) -> "BotNode":
        capabilities_raw = data.get("capabilities", [])
        if isinstance(capabilities_raw, str):
            capabilities = tuple(
                item.strip() for item in capabilities_raw.split(",") if item.strip()
            )
        elif isinstance(capabilities_raw, list):
            capabilities = tuple(
                clean_text(item) for item in capabilities_raw if clean_text(item)
            )
        else:
            capabilities = ()
        aliases_raw = data.get("aliases", [])
        if isinstance(aliases_raw, str):
            aliases = tuple(
                item.strip() for item in aliases_raw.split(",") if item.strip()
            )
        elif isinstance(aliases_raw, list):
            aliases = tuple(
                clean_text(item) for item in aliases_raw if clean_text(item)
            )
        else:
            aliases = ()
        resolved_type = node_type or clean_text(data.get("node_type")) or "bot"
        if resolved_type not in {"bot", "user"}:
            resolved_type = "bot"
        bot_id = clean_text(
            data.get("bot_id")
            or data.get("user_id")
            or data.get("node_id")
        )
        return cls(
            bot_id=bot_id,
            display_name=clean_text(data.get("display_name")) or bot_id,
            account_id=clean_text(
                data.get("account_id") or data.get("platform_user_id")
            ),
            node_type=resolved_type,
            persona_id=clean_text(data.get("persona_id")),
            provider_id=clean_text(data.get("provider_id")),
            description=clean_text(data.get("description")),
            capabilities=capabilities,
            aliases=aliases,
            platform_id=clean_text(data.get("platform_id")),
        )


@dataclass(frozen=True, slots=True)
class Relation:
    source_bot_id: str
    target_bot_id: str
    group_id: str = ""
    relation_type: str = "acquaintance"
    allow_ask: bool = True
    trust: float = 0.5
    tone: str = ""
    share_context: bool = False
    address_as: str = ""
    familiarity: float = 0.0
    affinity: float = 0.0
    romantic_interest: float = 0.0
    allow_flirt: bool = False
    allow_interject: bool = False
    allow_evolve: bool = True
    interject_priority: float = 1.0
    origin: str = "manual"
    confidence: float = 1.0
    evidence: str = ""
    prompt_hash: str = ""

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "Relation":
        trust = max(0.0, min(1.0, clean_float(data.get("trust"), 0.5)))
        familiarity = max(
            0.0, min(1.0, clean_float(data.get("familiarity"), 0.0))
        )
        affinity = max(-1.0, min(1.0, clean_float(data.get("affinity"), 0.0)))
        romantic_interest = max(
            0.0, min(1.0, clean_float(data.get("romantic_interest"), 0.0))
        )
        confidence = max(
            0.0, min(1.0, clean_float(data.get("confidence"), 1.0))
        )
        interject_priority = max(
            0.01, min(100.0, clean_float(data.get("interject_priority"), 1.0))
        )
        return cls(
            source_bot_id=clean_text(data.get("source_bot_id")),
            target_bot_id=clean_text(data.get("target_bot_id")),
            group_id=clean_text(data.get("group_id") or data.get("scope_id"))[:128],
            relation_type=clean_text(data.get("relation_type")) or "acquaintance",
            allow_ask=clean_bool(data.get("allow_ask"), True),
            trust=trust,
            tone=clean_text(data.get("tone")),
            share_context=clean_bool(data.get("share_context"), False),
            address_as=clean_text(data.get("address_as")),
            familiarity=familiarity,
            affinity=affinity,
            romantic_interest=romantic_interest,
            allow_flirt=clean_bool(data.get("allow_flirt"), False),
            allow_interject=clean_bool(data.get("allow_interject"), False),
            allow_evolve=clean_bool(data.get("allow_evolve"), True),
            interject_priority=interject_priority,
            origin=clean_text(data.get("origin")) or "manual",
            confidence=confidence,
            evidence=clean_text(data.get("evidence")),
            prompt_hash=clean_text(data.get("prompt_hash")),
        )


@dataclass(frozen=True, slots=True)
class InteractionEnvelope:
    kind: InteractionKind
    interaction_id: str
    source_bot_id: str
    target_bot_id: str
    depth: int
    created_at: int
    signature: str = ""

    @property
    def is_request(self) -> bool:
        return self.kind == "REQ"

    @property
    def is_reply(self) -> bool:
        return self.kind == "REP"

    @property
    def is_observation(self) -> bool:
        return self.kind == "OBS"

    @property
    def is_display(self) -> bool:
        return self.kind == "DSP"
