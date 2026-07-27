from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .graph import BotGraph, GraphConfigError
from .models import BotNode, Relation


MAX_RELATIONS = 500
MAX_NODES = 200
_TEXT_LIMITS = {
    "group_id": 128,
    "relation_type": 80,
    "tone": 500,
    "address_as": 80,
}


class RelationshipEditorError(ValueError):
    """Raised when relationship-editor input is invalid."""


def relation_to_config(relation: Relation) -> dict[str, Any]:
    """Serialize only the administrator-editable relation fields."""
    return {
        "__template_key": "relation",
        "source_bot_id": relation.source_bot_id,
        "target_bot_id": relation.target_bot_id,
        "group_id": relation.group_id,
        "relation_type": relation.relation_type,
        "allow_ask": relation.allow_ask,
        "trust": relation.trust,
        "tone": relation.tone,
        "share_context": relation.share_context,
        "address_as": relation.address_as,
        "familiarity": relation.familiarity,
        "affinity": relation.affinity,
        "romantic_interest": relation.romantic_interest,
        "allow_flirt": relation.allow_flirt,
        "allow_interject": relation.allow_interject,
        "allow_evolve": relation.allow_evolve,
        "interject_priority": relation.interject_priority,
    }


def node_to_config(node: BotNode) -> dict[str, Any]:
    if node.node_type == "user":
        return {
            "__template_key": "user",
            "user_id": node.bot_id,
            "display_name": node.display_name,
            "account_id": node.account_id,
            "description": node.description,
            "aliases": list(node.aliases),
        }
    return {
        "__template_key": "bot",
        "bot_id": node.bot_id,
        "display_name": node.display_name,
        "account_id": node.account_id,
        "platform_id": node.platform_id,
        "description": node.description,
        "capabilities": list(node.capabilities),
        "aliases": list(node.aliases),
    }


def normalize_node_entries(
    raw_bots: Any,
    raw_users: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], BotGraph]:
    if not isinstance(raw_bots, list) or not isinstance(raw_users, list):
        raise RelationshipEditorError("bots 和 users 必须是数组")
    if len(raw_bots) + len(raw_users) > MAX_NODES:
        raise RelationshipEditorError(f"节点总数不能超过 {MAX_NODES} 个")

    def parse(rows: list[Any], node_type: str) -> list[BotNode]:
        result: list[BotNode] = []
        for index, item in enumerate(rows, start=1):
            label = "Bot" if node_type == "bot" else "普通用户"
            if not isinstance(item, dict):
                raise RelationshipEditorError(f"第 {index} 个{label}必须是对象")
            node = BotNode.from_mapping(item, node_type=node_type)
            for field_name, limit in (
                ("display_name", 80),
                ("description", 500),
                ("platform_id", 128),
            ):
                if len(getattr(node, field_name)) > limit:
                    raise RelationshipEditorError(
                        f"第 {index} 个{label}的 {field_name} 不能超过 {limit} 个字符"
                    )
            if len(node.aliases) > 30 or len(node.capabilities) > 30:
                raise RelationshipEditorError(
                    f"第 {index} 个{label}的别名或能力标签不能超过 30 项"
                )
            if any(len(value) > 80 for value in (*node.aliases, *node.capabilities)):
                raise RelationshipEditorError(
                    f"第 {index} 个{label}的单个别名或能力标签不能超过 80 个字符"
                )
            result.append(node)
        return result

    bots = parse(raw_bots, "bot")
    users = parse(raw_users, "user")
    try:
        graph = BotGraph(bots, [], users=users)
    except GraphConfigError as exc:
        raise RelationshipEditorError(str(exc)) from exc
    return (
        [node_to_config(node) for node in bots],
        [node_to_config(node) for node in users],
        graph,
    )


def normalize_relation_entries(
    raw_relations: Any,
    bots: Iterable[BotNode],
    users: Iterable[BotNode] = (),
) -> list[dict[str, Any]]:
    """Validate Page input against the current Bot list and normalize it."""
    if not isinstance(raw_relations, list):
        raise RelationshipEditorError("relations 必须是数组")
    if len(raw_relations) > MAX_RELATIONS:
        raise RelationshipEditorError(f"关系数量不能超过 {MAX_RELATIONS} 条")

    bot_tuple = tuple(bots)
    user_tuple = tuple(users)
    bot_ids = {bot.bot_id for bot in (*bot_tuple, *user_tuple)}
    seen: set[tuple[str, str, str]] = set()
    relations: list[Relation] = []

    for index, item in enumerate(raw_relations, start=1):
        if not isinstance(item, dict):
            raise RelationshipEditorError(f"第 {index} 条关系必须是对象")
        relation = Relation.from_mapping(item)
        if relation.source_bot_id not in bot_ids:
            raise RelationshipEditorError(
                f"第 {index} 条关系的发起方 Bot 不存在: "
                f"{relation.source_bot_id or '<empty>'}"
            )
        if relation.target_bot_id not in bot_ids:
            raise RelationshipEditorError(
                f"第 {index} 条关系的目标 Bot 不存在: "
                f"{relation.target_bot_id or '<empty>'}"
            )
        if relation.source_bot_id == relation.target_bot_id:
            raise RelationshipEditorError(f"第 {index} 条关系不能指向自己")

        key = (
            relation.source_bot_id,
            relation.target_bot_id,
            relation.group_id,
        )
        if key in seen:
            raise RelationshipEditorError(
                f"关系重复: {relation.source_bot_id} -> {relation.target_bot_id}"
                f"（群 {relation.group_id or '全局'}）"
            )
        seen.add(key)

        for field_name, limit in _TEXT_LIMITS.items():
            value = getattr(relation, field_name)
            if len(value) > limit:
                raise RelationshipEditorError(
                    f"第 {index} 条关系的 {field_name} 不能超过 {limit} 个字符"
                )
        relations.append(relation)

    try:
        BotGraph(bot_tuple, relations, users=user_tuple)
    except GraphConfigError as exc:
        raise RelationshipEditorError(str(exc)) from exc
    return [relation_to_config(relation) for relation in relations]


def relationship_editor_payload(
    graph: BotGraph,
    *,
    self_bot_id: str = "",
) -> dict[str, Any]:
    """Return the safe, runtime-backed data needed by the plugin Page."""
    return {
        "self_bot_id": self_bot_id,
        "bots": [
            node_to_config(bot)
            for bot in graph.bots
        ],
        "users": [node_to_config(user) for user in graph.users],
        "nodes": [
            {
                "node_id": node.bot_id,
                "node_type": node.node_type,
                "display_name": node.display_name,
                "account_id": node.account_id,
            }
            for node in graph.participants
        ],
        "relations": [relation_to_config(relation) for relation in graph.relations],
    }
