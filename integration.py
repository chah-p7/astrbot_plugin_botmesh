from __future__ import annotations

from typing import Any


_provider: Any | None = None


def register_provider(provider: Any) -> None:
    global _provider
    _provider = provider


def unregister_provider(provider: Any) -> None:
    global _provider
    if _provider is provider:
        _provider = None


def get_chat_history_scope(
    *,
    umo: str,
    event: Any | None = None,
) -> dict[str, Any]:
    """Expose BotMesh logical-group selectors to chat_history_context."""
    provider = _provider
    if provider is None:
        return {}
    method = getattr(provider, "chat_history_scope", None)
    if not callable(method):
        return {}
    result = method(umo=umo, event=event)
    return dict(result) if isinstance(result, dict) else {}


def normalize_chat_history_message(
    *,
    umo: str,
    content: str,
    event: Any | None = None,
) -> str:
    """Return the verified visible body of a BotMesh-framed group message."""
    provider = _provider
    if provider is None:
        return str(content or "")
    method = getattr(provider, "normalize_chat_history_message", None)
    if not callable(method):
        return str(content or "")
    return str(method(umo=umo, content=content, event=event) or content or "")


async def get_proactive_topics_context(
    *,
    umo: str,
    event: Any | None = None,
    identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    provider = _provider
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


def wrap_proactive_topics_message(
    *,
    umo: str,
    content: str,
    event: Any | None = None,
    identity: dict[str, Any] | None = None,
) -> str:
    provider = _provider
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
