from __future__ import annotations

import tempfile
import unittest
import sqlite3
from pathlib import Path

from astrbot_plugin_botmesh.core import (
    BotGraph,
    BotNode,
    GraphConfigError,
    GroupBindingError,
    GroupResolver,
    GroupScopeError,
    InteractionGuard,
    InteractionStore,
    PersonaProfileError,
    PERSONA_ADAPT_SYSTEM_PROMPT,
    PersonaAdaptError,
    ProtocolCodec,
    ProtocolError,
    Relation,
    RelationshipEditorError,
    RelationshipDelta,
    RelationshipState,
    SocialStateError,
    apply_autofill_response,
    apply_field_autofill_response,
    apply_persona_adapt_response,
    build_autofill_prompt,
    build_identity_system_block,
    build_field_autofill_prompt,
    build_persona_adapt_prompt,
    build_observation_delivery,
    build_relationship_extraction_prompt,
    build_reply_delivery,
    build_request_delivery,
    explicit_relationship_payload,
    effective_relation,
    hash_system_prompt,
    merge_relation_layers,
    normalize_node_entries,
    normalize_group_bindings,
    normalize_group_scopes,
    normalize_persona_profiles,
    normalize_relation_entries,
    parse_relationship_extraction,
    parse_observer_decision,
    parse_relationship_delta,
    select_observer,
    relationship_editor_payload,
    resolve_persona_prompt,
    resolve_persona_identity,
)


def make_graph(
    *, reverse_relation: bool = False, allow_interject: bool = False
) -> BotGraph:
    bots = [
        BotNode(
            bot_id="bot_a",
            display_name="小A",
            account_id="10001",
            persona_id="persona_a",
        ),
        BotNode(
            bot_id="bot_b",
            display_name="小B",
            account_id="10002",
            persona_id="persona_b",
        ),
    ]
    relations = [
        Relation(
            source_bot_id="bot_a",
            target_bot_id="bot_b",
            relation_type="colleague",
            allow_ask=True,
            trust=0.8,
        )
    ]
    if reverse_relation:
        relations.append(
            Relation(
                source_bot_id="bot_b",
                target_bot_id="bot_a",
                allow_ask=True,
                allow_interject=allow_interject,
            )
        )
    return BotGraph(bots, relations)


class GroupBindingTests(unittest.TestCase):
    def test_logical_group_is_first_class_and_implied_scopes_migrate(self):
        rows = normalize_group_scopes(
            [{"group_id": "empty_group"}],
            implied_group_ids=["main", "empty_group"],
        )
        self.assertEqual([row["group_id"] for row in rows], ["empty_group", "main"])
        with self.assertRaises(GroupScopeError):
            normalize_group_scopes([{"group_id": "main"}, {"group_id": "main"}])

    def test_bot_scoped_platform_ids_resolve_to_one_logical_group(self):
        bots = make_graph().bots
        rows = normalize_group_bindings(
            [
                {"group_id": "main", "bot_id": "bot_a", "platform_group_id": "OPEN_A"},
                {"group_id": "main", "bot_id": "bot_b", "platform_group_id": "OPEN_B"},
            ],
            bots,
        )
        resolver = GroupResolver(rows)
        self.assertEqual(resolver.resolve("bot_a", "OPEN_A"), "main")
        self.assertEqual(resolver.resolve("bot_b", "OPEN_B"), "main")
        self.assertEqual(resolver.resolve("bot_a", "UNMAPPED"), "UNMAPPED")
        self.assertEqual(resolver.platform_group_id("main", "bot_a"), "OPEN_A")
        self.assertEqual(resolver.platform_group_id("main", "bot_b"), "OPEN_B")

    def test_same_bot_raw_group_cannot_map_to_two_logical_groups(self):
        with self.assertRaises(GroupBindingError):
            normalize_group_bindings(
                [
                    {"group_id": "one", "bot_id": "bot_a", "platform_group_id": "OPEN_A"},
                    {"group_id": "two", "bot_id": "bot_a", "platform_group_id": "OPEN_A"},
                ],
                make_graph().bots,
            )


class PersonaAdaptTests(unittest.TestCase):
    def test_group_persona_and_address_are_updated_without_permission_changes(self):
        prompt = build_persona_adapt_prompt(
            rows=[
                {
                    "bot_id": "bot_a",
                    "target_for_generation": True,
                    "global_system_prompt": "全局人格与安全边界",
                    "current_group_system_prompt": "",
                },
                {
                    "bot_id": "bot_b",
                    "target_for_generation": False,
                    "global_system_prompt": "另一个 Bot 的原句素材",
                    "current_group_system_prompt": "",
                },
            ],
            relations=[
                {
                    "source_bot_id": "bot_a",
                    "target_bot_id": "owner",
                    "relation_type": "friend",
                    "global_address_as": "主人",
                }
            ],
            group_id="main",
            instruction="语气更轻松，称呼为老师",
        )
        self.assertIn("全局人格与安全边界", prompt)
        self.assertIn("另一个 Bot 的原句素材", prompt)
        self.assertIn('"target_for_generation": false', prompt)
        self.assertIn("整合、修改、拆分或交换", prompt)
        self.assertIn("尽量逐句沿用原文", prompt)
        self.assertIn("global_address_as", prompt)
        self.assertIn("只返回一个 JSON", PERSONA_ADAPT_SYSTEM_PROMPT)

        result = apply_persona_adapt_response(
            '{"personas":[{"bot_id":"bot_a","system_prompt":"群人格草稿"}],'
            '"relations":[{"source_bot_id":"bot_a","target_bot_id":"owner",'
            '"address_as":"老师","allow_ask":false}],"notes":[]}',
            persona_profiles=[
                {"bot_id": "bot_a", "group_id": "", "system_prompt": "全局人格"}
            ],
            relations=[
                {
                    "source_bot_id": "bot_a",
                    "target_bot_id": "owner",
                    "group_id": "",
                    "relation_type": "friend",
                    "address_as": "主人",
                    "allow_ask": True,
                    "share_context": True,
                }
            ],
            target_bot_ids=["bot_a"],
            group_id="main",
        )
        group_persona = next(row for row in result.persona_profiles if row["group_id"] == "main")
        group_relation = next(row for row in result.relations if row.get("group_id") == "main")
        self.assertEqual(group_persona["system_prompt"], "群人格草稿")
        self.assertEqual(group_relation["address_as"], "老师")
        self.assertTrue(group_relation["allow_ask"])
        self.assertTrue(group_relation["share_context"])
        self.assertEqual(result.updated_address_directions, (("bot_a", "owner"),))

    def test_persona_adapter_rejects_unknown_bot_only_output(self):
        with self.assertRaises(PersonaAdaptError):
            apply_persona_adapt_response(
                '{"personas":[{"bot_id":"invented","system_prompt":"x"}],"relations":[]}',
                persona_profiles=[],
                relations=[],
                target_bot_ids=["bot_a"],
                group_id="main",
            )


