from __future__ import annotations

import sys
from typing import Any

from astrbot.api import logger


_provider: Any | None = None


def _matching_modules() -> list[Any]:
    current = sys.modules.get(__name__)
    return [
        module
        for name, module in list(sys.modules.items())
        if module is not None
        and (
            name == "astrbot_plugin_botmesh.integration"
            or name.endswith(".astrbot_plugin_botmesh.integration")
        )
        and module is not current
    ]


def _active_provider() -> Any | None:
    if _provider is not None:
        return _provider
    for module in _matching_modules():
        provider = getattr(module, "_provider", None)
        if provider is not None:
            return provider
    return None


def register_provider(provider: Any) -> None:
    global _provider
    _provider = provider
    for module in _matching_modules():
        setattr(module, "_provider", provider)


def unregister_provider(provider: Any) -> None:
    global _provider
    if _provider is provider:
        _provider = None
    for module in _matching_modules():
        if getattr(module, "_provider", None) is provider:
            setattr(module, "_provider", None)


def get_chat_history_scope(
    *,
    umo: str,
    event: Any | None = None,
) -> dict[str, Any]:
    """Expose BotMesh logical-group selectors to chat_history_context."""
    provider = _active_provider()
    if provider is None:
        return {}
    method = getattr(provider, "chat_history_scope", None)
    if not callable(method):
        return {}
    result = method(umo=umo, event=event)
    return dict(result) if isinstance(result, dict) else {}


def get_identity_state(
    *,
    bot_id: str,
    logical_group_id: str = "",
) -> dict[str, Any]:
    """Read the live structured identity from BotMesh Persona configuration."""
    provider = _active_provider()
    if provider is None:
        return {}
    method = getattr(provider, "persona_identity_state", None)
    if not callable(method):
        return {}
    result = method(bot_id=bot_id, group_id=logical_group_id)
    return dict(result) if isinstance(result, dict) else {}


def get_management_labels() -> dict[str, dict[str, str]]:
    """Expose human-readable Bot and logical-group labels to companion pages."""
    provider = _active_provider()
    if provider is None:
        return {
            "bots": {}, "groups": {}, "scopes": {}, "scope_groups": {},
            "bot_ids": {}, "memory_keys": {},
        }
    method = getattr(provider, "management_labels", None)
    if not callable(method):
        return {
            "bots": {}, "groups": {}, "scopes": {}, "scope_groups": {},
            "bot_ids": {}, "memory_keys": {},
        }
    result = method()
    if not isinstance(result, dict):
        return {
            "bots": {}, "groups": {}, "scopes": {}, "scope_groups": {},
            "bot_ids": {}, "memory_keys": {},
        }
    return {
        key: {
            str(item_key): str(item_value)
            for item_key, item_value in value.items()
            if str(item_key).strip() and str(item_value).strip()
        }
        for key in (
            "bots", "groups", "scopes", "scope_groups", "bot_ids", "memory_keys"
        )
        if isinstance((value := result.get(key)), dict)
    }


async def set_memory_key(
    *,
    bot_id: str,
    logical_group_id: str,
    memory_key: str,
) -> dict[str, Any]:
    """Update the canonical BotMesh Persona memory binding."""
    provider = _active_provider()
    if provider is None:
        raise RuntimeError("BotMesh provider 尚未就绪")
    method = getattr(provider, "set_persona_memory_key", None)
    if not callable(method):
        raise RuntimeError("当前 BotMesh 版本不支持修改 memory_key")
    result = await method(
        bot_id=bot_id,
        group_id=logical_group_id,
        memory_key=memory_key,
    )
    return dict(result) if isinstance(result, dict) else {}


def normalize_chat_history_message(
    *,
    umo: str,
    content: str,
    event: Any | None = None,
) -> str:
    """Return the verified visible body of a BotMesh-framed group message."""
    record = normalize_chat_history_record(umo=umo, content=content, event=event)
    return str(record.get("content", "") or content or "")


