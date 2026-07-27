from __future__ import annotations

from dataclasses import dataclass

from .graph import BotGraph
from .models import InteractionEnvelope
from .protocol import ProtocolCodec, ProtocolError


@dataclass(frozen=True, slots=True)
class DeliveryPlan:
    mention_account_id: str
    envelope: InteractionEnvelope
    body: str


def build_request_delivery(
    graph: BotGraph,
    codec: ProtocolCodec,
    envelope: InteractionEnvelope,
    content: str,
) -> DeliveryPlan:
    if not envelope.is_request:
        raise ProtocolError("请求投递只能使用 REQ 信封")
    target = graph.get_bot(envelope.target_bot_id)
    if target is None:
        raise ProtocolError(f"找不到目标 Bot: {envelope.target_bot_id}")
    bound = codec.bind_content(envelope, content)
    return DeliveryPlan(
        mention_account_id=target.account_id,
        envelope=bound,
        body=codec.attach(content, bound),
    )


def build_reply_delivery(
    graph: BotGraph,
    codec: ProtocolCodec,
    request: InteractionEnvelope,
    content: str,
    *,
    now: int | None = None,
) -> DeliveryPlan:
    """Build B -> @A delivery by reversing the request's source and target."""
    if not request.is_request:
        raise ProtocolError("回复投递必须引用 REQ 信封")
    requester = graph.get_bot(request.source_bot_id)
    if requester is None:
        raise ProtocolError(f"找不到请求方 Bot: {request.source_bot_id}")
    reply = codec.reply_to(request, now=now)
    bound = codec.bind_content(reply, content)
    return DeliveryPlan(
        mention_account_id=requester.account_id,
        envelope=bound,
        body=codec.attach(content, bound),
    )


def build_observation_delivery(
    graph: BotGraph,
    codec: ProtocolCodec,
    envelope: InteractionEnvelope,
    content: str,
) -> DeliveryPlan:
    """Build a signed B -> @A spectator interjection delivery."""
    if not envelope.is_observation:
        raise ProtocolError("旁听插话投递只能使用 OBS 信封")
    target = graph.get_bot(envelope.target_bot_id)
    if target is None:
        raise ProtocolError(f"找不到被旁听的目标 Bot: {envelope.target_bot_id}")
    bound = codec.bind_content(envelope, content)
    return DeliveryPlan(
        mention_account_id=target.account_id,
        envelope=bound,
        body=codec.attach(content, bound),
    )
