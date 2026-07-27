from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .models import BotNode, clean_text


MAX_PERSONA_PROFILES = 500
MAX_PERSONA_PROMPT_CHARS = 50000


class PersonaProfileError(ValueError):
    """Raised when a BotMesh-managed persona profile is invalid."""


def normalize_persona_profiles(
    raw_profiles: Any,
    bots: Iterable[BotNode],
) -> list[dict[str, str]]:
    if not isinstance(raw_profiles, list):
        raise PersonaProfileError("persona_profiles 必须是数组")
    if len(raw_profiles) > MAX_PERSONA_PROFILES:
        raise PersonaProfileError(
            f"人格配置不能超过 {MAX_PERSONA_PROFILES} 条"
        )

    bot_ids = {bot.bot_id for bot in bots}
    seen: set[tuple[str, str]] = set()
    normalized: list[dict[str, str]] = []
    for index, item in enumerate(raw_profiles, start=1):
        if not isinstance(item, dict):
            raise PersonaProfileError(f"第 {index} 条人格配置必须是对象")
        bot_id = clean_text(item.get("bot_id"))
        group_id = clean_text(item.get("group_id"))
        system_prompt = str(
            item.get("system_prompt") or item.get("prompt") or ""
        ).strip()
        if bot_id not in bot_ids:
            raise PersonaProfileError(
                f"第 {index} 条人格配置引用了不存在的 Bot: {bot_id or '<empty>'}"
            )
        if len(group_id) > 128:
            raise PersonaProfileError(f"第 {index} 条人格配置的群 ID 过长")
        if not system_prompt:
            raise PersonaProfileError(f"第 {index} 条人格配置内容不能为空")
        if len(system_prompt) > MAX_PERSONA_PROMPT_CHARS:
            raise PersonaProfileError(
                f"第 {index} 条人格配置不能超过 {MAX_PERSONA_PROMPT_CHARS} 个字符"
            )
        key = (bot_id, group_id)
        if key in seen:
            scope = f"群 {group_id}" if group_id else "全局"
            raise PersonaProfileError(f"人格配置重复: {bot_id}（{scope}）")
        seen.add(key)
        normalized.append(
            {
                "__template_key": "persona_profile",
                "bot_id": bot_id,
                "group_id": group_id,
                "system_prompt": system_prompt,
            }
        )
    return normalized


def resolve_persona_prompt(
    profiles: Iterable[dict[str, Any]],
    bot_id: str,
    group_id: str = "",
) -> str:
    exact = ""
    fallback = ""
    target_bot_id = clean_text(bot_id)
    target_group_id = clean_text(group_id)
    for item in profiles:
        if clean_text(item.get("bot_id")) != target_bot_id:
            continue
        item_group_id = clean_text(item.get("group_id"))
        prompt = str(item.get("system_prompt") or "").strip()
        if not item_group_id:
            fallback = prompt
        if target_group_id and item_group_id == target_group_id:
            exact = prompt
    return exact or fallback


def persona_profiles_for_group(
    profiles: Iterable[dict[str, Any]],
    bots: Iterable[BotNode],
    group_id: str = "",
) -> list[dict[str, str]]:
    scope = clean_text(group_id)
    rows: list[dict[str, str]] = []
    for bot in bots:
        prompt = resolve_persona_prompt(profiles, bot.bot_id, scope)
        if not prompt:
            continue
        rows.append(
            {
                "id": bot.bot_id,
                "name": bot.display_name,
                "system_prompt": prompt,
            }
        )
    return rows
