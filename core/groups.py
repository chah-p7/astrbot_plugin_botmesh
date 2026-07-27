from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from .models import BotNode, clean_text


class GroupBindingError(ValueError):
    """Raised when logical-group bindings are ambiguous or invalid."""


class GroupScopeError(ValueError):
    """Raised when the first-class logical-group list is invalid."""


def normalize_group_scopes(
    entries: Any,
    *,
    implied_group_ids: Iterable[str] = (),
) -> list[dict[str, str]]:
    if entries is None:
        entries = []
    if not isinstance(entries, list):
        raise GroupScopeError("group_scopes 必须是列表")
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, item in enumerate(entries, start=1):
        if not isinstance(item, Mapping):
            raise GroupScopeError(f"第 {index} 个逻辑群必须是对象")
        group_id = clean_text(item.get("group_id"))
        if not group_id or len(group_id) > 128:
            raise GroupScopeError(f"第 {index} 个逻辑群 ID 无效")
        if group_id in seen:
            raise GroupScopeError(f"逻辑群 ID 重复：{group_id}")
        seen.add(group_id)
        result.append(
            {"__template_key": "group_scope", "group_id": group_id}
        )
    for raw_group_id in implied_group_ids:
        group_id = clean_text(raw_group_id)
        if not group_id or group_id in seen:
            continue
        if len(group_id) > 128:
            raise GroupScopeError(f"逻辑群 ID 无效：{group_id[:32]}")
        seen.add(group_id)
        result.append(
            {"__template_key": "group_scope", "group_id": group_id}
        )
    return result


@dataclass(frozen=True, slots=True)
class GroupBinding:
    group_id: str
    bot_id: str
    platform_group_id: str

    def to_config(self) -> dict[str, str]:
        return {
            "__template_key": "group_binding",
            "group_id": self.group_id,
            "bot_id": self.bot_id,
            "platform_group_id": self.platform_group_id,
        }


def normalize_group_bindings(
    entries: Any,
    bots: Iterable[BotNode],
) -> list[dict[str, str]]:
    if entries is None:
        entries = []
    if not isinstance(entries, list):
        raise GroupBindingError("group_bindings 必须是列表")
    bot_ids = {bot.bot_id for bot in bots}
    logical_keys: set[tuple[str, str]] = set()
    raw_keys: set[tuple[str, str]] = set()
    result: list[dict[str, str]] = []
    for index, item in enumerate(entries, start=1):
        if not isinstance(item, Mapping):
            raise GroupBindingError(f"第 {index} 条群聊映射必须是对象")
        group_id = clean_text(item.get("group_id"))
        bot_id = clean_text(item.get("bot_id"))
        platform_group_id = clean_text(item.get("platform_group_id"))
        if not group_id or len(group_id) > 128:
            raise GroupBindingError(f"第 {index} 条群聊映射的逻辑群 ID 无效")
        if bot_id not in bot_ids:
            raise GroupBindingError(f"第 {index} 条群聊映射引用了不存在的 Bot")
        if not platform_group_id or len(platform_group_id) > 128:
            raise GroupBindingError(f"第 {index} 条群聊映射的平台群 ID 无效")
        logical_key = (group_id, bot_id)
        raw_key = (bot_id, platform_group_id)
        if logical_key in logical_keys:
            raise GroupBindingError(f"群 {group_id} 中的 {bot_id} 出现了重复映射")
        if raw_key in raw_keys:
            raise GroupBindingError(
                f"{bot_id} 的平台群 ID {platform_group_id} 被映射了多次"
            )
        logical_keys.add(logical_key)
        raw_keys.add(raw_key)
        result.append(
            GroupBinding(group_id, bot_id, platform_group_id).to_config()
        )
    return result


class GroupResolver:
    def __init__(self, entries: Iterable[Mapping[str, Any]] = ()) -> None:
        self._by_raw: dict[tuple[str, str], str] = {}
        self._by_logical: dict[tuple[str, str], str] = {}
        for item in entries:
            group_id = clean_text(item.get("group_id"))
            bot_id = clean_text(item.get("bot_id"))
            platform_group_id = clean_text(item.get("platform_group_id"))
            if group_id and bot_id and platform_group_id:
                self._by_raw[(bot_id, platform_group_id)] = group_id
                self._by_logical[(group_id, bot_id)] = platform_group_id

    def resolve(self, bot_id: str, platform_group_id: str) -> str:
        raw = clean_text(platform_group_id)[:128]
        if not raw:
            return ""
        return self._by_raw.get((clean_text(bot_id), raw), raw)

    def platform_group_id(self, group_id: str, bot_id: str) -> str:
        return self._by_logical.get(
            (clean_text(group_id), clean_text(bot_id)),
            "",
        )
