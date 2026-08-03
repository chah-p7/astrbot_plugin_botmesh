from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .models import BotNode, clean_text


MAX_PERSONA_PROFILES = 500
MAX_PERSONA_PROMPT_CHARS = 50000
MAX_IDENTITY_FIELD_CHARS = 160
MAX_IDENTITY_NOTE_CHARS = 1000
MAX_MEMORY_KEY_CHARS = 160


class PersonaProfileError(ValueError):
    """Raised when a BotMesh-managed persona profile is invalid."""


def normalize_persona_profiles(
    raw_profiles: Any,
    bots: Iterable[BotNode],
) -> list[dict[str, Any]]:
    if not isinstance(raw_profiles, list):
        raise PersonaProfileError("persona_profiles 必须是数组")
    if len(raw_profiles) > MAX_PERSONA_PROFILES:
        raise PersonaProfileError(
            f"人格配置不能超过 {MAX_PERSONA_PROFILES} 条"
        )

    bot_ids = {bot.bot_id for bot in bots}
    seen: set[tuple[str, str]] = set()
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw_profiles, start=1):
        if not isinstance(item, dict):
            raise PersonaProfileError(f"第 {index} 条人格配置必须是对象")
        bot_id = clean_text(item.get("bot_id"))
        group_id = clean_text(item.get("group_id"))
        has_split_fields = (
            "personality_prompt" in item or "worldview_prompt" in item
        )
        if has_split_fields:
            personality_prompt = str(item.get("personality_prompt") or "").strip()
            worldview_prompt = str(item.get("worldview_prompt") or "").strip()
            if not personality_prompt and not worldview_prompt:
                personality_prompt = str(
                    item.get("system_prompt") or item.get("prompt") or ""
                ).strip()
        else:
            # 0.8.x stored identity, personality, worldview and style in one field.
            # Preserve that text verbatim as the personality/identity section.
            personality_prompt = str(
                item.get("system_prompt") or item.get("prompt") or ""
            ).strip()
            worldview_prompt = ""
        self_identity = clean_text(item.get("self_identity"))
        soul_identity = clean_text(item.get("soul_identity"))
        body_identity = clean_text(item.get("body_identity"))
        memory_key = clean_text(item.get("memory_key"))
        identity_note = str(item.get("identity_note") or "").strip()
        has_identity = bool(
            self_identity
            or soul_identity
            or body_identity
            or memory_key
            or identity_note
        )
        if bot_id not in bot_ids:
            raise PersonaProfileError(
                f"第 {index} 条人格配置引用了不存在的 Bot: {bot_id or '<empty>'}"
            )
        if len(group_id) > 128:
            raise PersonaProfileError(f"第 {index} 条人格配置的群 ID 过长")
        if not personality_prompt and not worldview_prompt and not has_identity:
            raise PersonaProfileError(
                f"第 {index} 条人格配置的人格、世界观和身份不能同时为空"
            )
        if len(personality_prompt) > MAX_PERSONA_PROMPT_CHARS:
            raise PersonaProfileError(
                f"第 {index} 条人格提示词不能超过 {MAX_PERSONA_PROMPT_CHARS} 个字符"
            )
        if len(worldview_prompt) > MAX_PERSONA_PROMPT_CHARS:
            raise PersonaProfileError(
                f"第 {index} 条世界观提示词不能超过 {MAX_PERSONA_PROMPT_CHARS} 个字符"
            )
        for label, value in (
            ("当前自我", self_identity),
            ("灵魂/操控者", soul_identity),
            ("身体身份", body_identity),
            ("记忆身份键", memory_key),
        ):
            if len(value) > MAX_IDENTITY_FIELD_CHARS:
                raise PersonaProfileError(
                    f"第 {index} 条人格配置的{label}不能超过 "
                    f"{MAX_IDENTITY_FIELD_CHARS} 个字符"
                )
        if len(identity_note) > MAX_IDENTITY_NOTE_CHARS:
            raise PersonaProfileError(
                f"第 {index} 条人格配置的身份说明不能超过 "
                f"{MAX_IDENTITY_NOTE_CHARS} 个字符"
            )
        key = (bot_id, group_id)
        if key in seen:
            scope = f"群 {group_id}" if group_id else "全局"
            raise PersonaProfileError(f"人格配置重复: {bot_id}（{scope}）")
        seen.add(key)
        row: dict[str, Any] = {
                "__template_key": "persona_profile",
                "bot_id": bot_id,
                "group_id": group_id,
                "personality_prompt": personality_prompt,
                "worldview_prompt": worldview_prompt,
                "self_identity": self_identity,
                "soul_identity": soul_identity,
                "body_identity": body_identity,
                "memory_key": memory_key,
                "identity_note": identity_note,
                # Keep the old API/config view readable for integrations that have
                # not learned the split fields yet. Split fields remain canonical.
                "system_prompt": compose_persona_prompt(
                    personality_prompt,
                    worldview_prompt,
                ),
            }
        if "identity_locked" in item:
            row["identity_locked"] = bool(item.get("identity_locked"))
        normalized.append(row)
    return normalized


def compose_persona_prompt(
    personality_prompt: Any,
    worldview_prompt: Any,
) -> str:
    """Compose separate editor fields into the effective runtime persona."""
    personality = str(personality_prompt or "").strip()
    worldview = str(worldview_prompt or "").strip()
    if personality and worldview:
        return (
            "【人格、身份与表达方式】\n"
            f"{personality}\n\n"
            "【世界观、经历与认知框架】\n"
            f"{worldview}"
        )
    return personality or worldview