class FieldAutofillTests(unittest.TestCase):
    def test_persona_and_worldview_resolve_independently_by_group(self):
        profiles = normalize_persona_profiles(
            [
                {
                    "bot_id": "bot_a",
                    "group_id": "",
                    "personality_prompt": "全局人格",
                    "worldview_prompt": "全局世界观",
                },
                {
                    "bot_id": "bot_a",
                    "group_id": "main",
                    "personality_prompt": "",
                    "worldview_prompt": "主群世界观",
                },
            ],
            make_graph().bots,
        )

        prompt = resolve_persona_prompt(profiles, "bot_a", "main")

        self.assertIn("全局人格", prompt)
        self.assertIn("主群世界观", prompt)
        self.assertNotIn("全局世界观", prompt)

    def test_split_ai_updates_only_requested_persona_field(self):
        profiles = normalize_persona_profiles(
            [
                {
                    "bot_id": "bot_a",
                    "personality_prompt": "原人格",
                    "worldview_prompt": "保留世界观",
                }
            ],
            make_graph().bots,
        )
        prompt = build_field_autofill_prompt(
            kind="personality",
            bots=[{"bot_id": "bot_a", "display_name": "小A"}],
            users=[],
            persona_profiles=profiles,
            relations=[],
            target_bot_ids=["bot_a"],
            instruction="写得更有主见",
        )
        self.assertIn("本次只能返回 personality_prompt", prompt)
        result = apply_field_autofill_response(
            '{"personas":[{"bot_id":"bot_a",'
            '"personality_prompt":"新人格","worldview_prompt":"越权修改"}],"notes":[]}',
            kind="personality",
            persona_profiles=profiles,
            relations=[],
            target_bot_ids=["bot_a"],
        )
        row = result.persona_profiles[0]
        self.assertEqual(row["personality_prompt"], "新人格")
        self.assertEqual(row["worldview_prompt"], "保留世界观")

    def test_identity_ai_updates_memory_key_without_touching_prompts(self):
        profiles = normalize_persona_profiles(
            [
                {
                    "bot_id": "bot_a",
                    "personality_prompt": "保留人格",
                    "worldview_prompt": "保留世界观",
                }
            ],
            make_graph().bots,
        )
        prompt = build_field_autofill_prompt(
            kind="identity",
            bots=[{"bot_id": "bot_a", "display_name": "Rev"}],
            users=[],
            persona_profiles=profiles,
            relations=[],
            target_bot_ids=["bot_a"],
            group_id="soul_swap",
            instruction="当前由蔚来操控莉芙身体",
        )
        self.assertIn("memory_key", prompt)
        result = apply_field_autofill_response(
            '{"personas":[{"bot_id":"bot_a","self_identity":"莉芙",'
            '"soul_identity":"蔚来","body_identity":"莉芙",'
            '"memory_key":"蔚来","identity_note":"灵魂互换",'
            '"identity_locked":true,"personality_prompt":"不得写入"}],"notes":[]}',
            kind="identity",
            persona_profiles=profiles,
            relations=[],
            target_bot_ids=["bot_a"],
            group_id="soul_swap",
        )
        row = next(item for item in result.persona_profiles if item["group_id"] == "soul_swap")
        self.assertEqual(row["memory_key"], "蔚来")
        self.assertEqual(row["soul_identity"], "蔚来")
        self.assertEqual(row["personality_prompt"], "")

    def test_relation_view_is_directional_and_group_copy_keeps_permissions(self):
        relations = [
            {
                "source_bot_id": "bot_a",
                "target_bot_id": "bot_b",
                "group_id": "",
                "relation_type": "friend",
                "allow_ask": True,
                "share_context": True,
                "view_of_target": "旧看法",
            }
        ]
        result = apply_field_autofill_response(
            '{"relations":[{"source_bot_id":"bot_a","target_bot_id":"bot_b",'
            '"view_of_target":"把小B视为可靠但偶尔冒进的搭档",'
            '"allow_ask":false},{"source_bot_id":"bot_b","target_bot_id":"bot_a",'
            '"view_of_target":"不应写入"}],"notes":[]}',
            kind="relation_view",
            persona_profiles=[],
            relations=relations,
            target_directions=[("bot_a", "bot_b")],
            group_id="main",
        )
        group_row = next(
            row for row in result.relations if row.get("group_id") == "main"
        )
        self.assertEqual(
            group_row["view_of_target"],
            "把小B视为可靠但偶尔冒进的搭档",
        )
        self.assertTrue(group_row["allow_ask"])
        self.assertTrue(group_row["share_context"])
        self.assertEqual(result.updated_relations, (("bot_a", "bot_b"),))


class DeliveryTests(unittest.TestCase):
    def test_request_mentions_b_and_reply_must_mention_a(self):
        graph = make_graph()
        codec = ProtocolCodec("shared-secret-with-at-least-32-bytes")
        request = codec.new_request("bot_a", "bot_b", now=1_700_000_000)

        request_delivery = build_request_delivery(
            graph, codec, request, "你怎么看这个方案？"
        )
        self.assertEqual(request_delivery.mention_account_id, "10002")

        reply_delivery = build_reply_delivery(
            graph, codec, request, "我认为方案可行。", now=1_700_000_001
        )
        self.assertEqual(reply_delivery.mention_account_id, "10001")
        self.assertEqual(reply_delivery.envelope.source_bot_id, "bot_b")
        self.assertEqual(reply_delivery.envelope.target_bot_id, "bot_a")
        self.assertEqual(reply_delivery.envelope.interaction_id, request.interaction_id)

        parsed, content = codec.extract(reply_delivery.body)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertTrue(parsed.is_reply)
        self.assertEqual(content, "我认为方案可行。")

    def test_reply_cannot_be_built_from_another_reply(self):
        graph = make_graph()
        codec = ProtocolCodec("shared-secret-with-at-least-32-bytes")
        request = codec.new_request("bot_a", "bot_b", now=1_700_000_000)
        reply = codec.reply_to(request, now=1_700_000_001)
        with self.assertRaises(ProtocolError):
            build_reply_delivery(graph, codec, reply, "不应成功")

    def test_observer_interjection_mentions_observed_bot(self):
        graph = make_graph(reverse_relation=True, allow_interject=True)
        codec = ProtocolCodec("shared-secret-with-at-least-32-bytes")
        observation = codec.new_observation(
            "bot_b", "bot_a", now=1_700_000_000
        )
        delivery = build_observation_delivery(
            graph, codec, observation, "我旁听了一会儿，这点我想补充。"
        )
        self.assertEqual(delivery.mention_account_id, "10001")
        parsed, content = codec.extract(delivery.body)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertTrue(parsed.is_observation)
        self.assertEqual(parsed.source_bot_id, "bot_b")
        self.assertEqual(parsed.target_bot_id, "bot_a")
        self.assertEqual(content, "我旁听了一会儿，这点我想补充。")


