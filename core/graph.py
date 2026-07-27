from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from .models import BotNode, Relation, clean_bool, is_placeholder_account_id


_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


class GraphConfigError(ValueError):
    """Raised when BotMesh's configured graph is ambiguous or unsafe."""


def merge_relation_layers(
    bots: Iterable[BotNode],
    manual_relations: Iterable[Relation],
    inferred_relations: Iterable[Relation],
) -> tuple[Relation, ...]:
    """Merge relationship rows while keeping explicit admin rows authoritative."""
    bot_ids = {bot.bot_id for bot in bots}
    manual = {
        (relation.source_bot_id, relation.target_bot_id, relation.group_id): relation
        for relation in manual_relations
    }
    result = list(manual.values())
    for inferred in inferred_relations:
        key = (inferred.source_bot_id, inferred.target_bot_id, inferred.group_id)
        if (
            key not in manual
            and inferred.source_bot_id in bot_ids
            and inferred.target_bot_id in bot_ids
            and inferred.source_bot_id != inferred.target_bot_id
        ):
            result.append(inferred)
    return tuple(result)


class BotGraph:
    def __init__(
        self,
        bots: Iterable[BotNode],
        relations: Iterable[Relation],
        *,
        users: Iterable[BotNode] = (),
        default_allow_ask: bool = False,
    ) -> None:
        self.default_allow_ask = bool(default_allow_ask)
        self._bots: dict[str, BotNode] = {}
        self._users: dict[str, BotNode] = {}
        self._participants: dict[str, BotNode] = {}
        self._accounts: dict[str, BotNode] = {}
        self._platforms: dict[str, BotNode] = {}
        self._aliases: dict[str, BotNode] = {}
        self._relations: dict[tuple[str, str, str], Relation] = {}

        for bot in bots:
            self._add_participant(bot, expected_type="bot")
        for user in users:
            self._add_participant(user, expected_type="user")
        self._validate_identity_names()
        for relation in relations:
            self._add_relation(relation)

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "BotGraph":
        raw_bots = config.get("bots", [])
        raw_relations = config.get("relations", [])
        bots = [
            BotNode.from_mapping(item, node_type="bot")
            for item in raw_bots
            if isinstance(item, dict)
        ]
        raw_users = config.get("users", [])
        users = [
            BotNode.from_mapping(item, node_type="user")
            for item in raw_users
            if isinstance(item, dict)
        ]
        relations = [
            Relation.from_mapping(item)
            for item in raw_relations
            if isinstance(item, dict)
        ]
        return cls(
            bots,
            relations,
            users=users,
            default_allow_ask=clean_bool(config.get("default_allow_ask"), False),
        )

    def _add_participant(self, node: BotNode, *, expected_type: str) -> None:
        if node.node_type != expected_type:
            raise GraphConfigError(
                f"节点 {node.bot_id or '<empty>'} 的类型应为 {expected_type}"
            )
        if not _ID_RE.fullmatch(node.bot_id):
            raise GraphConfigError(
                f"非法节点 ID {node.bot_id!r}；仅允许字母、数字、点、下划线和短横线"
            )
        if not node.account_id:
            raise GraphConfigError(f"节点 {node.bot_id!r} 缺少 account_id")
        if node.bot_id in self._participants:
            raise GraphConfigError(f"重复的节点 ID: {node.bot_id}")
        account_is_placeholder = is_placeholder_account_id(node.account_id)
        if not account_is_placeholder and node.account_id in self._accounts:
            other = self._accounts[node.account_id]
            raise GraphConfigError(
                f"account_id {node.account_id!r} 同时属于 {other.bot_id} 和 {node.bot_id}"
            )
        if expected_type == "bot" and node.platform_id:
            if node.platform_id in self._platforms:
                other = self._platforms[node.platform_id]
                raise GraphConfigError(
                    f"platform_id {node.platform_id!r} 同时属于 {other.bot_id} 和 {node.bot_id}"
                )
        aliases = (node.display_name, *node.aliases)
        for raw_alias in aliases:
            alias = raw_alias.casefold()
            if not alias:
                continue
            if alias in self._aliases:
                other = self._aliases[alias]
                raise GraphConfigError(
                    f"名称/别名 {raw_alias!r} 同时属于 {other.bot_id} 和 {node.bot_id}"
                )
        self._participants[node.bot_id] = node
        if expected_type == "bot":
            self._bots[node.bot_id] = node
            if node.platform_id:
                self._platforms[node.platform_id] = node
        else:
            self._users[node.bot_id] = node
        if not account_is_placeholder:
            self._accounts[node.account_id] = node
        for raw_alias in aliases:
            alias = raw_alias.casefold()
            if alias:
                self._aliases[alias] = node

    def _add_relation(self, relation: Relation) -> None:
        if relation.source_bot_id not in self._participants:
            raise GraphConfigError(
                f"关系源 Bot 不存在: {relation.source_bot_id or '<empty>'}"
            )
        if relation.target_bot_id not in self._participants:
            raise GraphConfigError(
                f"关系目标 Bot 不存在: {relation.target_bot_id or '<empty>'}"
            )
        if relation.source_bot_id == relation.target_bot_id:
            raise GraphConfigError("不能创建 Bot 指向自己的关系")
        key = (
            relation.source_bot_id,
            relation.target_bot_id,
            relation.group_id,
        )
        if key in self._relations:
            raise GraphConfigError(
                f"重复关系: {key[0]} -> {key[1]}（群 {key[2] or '全局'}）"
            )
        self._relations[key] = relation

    def _validate_identity_names(self) -> None:
        identities: dict[str, BotNode] = {}
        for bot in self._participants.values():
            identity_values = [bot.bot_id, bot.display_name, *bot.aliases]
            if not is_placeholder_account_id(bot.account_id):
                identity_values.append(bot.account_id)
            for value in identity_values:
                normalized = value.casefold().strip()
                if not normalized:
                    continue
                other = identities.get(normalized)
                if other is not None and other.bot_id != bot.bot_id:
                    raise GraphConfigError(
                        f"身份名称 {value!r} 同时对应 {other.bot_id} 和 {bot.bot_id}"
                    )
                identities[normalized] = bot

    @property
    def bots(self) -> tuple[BotNode, ...]:
        return tuple(self._bots.values())

    @property
    def users(self) -> tuple[BotNode, ...]:
        return tuple(self._users.values())

    @property
    def participants(self) -> tuple[BotNode, ...]:
        return tuple(self._participants.values())

    @property
    def relations(self) -> tuple[Relation, ...]:
        return tuple(self._relations.values())

    def get_bot(self, bot_id: str) -> BotNode | None:
        return self._bots.get(str(bot_id or "").strip())

    def get_user(self, user_id: str) -> BotNode | None:
        return self._users.get(str(user_id or "").strip())

    def get_participant(self, node_id: str) -> BotNode | None:
        return self._participants.get(str(node_id or "").strip())

    def resolve_bot(self, value: str) -> BotNode | None:
        cleaned = str(value or "").strip()
        resolved = (
            self._bots.get(cleaned)
            or self._accounts.get(cleaned)
            or self._aliases.get(cleaned.casefold())
        )
        return resolved if resolved is not None and resolved.node_type == "bot" else None

    def resolve_participant(self, value: str) -> BotNode | None:
        cleaned = str(value or "").strip()
        return (
            self._participants.get(cleaned)
            or self._accounts.get(cleaned)
            or self._aliases.get(cleaned.casefold())
        )

    def get_by_account(self, account_id: str) -> BotNode | None:
        node = self._accounts.get(str(account_id or "").strip())
        return node if node is not None and node.node_type == "bot" else None

    def get_by_platform(self, platform_id: str) -> BotNode | None:
        return self._platforms.get(str(platform_id or "").strip())

    def get_user_by_account(self, account_id: str) -> BotNode | None:
        node = self._accounts.get(str(account_id or "").strip())
        return node if node is not None and node.node_type == "user" else None

    def get_relation(
        self,
        source_bot_id: str,
        target_bot_id: str,
        group_id: str = "",
    ) -> Relation | None:
        scope = str(group_id or "").strip()
        if scope:
            scoped = self._relations.get((source_bot_id, target_bot_id, scope))
            if scoped is not None:
                return scoped
        return self._relations.get((source_bot_id, target_bot_id, ""))

    def can_ask(
        self,
        source_bot_id: str,
        target_bot_id: str,
        group_id: str = "",
    ) -> bool:
        if source_bot_id == target_bot_id:
            return False
        relation = self.get_relation(source_bot_id, target_bot_id, group_id)
        if relation is None:
            return self.default_allow_ask
        return relation.allow_ask

    def accessible_from(
        self,
        source_bot_id: str,
        group_id: str = "",
    ) -> tuple[BotNode, ...]:
        return tuple(
            bot
            for bot in self._bots.values()
            if self.can_ask(source_bot_id, bot.bot_id, group_id)
        )

    def relations_for_group(self, group_id: str = "") -> tuple[Relation, ...]:
        """Return one effective row per direction, with group rows overriding global."""
        scope = str(group_id or "").strip()
        selected: dict[tuple[str, str], Relation] = {}
        for relation in self._relations.values():
            if not relation.group_id:
                selected[(relation.source_bot_id, relation.target_bot_id)] = relation
        if scope:
            for relation in self._relations.values():
                if relation.group_id == scope:
                    selected[(relation.source_bot_id, relation.target_bot_id)] = relation
        return tuple(selected.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "bots": [
                {
                    "bot_id": bot.bot_id,
                    "display_name": bot.display_name,
                    "account_id": bot.account_id,
                    "platform_id": bot.platform_id,
                    "description": bot.description,
                    "capabilities": list(bot.capabilities),
                    "aliases": list(bot.aliases),
                }
                for bot in self.bots
            ],
            "users": [
                {
                    "user_id": user.bot_id,
                    "display_name": user.display_name,
                    "account_id": user.account_id,
                    "description": user.description,
                    "aliases": list(user.aliases),
                }
                for user in self.users
            ],
            "relations": [
                {
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
                    "origin": relation.origin,
                    "confidence": relation.confidence,
                    "evidence": relation.evidence,
                    "prompt_hash": relation.prompt_hash,
                }
                for relation in self.relations
            ],
        }
