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


async def get_proactive_topics_context(
    *,
    umo: str,
    event: Any | None = None,
) -> dict[str, Any]:
    provider = _provider
    if provider is None:
        return {}
    method = getattr(provider, "proactive_topics_context", None)
    if not callable(method):
        return {}
    result = await method(umo=umo, event=event)
    return dict(result) if isinstance(result, dict) else {}


def wrap_proactive_topics_message(
    *,
    umo: str,
    content: str,
    event: Any | None = None,
) -> str:
    provider = _provider
    if provider is None:
        return str(content or "")
    method = getattr(provider, "wrap_proactive_topics_message", None)
    if not callable(method):
        return str(content or "")
    return str(method(umo=umo, content=content, event=event) or content or "")
