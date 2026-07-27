from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, replace
from typing import Any, Iterable, Mapping

from .models import Relation, clean_float, clean_text


class SocialStateError(ValueError):
    """Raised when a social-state model response is malformed."""


@dataclass(frozen=True, slots=True)
class RelationshipDelta:
    active_mode: str = ""
    trust_delta: float = 0.0
    familiarity_delta: float = 0.0
    affinity_delta: float = 0.0
    romantic_interest_delta: float = 0.0
    confidence: float = 0.0
    reason: str = ""
    accepted: bool = False


@dataclass(frozen=True, slots=True)
class RelationshipState:
    source_bot_id: str
    target_bot_id: str
    active_mode: str = ""
    trust_delta: float = 0.0
    familiarity_delta: float = 0.0
    affinity_delta: float = 0.0
    romantic_interest_delta: float = 0.0
    last_reason: str = ""
    version: int = 0
    updated_at: int = 0

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "RelationshipState":
        return cls(
            source_bot_id=clean_text(data.get("source_bot_id")),
            target_bot_id=clean_text(data.get("target_bot_id")),
            active_mode=_limited(data.get("active_mode"), 40),
            trust_delta=_clamp(data.get("trust_delta"), -0.5, 0.5, 0.0),
            familiarity_delta=_clamp(
                data.get("familiarity_delta"), -0.5, 0.5, 0.0
            ),
            affinity_delta=_clamp(data.get("affinity_delta"), -1.0, 1.0, 0.0),
            romantic_interest_delta=_clamp(
                data.get("romantic_interest_delta"), -0.5, 0.5, 0.0
            ),
            last_reason=_limited(data.get("last_reason"), 300),
            version=max(0, int(clean_float(data.get("version"), 0.0))),
            updated_at=max(0, int(clean_float(data.get("updated_at"), 0.0))),
        )


@dataclass(frozen=True, slots=True)
class ObserverDecision:
    should_speak: bool
    score: float = 0.0
    message: str = ""
    reason: str = ""


def parse_relationship_delta(
    payload: str,
    *,
    max_step: float = 0.05,
    confidence_threshold: float = 0.65,
) -> RelationshipDelta:
    data = _load_json_object(payload)
    confidence = _clamp(data.get("confidence"), 0.0, 1.0, 0.0)
    threshold = _clamp(confidence_threshold, 0.0, 1.0, 0.65)
    if confidence < threshold:
        return RelationshipDelta(
            confidence=confidence,
            reason=_limited(data.get("reason"), 300),
            accepted=False,
        )
    step = _clamp(max_step, 0.001, 0.25, 0.05)
    return RelationshipDelta(
        active_mode=_limited(data.get("active_mode"), 40),
        trust_delta=_clamp(data.get("trust_delta"), -step, step, 0.0),
        familiarity_delta=_clamp(
            data.get("familiarity_delta"), -step, step, 0.0
        ),
        affinity_delta=_clamp(data.get("affinity_delta"), -step, step, 0.0),
        romantic_interest_delta=_clamp(
            data.get("romantic_interest_delta"), -step, step, 0.0
        ),
        confidence=confidence,
        reason=_limited(data.get("reason"), 300),
        accepted=True,
    )


def effective_relation(
    base: Relation, state: RelationshipState | Mapping[str, Any] | None
) -> Relation:
    if state is None:
        return base
    if not isinstance(state, RelationshipState):
        state = RelationshipState.from_mapping(state)
    mode_suffix = f"；当前互动模式：{state.active_mode}" if state.active_mode else ""
    return replace(
        base,
        trust=_clamp(base.trust + state.trust_delta, 0.0, 1.0, base.trust),
        familiarity=_clamp(
            base.familiarity + state.familiarity_delta,
            0.0,
            1.0,
            base.familiarity,
        ),
        affinity=_clamp(
            base.affinity + state.affinity_delta, -1.0, 1.0, base.affinity
        ),
        romantic_interest=_clamp(
            base.romantic_interest + state.romantic_interest_delta,
            0.0,
            1.0,
            base.romantic_interest,
        ),
        tone=f"{base.tone}{mode_suffix}".strip("； "),
    )


def parse_observer_decision(
    payload: str,
    *,
    min_score: float = 0.78,
    max_chars: int = 500,
) -> ObserverDecision:
    data = _load_json_object(payload)
    score = _clamp(data.get("score"), 0.0, 1.0, 0.0)
    action = clean_text(data.get("action")).casefold()
    message = _limited(data.get("message"), max(20, min(int(max_chars), 4000)))
    message = message.replace("[BOTMESH/1:", "[已移除协议样式:").strip()
    reason = _limited(data.get("reason"), 300)
    should_speak = (
        action in {"speak", "interject", "插话", "发言"}
        and score >= _clamp(min_score, 0.0, 1.0, 0.78)
        and bool(message)
    )
    return ObserverDecision(should_speak, score, message if should_speak else "", reason)


def select_observer(
    relations: Iterable[Relation],
    *,
    target_bot_id: str,
    event_key: str,
) -> str | None:
    """Choose exactly one eligible observer via deterministic weighted rendezvous."""
    candidates: dict[str, float] = {}
    for relation in relations:
        if relation.target_bot_id != target_bot_id or not relation.allow_interject:
            continue
        candidates[relation.source_bot_id] = max(0.01, relation.interject_priority)
    winner: str | None = None
    best_rank = math.inf
    for source_bot_id, weight in candidates.items():
        digest = hashlib.sha256(
            f"{event_key}|{source_bot_id}|{target_bot_id}".encode("utf-8")
        ).digest()
        integer = int.from_bytes(digest, "big")
        uniform = (integer + 1) / ((1 << 256) + 1)
        rank = -math.log(uniform) / weight
        if rank < best_rank:
            best_rank = rank
            winner = source_bot_id
    return winner


def context_digest(context: str) -> str:
    return hashlib.sha256(str(context or "").encode("utf-8")).hexdigest()[:24]


def _load_json_object(payload: str) -> dict[str, Any]:
    text = str(payload or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        if start < 0:
            raise SocialStateError("模型结果中没有 JSON 对象")
        try:
            data, _ = json.JSONDecoder().raw_decode(text[start:])
        except json.JSONDecodeError as exc:
            raise SocialStateError(f"模型返回的 JSON 无效: {exc}") from exc
    if not isinstance(data, dict):
        raise SocialStateError("模型结果必须是 JSON 对象")
    return data


def _limited(value: Any, limit: int) -> str:
    return clean_text(value)[: max(0, int(limit))]


def _clamp(value: Any, minimum: float, maximum: float, default: float) -> float:
    return max(minimum, min(maximum, clean_float(value, default)))
