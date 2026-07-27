from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from astrbot.api.event import AstrMessageEvent


@dataclass(slots=True)
class AgentSession:
    platform_name: str
    message_type: Any
    session_id: str
    platform_id: str = field(init=False)

    def __post_init__(self) -> None:
        self.platform_id = self.platform_name

    def __str__(self) -> str:
        value = getattr(self.message_type, "value", self.message_type)
        return f"{self.platform_id}:{value}:{self.session_id}"


class AgentEventProxy(AstrMessageEvent):
    def __init__(
        self,
        base_event: Any,
        *,
        context: Any,
        session: AgentSession,
        platform_name: str,
        self_account_id: str,
        sender_account_id: str,
        group_id: str,
        message: str,
        extras: dict[str, Any] | None = None,
    ) -> None:
        self._base_event = base_event
        self._context = context
        self.session = session
        self.platform_meta = type(
            "BotMeshAgentPlatformMeta",
            (),
            {"id": session.platform_id, "name": platform_name},
        )()
        self.message_str = str(message or "")
        self._self_account_id = str(self_account_id or "")
        self._sender_account_id = str(sender_account_id or "")
        self._group_id = str(group_id or "")
        self._extras = dict(extras or {})
        self.is_at_or_wake_command = True
        self.is_wake = True

    @property
    def unified_msg_origin(self) -> str:
        return str(self.session)

    def get_self_id(self) -> str:
        return self._self_account_id

    def get_sender_id(self) -> str:
        return self._sender_account_id

    def get_group_id(self) -> str:
        return self._group_id

    def get_platform_id(self) -> str:
        return self.session.platform_id

    def get_platform_name(self) -> str:
        return str(self.platform_meta.name or "")

    def get_extra(self, key: str | None = None, default: Any = None) -> Any:
        if key is None:
            return self._extras
        return self._extras.get(key, default)

    def set_extra(self, key: str, value: Any) -> None:
        self._extras[key] = value

    def chain_result(self, chain: list[Any]) -> Any:
        return self._base_event.chain_result(chain)

    def plain_result(self, content: str) -> Any:
        return self._base_event.plain_result(content)

    async def send(self, message: Any) -> None:
        sent = await self._context.send_message(self.session, message)
        if sent is False:
            raise RuntimeError(
                f"找不到目标平台 {self.session.platform_id}，消息未发送"
            )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base_event, name)