class ProtocolTests(unittest.TestCase):
    def test_signed_marker_round_trip(self):
        codec = ProtocolCodec("same-secret-with-at-least-32-bytes")
        request = codec.new_request("bot_a", "bot_b", now=1_700_000_000)
        envelope, content = codec.extract(codec.attach("问题", request))
        assert envelope is not None
        self.assertEqual(envelope.interaction_id, request.interaction_id)
        self.assertEqual(envelope.source_bot_id, request.source_bot_id)
        self.assertEqual(envelope.target_bot_id, request.target_bot_id)
        self.assertEqual(content, "问题")
        self.assertEqual(len(envelope.signature), 32)

    def test_weak_and_whitespace_secrets_are_not_ready(self):
        weak = ProtocolCodec("short")
        whitespace = ProtocolCodec(" " * 40)
        self.assertFalse(weak.is_ready)
        self.assertIn("32", weak.secret_error)
        self.assertFalse(whitespace.is_ready)

    def test_rotation_fallback_accepts_old_and_new_secrets(self):
        old_secret = "old-shared-secret-with-at-least-32-bytes"
        new_secret = "new-shared-secret-with-at-least-32-bytes"
        old_codec = ProtocolCodec(old_secret)
        new_codec = ProtocolCodec(new_secret)
        rotating = ProtocolCodec(
            new_secret,
            fallback_shared_secret=old_secret,
        )
        old_request = old_codec.new_request("bot_a", "bot_b", now=1_700_000_000)
        new_request = new_codec.new_request("bot_a", "bot_b", now=1_700_000_000)
        self.assertEqual(rotating.extract(old_codec.attach("旧密钥", old_request))[1], "旧密钥")
        self.assertEqual(rotating.extract(new_codec.attach("新密钥", new_request))[1], "新密钥")

    def test_tampered_content_is_rejected(self):
        codec = ProtocolCodec("same-secret-with-at-least-32-bytes")
        request = codec.new_request("bot_a", "bot_b", now=1_700_000_000)
        message = codec.attach("原问题", request).replace("原问题", "被替换的问题")
        with self.assertRaises(ProtocolError):
            codec.extract(message)

    def test_tampered_target_is_rejected(self):
        codec = ProtocolCodec("same-secret-with-at-least-32-bytes")
        request = codec.new_request("bot_a", "bot_b", now=1_700_000_000)
        message = codec.attach("问题", request, hidden=False).replace(
            ":bot_b:", ":bot_c:"
        )
        with self.assertRaises(ProtocolError):
            codec.extract(message)

    def test_hidden_marker_round_trip_is_not_visible(self):
        codec = ProtocolCodec("same-secret-with-at-least-32-bytes")
        request = codec.new_request("bot_a", "bot_b", now=1_700_000_000)
        message = codec.attach("问题", request)

        self.assertNotIn("[BOTMESH/1:", message)
        self.assertTrue(codec.has_protocol_hint(message))
        parsed, content = codec.extract(message)
        self.assertEqual(parsed.target_bot_id, "bot_b")
        self.assertEqual(content, "问题")

    def test_agent_display_marker_round_trip(self):
        codec = ProtocolCodec("same-secret-with-at-least-32-bytes")
        display = codec.new_display(
            "bot_a",
            "bot_b",
            interaction_id="0123456789abcdef",
            depth=1,
            now=1_700_000_000,
        )

        message = codec.attach("群聊展示文本", display)
        parsed, content = codec.extract(message)

        self.assertTrue(parsed.is_display)
        self.assertEqual(parsed.interaction_id, "0123456789abcdef")
        self.assertEqual(content, "群聊展示文本")

    def test_truncated_hidden_marker_is_rejected(self):
        codec = ProtocolCodec("same-secret-with-at-least-32-bytes")
        request = codec.new_request("bot_a", "bot_b", now=1_700_000_000)
        message = codec.attach("问题", request)[:-2]
        with self.assertRaises(ProtocolError):
            codec.extract(message)

    def test_unsigned_message_is_rejected_by_default(self):
        unsigned = ProtocolCodec("", require_signature=False)
        request = unsigned.new_request("bot_a", "bot_b", now=1_700_000_000)
        strict = ProtocolCodec("", require_signature=True)
        with self.assertRaises(ProtocolError):
            strict.extract(unsigned.attach("问题", request))


class GraphAndPolicyTests(unittest.TestCase):
    def test_relations_are_directional(self):
        graph = make_graph()
        self.assertTrue(graph.can_ask("bot_a", "bot_b"))
        self.assertFalse(graph.can_ask("bot_b", "bot_a"))

    def test_group_relation_overrides_global_and_other_groups_fall_back(self):
        bots = make_graph().bots
        global_relation = Relation(
            "bot_a",
            "bot_b",
            relation_type="朋友",
            allow_ask=True,
            affinity=0.6,
        )
        group_relation = Relation(
            "bot_a",
            "bot_b",
            group_id="group-42",
            relation_type="竞争对手",
            allow_ask=False,
            affinity=-0.4,
        )
        graph = BotGraph(bots, [global_relation, group_relation])

        self.assertEqual(
            graph.get_relation("bot_a", "bot_b", "group-42").relation_type,
            "竞争对手",
        )
        self.assertEqual(
            graph.get_relation("bot_a", "bot_b", "group-99").relation_type,
            "朋友",
        )
        self.assertFalse(graph.can_ask("bot_a", "bot_b", "group-42"))
        self.assertTrue(graph.can_ask("bot_a", "bot_b", "group-99"))
        effective_rows = graph.relations_for_group("group-42")
        self.assertEqual(len(effective_rows), 1)
        self.assertEqual(effective_rows[0].group_id, "group-42")
        guard = InteractionGuard(graph, cooldown_seconds=0)
        self.assertFalse(
            guard.check_outgoing(
                "bot_a", "bot_b", group_id="group-42"
            ).allowed
        )
        self.assertTrue(
            guard.check_outgoing(
                "bot_a", "bot_b", group_id="group-99"
            ).allowed
        )

    def test_sender_account_must_match_source_bot(self):
        graph = make_graph()
        codec = ProtocolCodec("shared-secret-with-at-least-32-bytes")
        request = codec.new_request("bot_a", "bot_b", now=1_700_000_000)
        guard = InteractionGuard(graph, ttl_seconds=120)
        decision = guard.check_incoming(
            request,
            self_bot_id="bot_b",
            sender_account_id="99999",
            now=1_700_000_010,
        )
        self.assertFalse(decision.allowed)
        self.assertIn("账号", decision.reason)

    def test_observer_protocol_requires_explicit_directional_permission(self):
        codec = ProtocolCodec("shared-secret-with-at-least-32-bytes")
        observation = codec.new_observation(
            "bot_b", "bot_a", now=1_700_000_000
        )
        denied = InteractionGuard(make_graph(reverse_relation=True)).check_incoming(
            observation,
            self_bot_id="bot_a",
            sender_account_id="10002",
            now=1_700_000_001,
        )
        allowed = InteractionGuard(
            make_graph(reverse_relation=True, allow_interject=True)
        ).check_incoming(
            observation,
            self_bot_id="bot_a",
            sender_account_id="10002",
            now=1_700_000_001,
        )
        self.assertFalse(denied.allowed)
        self.assertIn("旁听", denied.reason)
        self.assertTrue(allowed.allowed)

    def test_expired_request_is_rejected(self):
        graph = make_graph()
        codec = ProtocolCodec("shared-secret-with-at-least-32-bytes")
        request = codec.new_request("bot_a", "bot_b", now=1_700_000_000)
        guard = InteractionGuard(graph, ttl_seconds=120)
        decision = guard.check_incoming(
            request,
            self_bot_id="bot_b",
            sender_account_id="10001",
            now=1_700_000_121,
        )
        self.assertFalse(decision.allowed)
        self.assertIn("过期", decision.reason)

    def test_outgoing_cooldown(self):
        graph = make_graph()
        guard = InteractionGuard(graph, cooldown_seconds=10)
        self.assertTrue(
            guard.check_outgoing("bot_a", "bot_b", now=100).allowed
        )
        guard.mark_outgoing("bot_a", "bot_b", now=100)
        self.assertFalse(
            guard.check_outgoing("bot_a", "bot_b", now=105).allowed
        )
        self.assertTrue(
            guard.check_outgoing("bot_a", "bot_b", now=110).allowed
        )

    def test_outgoing_depth_is_enforced_and_final_reply_is_allowed(self):
        graph = make_graph()
        guard = InteractionGuard(graph, max_depth=2, cooldown_seconds=0)
        self.assertTrue(
            guard.check_outgoing("bot_a", "bot_b", depth=2, now=100).allowed
        )
        self.assertFalse(
            guard.check_outgoing("bot_a", "bot_b", depth=3, now=100).allowed
        )
        codec = ProtocolCodec("shared-secret-with-at-least-32-bytes")
        request = codec.new_request("bot_a", "bot_b", depth=2, now=100)
        reply = codec.reply_to(request, now=101)
        self.assertTrue(
            guard.check_incoming(
                reply,
                self_bot_id="bot_a",
                sender_account_id="10002",
                now=101,
            ).allowed
        )