def resolve_persona_sections(
    profiles: Iterable[dict[str, Any]],
    bot_id: str,
    group_id: str = "",
) -> tuple[str, str]:
    """Resolve personality and worldview independently with group fallback."""
    target_bot_id = clean_text(bot_id)
    target_group_id = clean_text(group_id)
    global_profile: dict[str, Any] | None = None
    exact_profile: dict[str, Any] | None = None
    for item in profiles:
        if clean_text(item.get("bot_id")) != target_bot_id:
            continue
        item_group_id = clean_text(item.get("group_id"))
        if not item_group_id:
            global_profile = item
        elif target_group_id and item_group_id == target_group_id:
            exact_profile = item

    def section(item: dict[str, Any] | None, field: str) -> str:
        if not item:
            return ""
        if "personality_prompt" in item or "worldview_prompt" in item:
            return str(item.get(field) or "").strip()
        if field == "personality_prompt":
            return str(item.get("system_prompt") or item.get("prompt") or "").strip()
        return ""

    global_personality = section(global_profile, "personality_prompt")
    global_worldview = section(global_profile, "worldview_prompt")
    exact_personality = section(exact_profile, "personality_prompt")
    exact_worldview = section(exact_profile, "worldview_prompt")
    return (
        exact_personality or global_personality,
        exact_worldview or global_worldview,
    )


def resolve_persona_prompt(
    profiles: Iterable[dict[str, Any]],
    bot_id: str,
    group_id: str = "",
) -> str:
    personality, worldview = resolve_persona_sections(profiles, bot_id, group_id)
    return compose_persona_prompt(personality, worldview)


def resolve_persona_identity(
    profiles: Iterable[dict[str, Any]],
    bot_id: str,
    group_id: str = "",
) -> dict[str, Any]:
    """Resolve structured identity from the same BotMesh Persona source."""
    target_bot_id = clean_text(bot_id)
    target_group_id = clean_text(group_id)
    global_profile: dict[str, Any] | None = None
    exact_profile: dict[str, Any] | None = None
    for item in profiles:
        if clean_text(item.get("bot_id")) != target_bot_id:
            continue
        item_group_id = clean_text(item.get("group_id"))
        if not item_group_id:
            global_profile = item
        elif target_group_id and item_group_id == target_group_id:
            exact_profile = item

    def text_field(field: str) -> str:
        exact = clean_text((exact_profile or {}).get(field))
        if exact:
            return exact
        return clean_text((global_profile or {}).get(field))

    identity = {
        "self_identity": text_field("self_identity"),
        "soul_identity": text_field("soul_identity"),
        "body_identity": text_field("body_identity"),
        "memory_key": text_field("memory_key"),
        "identity_note": text_field("identity_note"),
    }
    if not any(identity.values()):
        return {}
    if exact_profile is not None and "identity_locked" in exact_profile:
        locked = bool(exact_profile.get("identity_locked"))
    elif global_profile is not None and "identity_locked" in global_profile:
        locked = bool(global_profile.get("identity_locked"))
    else:
        locked = True
    identity["locked"] = locked
    identity["source_scope"] = target_group_id if exact_profile else ""
    return identity


def build_identity_system_block(
    identity: dict[str, Any],
    *,
    scope_id: str,
    account_label: str,
) -> str:
    if not identity:
        return ""
    locked = bool(identity.get("locked", True))
    return (
        '<botmesh_memory_identity priority="highest">\n'
        f"身份配置来源：BotMesh Persona（{scope_id or '全局'}）。\n"
        f"平台账号标签：{account_label or '未填写'}。\n"
        f"当前自我身份：{identity.get('self_identity') or '未填写'}。\n"
        f"当前灵魂/操控者：{identity.get('soul_identity') or identity.get('self_identity') or '未填写'}。\n"
        f"当前身体身份：{identity.get('body_identity') or '未填写'}。\n"
        f"稳定记忆身份键：{identity.get('memory_key') or identity.get('soul_identity') or identity.get('self_identity') or '未填写'}。"
        "该键只决定主观记忆跟随哪个角色，不是账号名，也不得在公开回复中机械复述。\n"
        f"补充说明：{identity.get('identity_note') or '无'}。\n"
        f"防历史覆盖：{'开启' if locked else '关闭'}。"
        "开启时，聊天历史、引用、昵称、账号原名、旧回复和模型推测都不得覆盖上述身份；"
        "配置管理员对 BotMesh Persona 的修改始终可以覆盖并立即成为新身份。\n"
        "</botmesh_memory_identity>"
    )


def persona_profiles_for_group(
    profiles: Iterable[dict[str, Any]],
    bots: Iterable[BotNode],
    group_id: str = "",
) -> list[dict[str, str]]:
    scope = clean_text(group_id)
    rows: list[dict[str, str]] = []
    for bot in bots:
        personality, worldview = resolve_persona_sections(
            profiles,
            bot.bot_id,
            scope,
        )
        prompt = compose_persona_prompt(personality, worldview)
        if not prompt:
            continue
        rows.append(
            {
                "id": bot.bot_id,
                "name": bot.display_name,
                "personality_prompt": personality,
                "worldview_prompt": worldview,
                "system_prompt": prompt,
            }
        )
    return rows
