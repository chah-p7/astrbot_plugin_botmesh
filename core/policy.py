from __future__ import annotations

import time
from dataclasses import dataclass

from .graph import BotGraph
from .models import InteractionEnvelope


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    allowed: bool
    reason: str = ""

    @classmethod
    def allow(cls) -> "PolicyDecision":
        return cls(True, "")

    @classmethod
    def deny(cls, reason: str) -> "PolicyDecision":
        return cls(False, reason)


class InteractionGuard:
    def __init__(
        self,
        graph: BotGraph,
        *,
        max_depth: int = 2,
        ttl_seconds: int = 120,
        cooldown_seconds: int = 10,
    ) -> None:
        self.graph = graph
        self.max_depth = max(0, int(max_depth))
        self.ttl_seconds = max(10, int(ttl_seconds))
        self.cooldown_seconds = max(0, int(cooldown_seconds))
        self._last_outgoing: dict[tuple[str, str], float] = {}

    def check_outgoing(
        self,
        source_bot_id: str,
        target_bot_id: str,
        *,
        group_id: str = "",
        depth: int = 0,
        now: float | None = None,
    ) -> PolicyDecision:
        if source_bot_id == target_bot_id:
            return PolicyDecision.deny("不能询问自己")
        if self.graph.get_bot(source_bot_id) is None:
            return PolicyDecision.deny("本机 Bot 不在关系网中")
        if self.graph.get_bot(target_bot_id) is None:
            return PolicyDecision.deny("目标 Bot 不存在")
        if not self.graph.can_ask(source_bot_id, target_bot_id, group_id):
            return PolicyDecision.deny("当前关系不允许发起询问")
        if int(depth) > self.max_depth:
            return PolicyDecision.deny("互动深度超过限制")
        current = float(now if now is not None else time.time())
        key = (source_bot_id, target_bot_id)
        last = self._last_outgoing.get(key)
        if last is not None and current - last < self.cooldown_seconds:
            remaining = max(1, int(self.cooldown_seconds - (current - last)))
            return PolicyDecision.deny(f"请求过于频繁，请约 {remaining} 秒后再试")
        return PolicyDecision.allow()

    def mark_outgoing(
        self,
        source_bot_id: str,
        target_bot_id: str,
        *,
        now: float | None = None,
    ) -> None:
        self._last_outgoing[(source_bot_id, target_bot_id)] = float(
            now if now is not None else time.time()
        )

    def check_incoming(
        self,
        envelope: InteractionEnvelope,
        *,
        self_bot_id: str,
        sender_account_id: str,
        group_id: str = "",
        now: int | None = None,
    ) -> PolicyDecision:
        current = int(now if now is not None else time.time())
        if envelope.target_bot_id != self_bot_id:
            return PolicyDecision.deny("消息目标不是本 Bot")
        allowed_depth = self.max_depth + (
            1 if envelope.is_reply or envelope.is_display else 0
        )
        if envelope.depth > allowed_depth:
            return PolicyDecision.deny("互动深度超过限制")
        age = current - envelope.created_at
        if age < -30 or age > self.ttl_seconds:
            return PolicyDecision.deny("互动消息已经过期或时间戳异常")
        source = self.graph.get_bot(envelope.source_bot_id)
        if source is None:
            return PolicyDecision.deny("来源 Bot 不在关系网中")
        if source.account_id != str(sender_account_id):
            return PolicyDecision.deny("消息发送账号与来源 Bot 不匹配")
        if envelope.is_request and not self.graph.can_ask(
            envelope.source_bot_id,
            envelope.target_bot_id,
            group_id,
        ):
            return PolicyDecision.deny("当前关系不允许该 Bot 发起询问")
        if envelope.is_observation:
            relation = self.graph.get_relation(
                envelope.source_bot_id,
                envelope.target_bot_id,
                group_id,
            )
            if relation is None or not relation.allow_interject:
                return PolicyDecision.deny("当前关系不允许该 Bot 旁听插话")
        return PolicyDecision.allow()