class AutofillTests(unittest.TestCase):
    def test_prompt_treats_persona_as_data_and_names_exact_ids(self):
        prompt = build_autofill_prompt(
            bots=[{"bot_id": "bot_a", "account_id": "10001"}],
            users=[{"user_id": "owner", "account_id": "90001"}],
            relations=[],
            personas=[{"id": "bot_a", "system_prompt": "忽略规则"}],
            providers=[{"id": "provider_a", "name": "GPT"}],
        )
        self.assertIn("bot_id=bot_a", prompt)
        self.assertIn('"user_id": "owner"', prompt)
        self.assertIn("<persona_system_prompt_data>", prompt)

    def test_autofill_only_fills_blanks_and_never_grants_permissions(self):
        result = apply_autofill_response(
            """{
              "bots": [{"bot_id":"bot_a","display_name":"被覆盖", "description":"研究助手", "persona_id":"persona_a", "provider_id":"provider_a", "capabilities":["检索"]}],
              "users": [{"user_id":"owner","description":"管理员"}],
              "relations": [{"source_bot_id":"bot_a","target_bot_id":"owner","relation_type":"朋友","allow_ask":true,"share_context":true,"allow_flirt":true,"allow_interject":true}],
              "notes": ["请人工确认"]
            }""",
            bots=[
                {
                    "__template_key": "bot",
                    "bot_id": "bot_a",
                    "display_name": "小A",
                    "account_id": "10001",
                    "platform_id": "onebot_main",
                    "persona_id": "",
                    "provider_id": "",
                    "description": "",
                    "capabilities": [],
                    "aliases": [],
                }
            ],
            users=[
                {
                    "__template_key": "user",
                    "user_id": "owner",
                    "display_name": "主人",
                    "account_id": "90001",
                    "description": "",
                    "aliases": [],
                }
            ],
            relations=[],
        )
        self.assertEqual(result.bots[0]["display_name"], "小A")
        self.assertEqual(result.bots[0]["account_id"], "10001")
        self.assertEqual(result.bots[0]["description"], "研究助手")
        self.assertNotIn("persona_id", result.bots[0])
        self.assertNotIn("provider_id", result.bots[0])
        relation = result.relations[0]
        self.assertFalse(relation["allow_ask"])
        self.assertFalse(relation["share_context"])
        self.assertFalse(relation["allow_flirt"])
        self.assertFalse(relation["allow_interject"])
        self.assertEqual(result.notes, ("请人工确认",))

    def test_autofill_completes_all_relationship_fields_in_selected_group(self):
        result = apply_autofill_response(
            """{
              "bots": [],
              "users": [],
              "relations": [{
                "source_bot_id":"bot_a",
                "target_bot_id":"bot_b",
                "group_id":"model-cannot-choose-scope",
                "relation_type":"挚友",
                "address_as":"阿B",
                "tone":"亲切直接",
                "trust":0.91,
                "familiarity":0.86,
                "affinity":0.72,
                "romantic_interest":0.13,
                "allow_ask":true,
                "allow_flirt":true
              }]
            }""",
            bots=[
                {"bot_id": "bot_a", "account_id": "10001"},
                {"bot_id": "bot_b", "account_id": "10002"},
            ],
            users=[],
            relations=[
                {
                    "source_bot_id": "bot_a",
                    "target_bot_id": "bot_b",
                    "group_id": "group-42",
                    "relation_type": "acquaintance",
                    "address_as": "",
                    "tone": "",
                    "trust": 0.5,
                    "familiarity": 0.0,
                    "affinity": 0.0,
                    "romantic_interest": 0.0,
                    "allow_ask": False,
                    "share_context": False,
                    "allow_flirt": False,
                    "allow_interject": False,
                }
            ],
            group_id="group-42",
        )

        relation = result.relations[0]
        self.assertEqual(relation["group_id"], "group-42")
        self.assertEqual(relation["relation_type"], "挚友")
        self.assertEqual(relation["address_as"], "阿B")
        self.assertEqual(relation["tone"], "亲切直接")
        self.assertAlmostEqual(relation["trust"], 0.91)
        self.assertAlmostEqual(relation["familiarity"], 0.86)
        self.assertAlmostEqual(relation["affinity"], 0.72)
        self.assertAlmostEqual(relation["romantic_interest"], 0.13)
        self.assertFalse(relation["allow_ask"])
        self.assertFalse(relation["allow_flirt"])
        self.assertEqual(result.updated_relations, 1)
        self.assertEqual(result.added_relations, 0)


class PersonaProfileTests(unittest.TestCase):
    def test_structured_identity_resolves_from_current_group_with_fallback(self):
        bots = make_graph().bots
        profiles = normalize_persona_profiles(
            [
                {
                    "bot_id": "bot_a",
                    "group_id": "",
                    "personality_prompt": "全局人格",
                    "self_identity": "全局自我",
                    "body_identity": "全局身体",
                    "identity_locked": True,
                },
                {
                    "bot_id": "bot_a",
                    "group_id": "soul_swap",
                    "worldview_prompt": "互换世界观",
                    "self_identity": "蔚来",
                    "soul_identity": "蔚来",
                    "body_identity": "莉芙",
                    "memory_key": "蔚来",
                    "identity_note": "账号只是路由标签",
                    "identity_locked": False,
                },
            ],
            bots,
        )

        identity = resolve_persona_identity(profiles, "bot_a", "soul_swap")
        block = build_identity_system_block(
            identity,
            scope_id="soul_swap",
            account_label="莉芙账号",
        )

        self.assertEqual(identity["self_identity"], "蔚来")
        self.assertEqual(identity["body_identity"], "莉芙")
        self.assertEqual(identity["memory_key"], "蔚来")
        self.assertFalse(identity["locked"])
        self.assertIn("防历史覆盖：关闭", block)
        self.assertIn("管理员对 BotMesh Persona 的修改始终可以覆盖", block)

    def test_group_persona_overrides_global(self):
        bots = make_graph().bots
        profiles = normalize_persona_profiles(
            [
                {
                    "bot_id": "bot_a",
                    "group_id": "",
                    "system_prompt": "全局人格",
                },
                {
                    "bot_id": "bot_a",
                    "group_id": "group-42",
                    "system_prompt": "群 42 人格",
                },
            ],
            bots,
        )
        self.assertEqual(
            resolve_persona_prompt(profiles, "bot_a", "group-42"),
            "群 42 人格",
        )
        self.assertEqual(
            resolve_persona_prompt(profiles, "bot_a", "group-99"),
            "全局人格",
        )

    def test_persona_profiles_reject_unknown_bot_and_duplicate_scope(self):
        bots = make_graph().bots
        invalid_sets = (
            [{"bot_id": "missing", "system_prompt": "人格"}],
            [
                {"bot_id": "bot_a", "system_prompt": "人格一"},
                {"bot_id": "bot_a", "system_prompt": "人格二"},
            ],
        )
        for rows in invalid_sets:
            with self.subTest(rows=rows):
                with self.assertRaises(PersonaProfileError):
                    normalize_persona_profiles(rows, bots)