def normalize_chat_history_record(
    *,
    umo: str,
    content: str,
    event: Any | None = None,
) -> dict[str, str]:
    """Return visible content plus the verified sender identity when available."""
    fallback = {"content": str(content or "")}
    provider = _active_provider()
    if provider is None:
        return fallback
    method = getattr(provider, "normalize_chat_history_record", None)
    if callable(method):
        result = method(umo=umo, content=content, event=event)
        return dict(result) if isinstance(result, dict) else fallback
    method = getattr(provider, "normalize_chat_history_message", None)
    if not callable(method):
        return fallback
    fallback["content"] = str(
        method(umo=umo, content=content, event=event) or content or ""
    )
    return fallback


async def get_proactive_topics_context(
    *,
    umo: str,
    event: Any | None = None,
    identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provider = _active_provider()
    if provider is None:
        return {
            "available": False,
            "enabled": False,
            "error": "provider_unavailable",
        }
    method = getattr(provider, "proactive_topics_context", None)
    if not callable(method):
        return {"available": False, "enabled": False, "error": "api_unavailable"}
    result = await method(umo=umo, event=event, identity=identity)
    return dict(result) if isinstance(result, dict) else {}


async def get_dynamic_life_state_context(
    *,
    umo: str,
    event: Any | None = None,
    identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Expose identity-scoped personas for coordinated life-state generation."""
    provider = _active_provider()
    if provider is None:
        return {
            "available": False,
            "enabled": False,
            "error": "provider_unavailable",
        }
    method = getattr(provider, "dynamic_life_state_context", None)
    if not callable(method):
        return {"available": False, "enabled": False, "error": "api_unavailable"}
    result = await method(umo=umo, event=event, identity=identity)
    return dict(result) if isinstance(result, dict) else {}


async def dispatch_proactive_topic(
    *,
    umo: str,
    event: Any | None = None,
    identity: dict[str, Any] | None = None,
    trigger: dict[str, Any] | None = None,
    local_history: list[dict[str, Any]] | None = None,
    recent_topics: list[str] | None = None,
    generation_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Let BotMesh generate, sign and send one proactive group message."""
    trigger_payload = trigger if isinstance(trigger, dict) else {}
    trace_id = str(trigger_payload.get("trace_id", "") or "no-trace")
    provider = _active_provider()
    if provider is None:
        logger.warning(
            "[BotMesh][%s] 调用链 3/4：integration provider 未注册",
            trace_id,
        )
        return {
            "success": False,
            "proactive_dispatch_version": 1,
            "error": "provider_unavailable",
        }
    method = getattr(provider, "dispatch_proactive_topic", None)
    if not callable(method):
        logger.warning(
            "[BotMesh][%s] 调用链 3/4：provider=%s 缺少派发方法",
            trace_id,
            type(provider).__name__,
        )
        return {
            "success": False,
            "proactive_dispatch_version": 1,
            "error": "dispatch_api_unavailable",
        }
    logger.info(
        "[BotMesh][%s] 调用链 3/4：integration -> %s.dispatch_proactive_topic",
        trace_id,
        type(provider).__name__,
    )
    result = await method(
        umo=umo,
        event=event,
        identity=identity,
        trigger=trigger,
        local_history=local_history,
        recent_topics=recent_topics,
        generation_options=generation_options,
    )
    return dict(result) if isinstance(result, dict) else {
        "success": False,
        "proactive_dispatch_version": 1,
        "error": "invalid_dispatch_result",
    }


def wrap_proactive_topics_message(
    *,
    umo: str,
    content: str,
    event: Any | None = None,
    identity: dict[str, Any] | None = None,
) -> str:
    provider = _active_provider()
    if provider is None:
        return str(content or "")
    method = getattr(provider, "wrap_proactive_topics_message", None)
    if not callable(method):
        return str(content or "")
    return str(
        method(umo=umo, content=content, event=event, identity=identity)
        or content
        or ""
    )


# Keep one provider registry even when AstrBot loads the plugin below a dynamic
# package namespace and another plugin imports the canonical package name.
sys.modules.setdefault("astrbot_plugin_botmesh.integration", sys.modules[__name__])