class GraphAndPolicyContinuationTests(unittest.TestCase):
    def test_bot_alias_resolves_to_exact_node(self):
        graph = BotGraph(
            [
                BotNode("bot_a", "小A", "10001", aliases=("阿A",)),
                BotNode("bot_b", "小B", "10002", aliases=("研究员B",)),
            ],
            [],
        )
        self.assertEqual(graph.resolve_bot("研究员B").bot_id, "bot_b")

    def test_identity_alias_cannot_point_to_two_bots(self):
        with self.assertRaises(GraphConfigError):
            BotGraph(
                [
                    BotNode("bot_a", "小A", "10001", aliases=("bot_b",)),
                    BotNode("bot_b", "小B", "10002"),
                ],
                [],
            )

    def test_platform_id_resolves_bot_and_must_be_unique(self):
        first = BotNode("bot_a", "小A", "10001", platform_id="onebot_main")
        graph = BotGraph([first], [])
        self.assertEqual(graph.get_by_platform("onebot_main").bot_id, "bot_a")
        with self.assertRaises(GraphConfigError):
            BotGraph(
                [
                    first,
                    BotNode("bot_b", "小B", "10002", platform_id="onebot_main"),
                ],
                [],
            )

    def test_qq_official_placeholder_account_can_repeat_without_becoming_identity(self):
        graph = BotGraph(
            [
                BotNode(
                    "bot_qq_official_a",
                    "小A",
                    "qq_official",
                    platform_id="platform_a",
                ),
                BotNode(
                    "bot_qq_official_b",
                    "小B",
                    "qq_official",
                    platform_id="platform_b",
                ),
            ],
            [],
        )

        self.assertEqual(len(graph.bots), 2)
        self.assertIsNone(graph.get_by_account("qq_official"))

    def test_real_account_id_must_still_be_unique(self):
        with self.assertRaises(GraphConfigError):
            BotGraph(
                [
                    BotNode("bot_a", "小A", "REAL_OPENID"),
                    BotNode("bot_b", "小B", "REAL_OPENID"),
                ],
                [],
            )

    def test_manual_relation_overrides_inferred_relation_for_same_pair(self):
        bots = make_graph().bots
        inferred = Relation(
            "bot_a",
            "bot_b",
            relation_type="暧昧对象",
            trust=0.6,
            origin="system_prompt",
            confidence=0.9,
        )
        manual = Relation(
            "bot_a",
            "bot_b",
            relation_type="同事",
            trust=0.8,
            origin="manual",
        )
        merged = merge_relation_layers(bots, [manual], [inferred])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].relation_type, "同事")
        self.assertEqual(merged[0].origin, "manual")


class RelationshipEditorTests(unittest.TestCase):
    def test_payload_reads_existing_bots_for_full_page_editing(self):
        graph = make_graph()
        payload = relationship_editor_payload(graph, self_bot_id="bot_a")

        self.assertEqual(payload["self_bot_id"], "bot_a")
        self.assertEqual(
            [item["bot_id"] for item in payload["bots"]],
            ["bot_a", "bot_b"],
        )
        self.assertEqual(payload["bots"][0]["account_id"], "10001")
        self.assertNotIn("persona_id", payload["bots"][0])
        self.assertNotIn("provider_id", payload["bots"][0])
        self.assertEqual(payload["relations"][0]["__template_key"], "relation")

    def test_users_are_participants_but_never_callable_bots(self):
        user = BotNode(
            "owner",
            "主人",
            "90001",
            node_type="user",
            aliases=("管理员",),
        )
        graph = BotGraph(
            make_graph().bots,
            [Relation("bot_a", "owner", relation_type="朋友")],
            users=[user],
        )

        self.assertIsNone(graph.get_bot("owner"))
        self.assertIsNone(graph.get_by_account("90001"))
        self.assertEqual(graph.get_user_by_account("90001").bot_id, "owner")
        self.assertEqual(graph.resolve_participant("管理员").bot_id, "owner")
        self.assertNotIn("owner", [item.bot_id for item in graph.accessible_from("bot_a")])
        self.assertEqual(graph.get_relation("bot_a", "owner").relation_type, "朋友")

    def test_node_editor_normalizes_bot_and_ordinary_user_templates(self):
        bots, users, graph = normalize_node_entries(
            [
                {
                    "bot_id": "bot_a",
                    "display_name": "小A",
                    "account_id": "10001",
                    "platform_id": "onebot_main",
                    "persona_id": "persona_a",
                }
            ],
            [
                {
                    "user_id": "owner",
                    "display_name": "主人",
                    "account_id": "90001",
                }
            ],
        )

        self.assertEqual(bots[0]["__template_key"], "bot")
        self.assertEqual(bots[0]["platform_id"], "onebot_main")
        self.assertEqual(users[0]["__template_key"], "user")
        self.assertEqual(graph.get_user("owner").display_name, "主人")
        relation = normalize_relation_entries(
            [{"source_bot_id": "bot_a", "target_bot_id": "owner"}],
            graph.bots,
            graph.users,
        )
        self.assertEqual(relation[0]["target_bot_id"], "owner")

    def test_node_editor_rejects_duplicate_identity_across_bot_and_user(self):
        with self.assertRaises(RelationshipEditorError):
            normalize_node_entries(
                [{"bot_id": "bot_a", "display_name": "同名", "account_id": "1"}],
                [{"user_id": "user_a", "display_name": "同名", "account_id": "2"}],
            )

    def test_page_relations_are_normalized_and_numeric_values_are_bounded(self):
        normalized = normalize_relation_entries(
            [
                {
                    "source_bot_id": "bot_a",
                    "target_bot_id": "bot_b",
                    "relation_type": "friend",
                    "allow_ask": "false",
                    "trust": 9,
                    "affinity": -9,
                    "romantic_interest": 2,
                    "interject_priority": 0,
                    "allow_interject": True,
                    "address_as": "小B",
                    "address_options": ["小B", "B同学", "小B"],
                    "origin": "system_prompt",
                    "confidence": 0.1,
                }
            ],
            make_graph().bots,
        )

        row = normalized[0]
        self.assertFalse(row["allow_ask"])
        self.assertTrue(row["allow_interject"])
        self.assertEqual(row["trust"], 1.0)
        self.assertEqual(row["affinity"], -1.0)
        self.assertEqual(row["romantic_interest"], 1.0)
        self.assertEqual(row["interject_priority"], 0.01)
        self.assertEqual(row["address_as"], "小B")
        self.assertEqual(row["address_options"], ["小B", "B同学"])
        self.assertNotIn("origin", row)
        self.assertNotIn("confidence", row)

    def test_page_rejects_unknown_self_and_duplicate_relations(self):
        bots = make_graph().bots
        invalid_sets = (
            [{"source_bot_id": "missing", "target_bot_id": "bot_b"}],
            [{"source_bot_id": "bot_a", "target_bot_id": "bot_a"}],
            [
                {"source_bot_id": "bot_a", "target_bot_id": "bot_b"},
                {"source_bot_id": "bot_a", "target_bot_id": "bot_b"},
            ],
        )
        for rows in invalid_sets:
            with self.subTest(rows=rows):
                with self.assertRaises(RelationshipEditorError):
                    normalize_relation_entries(rows, bots)

    def test_same_direction_can_have_global_and_group_specific_rows(self):
        normalized = normalize_relation_entries(
            [
                {
                    "source_bot_id": "bot_a",
                    "target_bot_id": "bot_b",
                    "group_id": "",
                    "relation_type": "朋友",
                },
                {
                    "source_bot_id": "bot_a",
                    "target_bot_id": "bot_b",
                    "group_id": "group-42",
                    "relation_type": "竞争对手",
                },
            ],
            make_graph().bots,
        )
        self.assertEqual([row["group_id"] for row in normalized], ["", "group-42"])

    def test_page_rejects_non_list_and_overlong_text(self):
        bots = make_graph().bots
        with self.assertRaises(RelationshipEditorError):
            normalize_relation_entries({}, bots)
        with self.assertRaises(RelationshipEditorError):
            normalize_relation_entries(
                [
                    {
                        "source_bot_id": "bot_a",
                        "target_bot_id": "bot_b",
                        "tone": "x" * 501,
                    }
                ],
                bots,
            )


class RelationshipExtractionTests(unittest.TestCase):
    def setUp(self):
        self.source = BotNode(
            "bot_a", "小A", "10001", aliases=("阿A",)
        )
        self.targets = (
            BotNode("bot_b", "小B", "10002", aliases=("研究员B",)),
            BotNode("bot_c", "小C", "10003"),
        )

    def test_direction_and_alias_are_mapped_into_table_row(self):
        result = parse_relationship_extraction(
            """
            {
              "relations": [{
                "source_bot_id": "bot_c",
                "target_name": "研究员B",
                "relation_type": "青梅竹马",
                "address_as": "小笨蛋",
                "trust": 0.9,
                "familiarity": 0.95,
                "affinity": 0.8,
                "romantic_interest": 0.7,
                "tone": "熟稔、爱打趣",
                "confidence": 0.91,
                "evidence": "明确写出两人从小认识"
              }],
              "unresolved_mentions": []
            }
            """,
            source=self.source,
            targets=self.targets,
            prompt_hash="hash-a",
        )
        self.assertEqual(len(result.relations), 1)
        relation = result.relations[0]
        self.assertEqual(relation.source_bot_id, "bot_a")
        self.assertEqual(relation.target_bot_id, "bot_b")
        self.assertEqual(relation.relation_type, "青梅竹马")
        self.assertEqual(relation.address_as, "小笨蛋")
        self.assertEqual(relation.origin, "system_prompt")
        self.assertFalse(relation.allow_ask)
        self.assertFalse(relation.allow_flirt)
        self.assertFalse(relation.allow_interject)

    def test_unknown_and_low_confidence_names_are_not_guessed(self):
        result = parse_relationship_extraction(
            """
            {"relations": [
              {"target_bot_id": "小D", "confidence": 0.9},
              {"target_bot_id": "bot_c", "confidence": 0.2}
            ]}
            """,
            source=self.source,
            targets=self.targets,
            prompt_hash="hash-a",
            confidence_threshold=0.55,
        )
        self.assertEqual(result.relations, ())
        self.assertTrue(any("小D" in item for item in result.unresolved_mentions))
        self.assertTrue(any("bot_c" in item for item in result.unresolved_mentions))

    def test_explicit_prompt_block_skips_free_form_discovery(self):
        prompt = """
        你是小A。
        <botmesh_relations>
        [{"target_bot_id":"bot_b","relation_type":"搭档","confidence":1}]
        </botmesh_relations>
        """
        payload = explicit_relationship_payload(prompt)
        self.assertIsNotNone(payload)
        result = parse_relationship_extraction(
            payload or "",
            source=self.source,
            targets=self.targets,
            prompt_hash=hash_system_prompt(prompt),
        )
        self.assertEqual(result.relations[0].target_bot_id, "bot_b")

    def test_extraction_prompt_fixes_source_and_lists_target_ids(self):
        prompt = build_relationship_extraction_prompt(
            self.source, self.targets, "你把研究员B当成很可靠的朋友。"
        )
        self.assertIn("主体固定为 小A（bot_a）", prompt)
        self.assertIn("bot_id=bot_b", prompt)
        self.assertIn("研究员B", prompt)


class DynamicRelationshipAndObserverTests(unittest.TestCase):
    def test_relationship_delta_is_confidence_gated_and_step_limited(self):
        accepted = parse_relationship_delta(
            """
            {"active_mode":"安慰","trust_delta":1,"familiarity_delta":0.3,
             "affinity_delta":-1,"romantic_interest_delta":0.2,
             "confidence":0.9,"reason":"对方认真提供了帮助"}
            """,
            max_step=0.05,
            confidence_threshold=0.65,
        )
        rejected = parse_relationship_delta(
            '{"active_mode":"紧张","trust_delta":-0.1,"confidence":0.2}',
            max_step=0.05,
            confidence_threshold=0.65,
        )
        self.assertTrue(accepted.accepted)
        self.assertEqual(accepted.trust_delta, 0.05)
        self.assertEqual(accepted.affinity_delta, -0.05)
        self.assertFalse(rejected.accepted)
        self.assertEqual(rejected.trust_delta, 0.0)

    def test_effective_relation_uses_dynamic_state_but_preserves_permissions(self):
        base = Relation(
            "bot_a",
            "bot_b",
            address_as="小B",
            address_options=("小B", "B同学", "搭档"),
            trust=0.8,
            familiarity=0.4,
            affinity=0.2,
            romantic_interest=0.1,
            allow_ask=True,
            allow_flirt=False,
            allow_interject=True,
        )
        state = RelationshipState(
            "bot_a",
            "bot_b",
            active_mode="玩笑",
            address_as_override="搭档",
            trust_delta=0.4,
            familiarity_delta=0.2,
            affinity_delta=-0.1,
            romantic_interest_delta=0.3,
        )
        current = effective_relation(base, state)
        self.assertEqual(current.trust, 1.0)
        self.assertAlmostEqual(current.familiarity, 0.6)
        self.assertAlmostEqual(current.affinity, 0.1)
        self.assertAlmostEqual(current.romantic_interest, 0.4)
        self.assertTrue(current.allow_ask)
        self.assertTrue(current.allow_interject)
        self.assertFalse(current.allow_flirt)
        self.assertIn("玩笑", current.tone)
        self.assertEqual(current.address_as, "搭档")
        self.assertEqual(current.address_options, ("小B", "B同学", "搭档"))

    def test_relationship_delta_parses_dynamic_address_actions(self):
        selected = parse_relationship_delta(
            '{"active_mode":"亲近","address_as":" 搭档 ","confidence":0.9}',
        )
        kept = parse_relationship_delta(
            '{"active_mode":"常态","address_as":null,"confidence":0.9}',
        )
        reset = parse_relationship_delta(
            '{"active_mode":"常态","address_as":"","confidence":0.9}',
        )

        self.assertEqual(selected.address_as, "搭档")
        self.assertIsNone(kept.address_as)
        self.assertEqual(reset.address_as, "")
        with self.assertRaises(SocialStateError):
            parse_relationship_delta(
                '{"address_as":["错误"],"confidence":0.9}',
            )

    def test_observer_decision_requires_action_score_and_message(self):
        speak = parse_observer_decision(
            '{"action":"speak","score":0.9,"message":"我补充一点。","reason":"相关"}',
            min_score=0.78,
        )
        silent = parse_observer_decision(
            '{"action":"speak","score":0.3,"message":"抢话","reason":"不够相关"}',
            min_score=0.78,
        )
        self.assertTrue(speak.should_speak)
        self.assertEqual(speak.message, "我补充一点。")
        self.assertFalse(silent.should_speak)
        self.assertEqual(silent.message, "")

    def test_exactly_one_observer_is_selected_for_same_event(self):
        relations = [
            Relation("bot_b", "bot_a", allow_interject=True, interject_priority=1),
            Relation("bot_c", "bot_a", allow_interject=True, interject_priority=2),
            Relation("bot_d", "bot_a", allow_interject=False),
        ]
        first = select_observer(relations, target_bot_id="bot_a", event_key="m-1")
        second = select_observer(relations, target_bot_id="bot_a", event_key="m-1")
        self.assertIn(first, {"bot_b", "bot_c"})
        self.assertEqual(first, second)


class StoreTests(unittest.TestCase):
    def test_audit_indexes_exist_and_old_interactions_are_pruned(self):
        codec = ProtocolCodec("shared-secret-with-at-least-32-bytes")
        request = codec.new_request("bot_a", "bot_b", now=1)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "botmesh.sqlite3"
            store = InteractionStore(path)
            store.record_outgoing(request, "旧问题")
            connection = sqlite3.connect(path)
            connection.execute(
                "UPDATE interactions SET updated_at=1 WHERE interaction_id=?",
                (request.interaction_id,),
            )
            index_names = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='index'"
                ).fetchall()
            }
            connection.commit()
            connection.close()
            deleted = store.prune(older_than=2)
            self.assertEqual(deleted["interactions"], 1)
            self.assertEqual(store.recent(), [])
            self.assertIn("idx_observer_rate_source", index_names)

    def test_duplicate_event_is_only_accepted_once(self):
        codec = ProtocolCodec("shared-secret-with-at-least-32-bytes")
        request = codec.new_request("bot_a", "bot_b", now=1_700_000_000)
        with tempfile.TemporaryDirectory() as temp_dir:
            store = InteractionStore(Path(temp_dir) / "botmesh.sqlite3")
            self.assertTrue(store.accept_event(request, "bot_b"))
            self.assertFalse(store.accept_event(request, "bot_b"))
            store.set_question(request.interaction_id, "问题")
            store.complete(request.interaction_id, "回答")
            recent = store.recent(1)
            self.assertEqual(recent[0]["status"], "replied")
            self.assertEqual(recent[0]["answer"], "回答")

    def test_only_a_sent_request_can_accept_b_reply(self):
        codec = ProtocolCodec("shared-secret-with-at-least-32-bytes")
        request = codec.new_request("bot_a", "bot_b", now=1_700_000_000)
        request_delivery = build_request_delivery(
            make_graph(), codec, request, "问题"
        )
        reply_delivery = build_reply_delivery(
            make_graph(), codec, request_delivery.envelope, "回答", now=1_700_000_001
        )
        unrelated = codec.new_request("bot_a", "bot_b", now=1_700_000_002)
        unrelated_reply = build_reply_delivery(
            make_graph(), codec, unrelated, "无缘由回复", now=1_700_000_003
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            store = InteractionStore(Path(temp_dir) / "botmesh.sqlite3")
            store.record_outgoing(request_delivery.envelope, "问题")
            self.assertTrue(
                store.expects_reply(reply_delivery.envelope, "bot_a")
            )
            self.assertFalse(
                store.expects_reply(unrelated_reply.envelope, "bot_a")
            )

    def test_inferred_relationship_table_is_replaced_per_source(self):
        first = Relation(
            source_bot_id="bot_a",
            target_bot_id="bot_b",
            relation_type="朋友",
            trust=0.8,
            familiarity=0.9,
            affinity=0.7,
            romantic_interest=0.2,
            origin="system_prompt",
            confidence=0.9,
            evidence="明确称为朋友",
            prompt_hash="hash-1",
        )
        second = Relation(
            source_bot_id="bot_a",
            target_bot_id="bot_c",
            relation_type="同事",
            origin="system_prompt",
            confidence=0.8,
            prompt_hash="hash-2",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            store = InteractionStore(Path(temp_dir) / "botmesh.sqlite3")
            store.replace_inferred_relations(
                "bot_a", "hash-1", [first], ["小D：无法映射"]
            )
            self.assertEqual(store.inferred_prompt_hash("bot_a"), "hash-1")
            loaded = store.load_inferred_relations(inferred_allow_ask=True)
            self.assertEqual([item.target_bot_id for item in loaded], ["bot_b"])
            self.assertTrue(loaded[0].allow_ask)
            self.assertFalse(loaded[0].share_context)
            self.assertFalse(loaded[0].allow_flirt)

            store.replace_inferred_relations("bot_a", "hash-2", [second])
            loaded = store.load_inferred_relations()
            self.assertEqual([item.target_bot_id for item in loaded], ["bot_c"])

    def test_existing_v01_database_is_migrated_without_losing_interactions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "botmesh.sqlite3"
            connection = sqlite3.connect(path)
            connection.execute(
                """
                CREATE TABLE interactions (
                    interaction_id TEXT PRIMARY KEY,
                    source_bot_id TEXT NOT NULL,
                    target_bot_id TEXT NOT NULL,
                    question TEXT NOT NULL DEFAULT '',
                    answer TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    depth INTEGER NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    error TEXT NOT NULL DEFAULT ''
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE interaction_events (
                    interaction_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    receiver_bot_id TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    PRIMARY KEY (interaction_id, kind, receiver_bot_id)
                )
                """
            )
            connection.execute(
                """
                INSERT INTO interactions (
                    interaction_id, source_bot_id, target_bot_id, question,
                    status, depth, created_at, updated_at
                ) VALUES ('old-id', 'bot_a', 'bot_b', '旧问题', 'sent', 0, 1, 1)
                """
            )
            connection.commit()
            connection.close()

            store = InteractionStore(path)
            self.assertEqual(store.recent(1)[0]["interaction_id"], "old-id")
            self.assertEqual(store.load_inferred_relations(), [])

    def test_legacy_global_relationship_reset_does_not_resurrect_on_restart(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "botmesh.sqlite3"
            store = InteractionStore(path)
            del store
            connection = sqlite3.connect(path)
            connection.execute(
                """
                INSERT INTO relationship_state (
                    source_bot_id, target_bot_id, active_mode, trust_delta,
                    familiarity_delta, affinity_delta,
                    romantic_interest_delta, last_reason, version, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "bot_a",
                    "bot_b",
                    "旧模式",
                    0.1,
                    0.0,
                    0.2,
                    0.0,
                    "旧数据",
                    1,
                    1,
                ),
            )
            connection.commit()
            connection.close()

            migrated = InteractionStore(path)
            self.assertIsNotNone(
                migrated.get_relationship_state("bot_a", "bot_b")
            )
            self.assertTrue(
                migrated.reset_relationship_state("bot_a", "bot_b")
            )
            reopened = InteractionStore(path)
            self.assertIsNone(
                reopened.get_relationship_state("bot_a", "bot_b")
            )

    def test_existing_scoped_state_is_migrated_with_dynamic_address_columns(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "botmesh.sqlite3"
            connection = sqlite3.connect(path)
            connection.execute(
                """
                CREATE TABLE relationship_state_scoped (
                    source_bot_id TEXT NOT NULL,
                    target_bot_id TEXT NOT NULL,
                    group_id TEXT NOT NULL DEFAULT '',
                    active_mode TEXT NOT NULL DEFAULT '',
                    trust_delta REAL NOT NULL DEFAULT 0,
                    familiarity_delta REAL NOT NULL DEFAULT 0,
                    affinity_delta REAL NOT NULL DEFAULT 0,
                    romantic_interest_delta REAL NOT NULL DEFAULT 0,
                    last_reason TEXT NOT NULL DEFAULT '',
                    version INTEGER NOT NULL DEFAULT 0,
                    updated_at INTEGER NOT NULL,
                    PRIMARY KEY (source_bot_id, target_bot_id, group_id)
                )
                """
            )
            connection.execute(
                """
                INSERT INTO relationship_state_scoped (
                    source_bot_id, target_bot_id, group_id, active_mode,
                    trust_delta, updated_at
                ) VALUES ('bot_a', 'bot_b', 'main', '安慰', 0.1, 1)
                """
            )
            connection.commit()
            connection.close()

            store = InteractionStore(path)
            state = store.get_relationship_state("bot_a", "bot_b", "main")
            self.assertEqual(state.active_mode, "安慰")
            self.assertEqual(state.address_as_override, "")
            self.assertAlmostEqual(state.trust_delta, 0.1)

    def test_relationship_delta_is_persistent_and_event_is_idempotent(self):
        delta = RelationshipDelta(
            active_mode="安慰",
            address_as="搭档",
            trust_delta=0.05,
            familiarity_delta=0.02,
            affinity_delta=0.04,
            confidence=0.9,
            reason="一次有效支持",
            accepted=True,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            store = InteractionStore(Path(temp_dir) / "botmesh.sqlite3")
            self.assertTrue(
                store.apply_relationship_delta(
                    "bot_a",
                    "bot_b",
                    event_id="evt-1",
                    event_kind="reply_received",
                    context="谢谢你认真帮我",
                    delta=delta,
                )
            )
            self.assertFalse(
                store.apply_relationship_delta(
                    "bot_a",
                    "bot_b",
                    event_id="evt-1",
                    event_kind="reply_received",
                    context="重复投递",
                    delta=delta,
                )
            )
            state = store.get_relationship_state("bot_a", "bot_b")
            self.assertIsNotNone(state)
            assert state is not None
            self.assertEqual(state.active_mode, "安慰")
            self.assertEqual(state.address_as_override, "搭档")
            self.assertEqual(state.version, 1)
            self.assertAlmostEqual(state.trust_delta, 0.05)
            overrides = store.relationship_address_overrides()
            self.assertEqual(overrides[0]["address_as_override"], "搭档")
            self.assertTrue(
                store.clear_relationship_address_override("bot_a", "bot_b")
            )
            retained = store.get_relationship_state("bot_a", "bot_b")
            self.assertEqual(retained.address_as_override, "")
            self.assertAlmostEqual(retained.trust_delta, 0.05)
            self.assertTrue(store.reset_relationship_state("bot_a", "bot_b"))
            self.assertIsNone(store.get_relationship_state("bot_a", "bot_b"))
            self.assertFalse(store.reset_relationship_state("bot_a", "bot_b"))

    def test_dynamic_relationship_state_is_independent_per_group(self):
        first = RelationshipDelta(
            active_mode="亲近",
            affinity_delta=0.08,
            confidence=0.9,
            reason="群一互动",
            accepted=True,
        )
        second = RelationshipDelta(
            active_mode="克制",
            affinity_delta=-0.03,
            confidence=0.9,
            reason="群二互动",
            accepted=True,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            store = InteractionStore(Path(temp_dir) / "botmesh.sqlite3")
            self.assertTrue(
                store.apply_relationship_delta(
                    "bot_a",
                    "bot_b",
                    group_id="group-1",
                    event_id="group-event-1",
                    event_kind="reply_received",
                    context="群一",
                    delta=first,
                )
            )
            self.assertTrue(
                store.apply_relationship_delta(
                    "bot_a",
                    "bot_b",
                    group_id="group-2",
                    event_id="group-event-2",
                    event_kind="reply_received",
                    context="群二",
                    delta=second,
                )
            )

            group_one = store.get_relationship_state(
                "bot_a", "bot_b", "group-1"
            )
            group_two = store.get_relationship_state(
                "bot_a", "bot_b", "group-2"
            )
            self.assertEqual(group_one.active_mode, "亲近")
            self.assertAlmostEqual(group_one.affinity_delta, 0.08)
            self.assertEqual(group_two.active_mode, "克制")
            self.assertAlmostEqual(group_two.affinity_delta, -0.03)
            self.assertIsNone(store.get_relationship_state("bot_a", "bot_b"))
            self.assertTrue(
                store.reset_relationship_state("bot_a", "bot_b", "group-1")
            )
            self.assertIsNone(
                store.get_relationship_state("bot_a", "bot_b", "group-1")
            )
            self.assertIsNotNone(
                store.get_relationship_state("bot_a", "bot_b", "group-2")
            )

    def test_observer_rate_limit_audit_is_persistent(self):
        codec = ProtocolCodec("shared-secret-with-at-least-32-bytes")
        observation = codec.new_observation("bot_b", "bot_a")
        with tempfile.TemporaryDirectory() as temp_dir:
            store = InteractionStore(Path(temp_dir) / "botmesh.sqlite3")
            store.record_observer_interjection(
                observation,
                direction="outgoing",
                message="补充一句",
                session_id="aiocqhttp:GroupMessage:42",
                origin_user_id="90000",
                reason="高度相关",
            )
            last, count = store.observer_rate_status(
                "bot_b",
                "bot_a",
                session_id="aiocqhttp:GroupMessage:42",
                since=0,
            )
            self.assertGreater(last, 0)
            self.assertEqual(count, 1)
            recent = store.recent_observer_interjections(1)
            self.assertEqual(recent[0]["source_bot_id"], "bot_b")
            self.assertEqual(recent[0]["target_bot_id"], "bot_a")


if __name__ == "__main__":
    unittest.main()
