from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
import tempfile
import time
import types
import unittest
from enum import Enum
from pathlib import Path


class _Logger:
    def __getattr__(self, _name):
        return lambda *_args, **_kwargs: None


def _decorator(*_args, **_kwargs):
    return lambda function: function


def _command_group(_name):
    def decorate(function):
        function.command = lambda *_args, **_kwargs: _decorator()
        return function

    return decorate


class _Star:
    def __init__(self, context):
        self.context = context


class _Context:
    pass


class _AstrMessageEvent:
    pass


class _MessageChain:
    def __init__(self, chain=None):
        self.chain = list(chain or [])


class _MessageType(Enum):
    GROUP_MESSAGE = "GroupMessage"
    FRIEND_MESSAGE = "FriendMessage"


class _MessageSession:
    def __init__(self, platform_name, message_type, session_id):
        self.platform_name = platform_name
        self.platform_id = platform_name
        self.message_type = message_type
        self.session_id = session_id

    def __str__(self):
        return f"{self.platform_id}:{self.message_type.value}:{self.session_id}"


class _Component:
    def __init__(self, *args, **kwargs):
        self.__dict__.update(kwargs)
        if args:
            self.text = args[0]


class _FunctionTool:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class _ToolSet:
    def __init__(self, tools=None):
        self.tools = list(tools or [])


def _install_astrbot_stubs() -> None:
    astrbot = types.ModuleType("astrbot")
    astrbot.__path__ = []
    api = types.ModuleType("astrbot.api")
    api.__path__ = []
    api.AstrBotConfig = dict
    api.FunctionTool = _FunctionTool
    api.ToolSet = _ToolSet
    api.logger = _Logger()

    components = types.ModuleType("astrbot.api.message_components")
    components.At = _Component
    components.Plain = _Component

    filter_api = types.SimpleNamespace(
        llm_tool=_decorator,
        command_group=_command_group,
        permission_type=_decorator,
        event_message_type=_decorator,
        regex=_decorator,
        on_llm_request=_decorator,
        PermissionType=types.SimpleNamespace(ADMIN="admin"),
        EventMessageType=types.SimpleNamespace(GROUP_MESSAGE="group"),
    )
    event = types.ModuleType("astrbot.api.event")
    event.AstrMessageEvent = _AstrMessageEvent
    event.MessageChain = _MessageChain
    event.filter = filter_api

    star = types.ModuleType("astrbot.api.star")
    star.Context = _Context
    star.Star = _Star

    web = types.ModuleType("astrbot.api.web")
    web.request = types.SimpleNamespace()
    web.json_response = lambda payload: payload
    web.error_response = lambda message, status_code=400: {
        "status": "error",
        "message": message,
        "status_code": status_code,
    }

    core = types.ModuleType("astrbot.core")
    core.__path__ = []
    platform_module = types.ModuleType("astrbot.core.platform")
    platform_module.__path__ = []
    message_session_module = types.ModuleType("astrbot.core.platform.message_session")
    message_session_module.MessageSession = _MessageSession
    message_type_module = types.ModuleType("astrbot.core.platform.message_type")
    message_type_module.MessageType = _MessageType
    utils = types.ModuleType("astrbot.core.utils")
    utils.__path__ = []
    path_module = types.ModuleType("astrbot.core.utils.astrbot_path")
    path_module.get_astrbot_data_path = tempfile.gettempdir

    astrbot.api = api
    sys.modules.update(
        {
            "astrbot": astrbot,
            "astrbot.api": api,
            "astrbot.api.message_components": components,
            "astrbot.api.event": event,
            "astrbot.api.star": star,
            "astrbot.api.web": web,
            "astrbot.core": core,
            "astrbot.core.platform": platform_module,
            "astrbot.core.platform.message_session": message_session_module,
            "astrbot.core.platform.message_type": message_type_module,
            "astrbot.core.utils": utils,
            "astrbot.core.utils.astrbot_path": path_module,
        }
    )


_install_astrbot_stubs()

from astrbot_plugin_botmesh import main as plugin_main
from astrbot_plugin_botmesh import integration as botmesh_integration
from astrbot_plugin_botmesh.core import RelationshipDelta


def _create_chat_history_db(path: Path, rows: list[tuple]) -> list[int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            CREATE TABLE group_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                umo TEXT NOT NULL,
                ts REAL NOT NULL,
                sender_id TEXT NOT NULL DEFAULT '',
                sender_name TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL,
                message_id TEXT
            )
            """
        )
        ids = []
        for row in rows:
            cursor = connection.execute(
                "INSERT INTO group_messages(umo, ts, sender_id, sender_name, content, message_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                row,
            )
            ids.append(int(cursor.lastrowid))
        connection.commit()
        return ids
    finally:
        connection.close()


class _Config(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.saved = 0

    def save_config(self):
        self.saved += 1


class _Meta:
    def __init__(self, platform_id="onebot_main", name="aiocqhttp"):
        self.id = platform_id
        self.name = name


class _Client:
    calls = 0

    async def call_action(self, *, action, **_kwargs):
        type(self).calls += 1
        if action != "get_login_info":
            raise AssertionError(action)
        return {"user_id": 10001, "nickname": "小A"}


class _Platform:
    status = types.SimpleNamespace(value="running")

    def __init__(self, platform_id="onebot_main", name="aiocqhttp"):
        self._meta = _Meta(platform_id, name)
        self._session_last_message_id = {}
        self._session_scene = {}

    def meta(self):
        return self._meta

    def get_client(self):
        return _Client()

    def remember_session_scene(self, session_id, scene):
        self._session_scene[session_id] = scene


class _PlatformManager:
    platforms_config = [
        {"id": "onebot_main", "type": "aiocqhttp", "enable": True}
    ]

    def __init__(self):
        self.instances = [_Platform()]

    def get_insts(self):
        return list(self.instances)


class _PersonaManager:
    personas_v3 = [{"name": "persona_a"}]

    async def get_all_personas(self):
        return []

    def get_persona(self, persona_id):
        if persona_id == "persona_a":
            return {"system_prompt": "你是擅长资料检索的小A。"}
        return None


class _ProviderManager:
    providers_config = [
        {"id": "provider_a", "type": "openai_chat_completion", "model": "gpt"}
    ]


class _ConversationManager:
    def __init__(self):
        self.current = {}
        self.histories = {}

    async def get_curr_conversation_id(self, origin):
        return self.current.get(origin)

    async def new_conversation(self, origin, platform_id=None):
        conversation_id = f"conversation-{len(self.current) + 1}"
        self.current[origin] = conversation_id
        self.histories[conversation_id] = []
        return conversation_id

    async def get_conversation(self, _origin, conversation_id):
        return types.SimpleNamespace(
            cid=conversation_id,
            history=json.dumps(
                self.histories.get(conversation_id, []),
                ensure_ascii=False,
            ),
        )

    async def update_conversation(
        self,
        _origin,
        conversation_id,
        history=None,
        **_kwargs,
    ):
        self.histories[conversation_id] = list(history or [])


class _PluginContext:
    def __init__(self):
        self.platform_manager = _PlatformManager()
        self.persona_manager = _PersonaManager()
        self.provider_manager = _ProviderManager()
        self.conversation_manager = _ConversationManager()
        self.routes = []
        self.last_llm_call = None
        self.last_agent_call = None
        self.proactive_sent = []
        self.agent_completion_text = "这是目标 Bot Agent 的真实回答。"
        self.completion_text = (
            '{"bots":[{"bot_id":"bot_a","description":"检索助手",'
            '"persona_id":"persona_a","provider_id":"provider_a",'
            '"capabilities":["资料检索"]}],"users":[],"relations":[],"notes":[]}'
        )

    def register_web_api(self, route, handler, methods, description):
        self.routes.append((route, handler, methods, description))

    async def llm_generate(self, **kwargs):
        self.last_llm_call = kwargs
        return types.SimpleNamespace(
            completion_text=self.completion_text
        )

    async def tool_loop_agent(self, **kwargs):
        self.last_agent_call = kwargs
        return types.SimpleNamespace(completion_text=self.agent_completion_text)

    async def send_message(self, session, message):
        platform = next(
            (
                item
                for item in self.platform_manager.get_insts()
                if item.meta().id == session.platform_id
            ),
            None,
        )
        if platform is None:
            return False
        normalized_name = "".join(
            ch for ch in platform.meta().name.casefold() if ch.isalnum()
        )
        if normalized_name == "qqofficial":
            if (
                session.message_type is not _MessageType.GROUP_MESSAGE
                or platform._session_scene.get(session.session_id) != "group"
            ):
                return True
            platform._session_last_message_id[session.session_id] = (
                f"message-{len(self.proactive_sent) + 1}"
            )
        stored_message = getattr(message, "chain", message)
        self.proactive_sent.append((session, stored_message))
        return True

    async def get_current_chat_provider_id(self, _origin):
        return "provider_a"


class _Event:
    def __init__(self, self_id, platform_id="", extras=None, group_id="", sender_id="90001"):
        self._self_id = self_id
        self._platform_id = platform_id
        self._extras = extras or {}
        self._group_id = group_id
        self._sender_id = sender_id
        self.unified_msg_origin = "aiocqhttp:GroupMessage:42"
        self.session = types.SimpleNamespace(
            platform_name=platform_id or "onebot_main",
            platform_id=platform_id or "onebot_main",
            message_type=types.SimpleNamespace(value="GroupMessage"),
            session_id=group_id or "42",
        )
        self.sent = []
        self.message_str = "测试消息"
        self.stopped = False

    def get_self_id(self):
        return self._self_id

    def get_platform_id(self):
        return self._platform_id

    def get_group_id(self):
        return self._group_id

    def get_extra(self, key):
        return self._extras.get(key)

    def set_extra(self, key, value):
        self._extras[key] = value

    def get_sender_id(self):
        return self._sender_id

    def get_sender_name(self):
        return f"用户{self._sender_id}"

    def get_messages(self):
        return []

    def should_call_llm(self, _value):
        pass

    def stop_event(self):
        self.stopped = True

    def chain_result(self, chain):
        return chain

    async def send(self, result):
        self.sent.append(result)


class Plain:
    def __init__(self, text):
        self.text = text


class At:
    pass


class PluginWorkspaceTests(unittest.IsolatedAsyncioTestCase):
    def make_plugin(self):
        _Client.calls = 0
        config = _Config(
            self_bot_id="",
            shared_secret="",
            bots=[],
            users=[],
            relations=[],
        )
        context = _PluginContext()
        return plugin_main.BotMeshPlugin(context, config), context, config

    async def test_proactive_send_review_preserves_safe_natural_prose(self):
        plugin, _context, _config = self.make_plugin()
        bot = plugin_main.BotNode(
            bot_id="bot_a",
            display_name="小A",
            account_id="10001",
            platform_id="onebot_main",
        )
        system_prompt = plugin._build_proactive_dispatch_system_prompt(
            bot,
            "",
            "你是小A。",
            {},
            None,
        )
        user_prompt = plugin._build_proactive_dispatch_user_prompt(
            trigger={},
            local_history=[],
            persistent_history="",
            recent_topics=[],
            generation_options={},
            target_candidates={},
        )
        render_options = {
            "target_candidates": {},
            "group_id": "",
            "identity_terms": ["莉芙"],
        }

        narrative = plugin._render_proactive_dispatch(
            '{"audience":"group","message":"莉芙的长头发又缠住梳子了。"}',
            **render_options,
        )
        plain_text = plugin._render_proactive_dispatch(
            "刚才忽然想起一件小事，心里有点说不上来的感觉。",
            **render_options,
        )
        clear_addressee = plugin._render_proactive_dispatch(
            '{"audience":"group","message":"莉芙，明天一起出去走走。"}',
            **render_options,
        )
        broken_json = plugin._render_proactive_dispatch(
            '{"audience":"group","message":"不完整"',
            **render_options,
        )

        self.assertEqual(narrative[0], "莉芙的长头发又缠住梳子了。")
        self.assertEqual(narrative[3], "group")
        self.assertEqual(plain_text[0], "刚才忽然想起一件小事，心里有点说不上来的感觉。")
        self.assertEqual(plain_text[3], "plain_text_group")
        self.assertEqual(clear_addressee[3], "group_identity_term_fallback")
        self.assertNotIn("？", clear_addressee[0])
        self.assertEqual(broken_json[3], "malformed_schema_fallback")
        self.assertNotIn("？", broken_json[0])
        self.assertIn("主动发言不要求提问", system_prompt)
        self.assertIn("可以是陈述句或问句", user_prompt)

    async def test_qqofficial_proactive_route_requires_new_delivery_receipt(self):
        plugin, context, _config = self.make_plugin()
        platform = _Platform("qq_main", "qq_official")
        context.platform_manager.instances = [platform]
        bot = types.SimpleNamespace(platform_id="qq_main")

        marker, error = plugin._prepare_proactive_group_route(bot, "GROUP_OPENID")

        self.assertEqual(error, "")
        self.assertIsNotNone(marker)
        self.assertEqual(platform._session_scene["GROUP_OPENID"], "group")
        self.assertEqual(plugin._confirmed_proactive_delivery_id(marker), "")

        platform._session_last_message_id["GROUP_OPENID"] = "message-1"
        self.assertEqual(
            plugin._confirmed_proactive_delivery_id(marker),
            "message-1",
        )

    async def test_qqofficial_proactive_dispatch_uses_native_session(self):
        config = _Config(
            self_bot_id="bot_a",
            shared_secret="test-secret-with-at-least-32-bytes",
            auto_extract_relations=False,
            bots=[
                {
                    "bot_id": "bot_a",
                    "display_name": "小A",
                    "account_id": "10001",
                    "platform_id": "qq_main",
                }
            ],
            users=[],
            relations=[],
            group_bindings=[
                {
                    "group_id": "main_group",
                    "bot_id": "bot_a",
                    "platform_group_id": "GROUP_OPENID",
                }
            ],
            persona_profiles=[
                {
                    "bot_id": "bot_a",
                    "group_id": "main_group",
                    "system_prompt": "小A的群人格",
                }
            ],
        )
        context = _PluginContext()
        platform = _Platform("qq_main", "qq_official")
        context.platform_manager.instances = [platform]
        context.completion_text = (
            '{"audience":"group","message":"今晚想聊点什么？"}'
        )
        plugin = plugin_main.BotMeshPlugin(context, config)

        result = await plugin.dispatch_proactive_topic(
            umo="qq_main:GroupMessage:GROUP_OPENID",
            event=None,
            identity={
                "platform_id": "qq_main",
                "self_id": "10001",
                "group_id": "GROUP_OPENID",
            },
            trigger={"reason": "retry"},
            local_history=[],
            recent_topics=[],
            generation_options={},
        )

        self.assertTrue(result["success"], result)
        session, sent_chain = context.proactive_sent[-1]
        self.assertIsInstance(session, _MessageSession)
        self.assertIs(session.message_type, _MessageType.GROUP_MESSAGE)
        self.assertEqual(platform._session_scene["GROUP_OPENID"], "group")
        self.assertEqual(
            platform._session_last_message_id["GROUP_OPENID"],
            "message-1",
        )
        self.assertEqual(len(sent_chain), 1)

    async def test_memory_key_setter_persists_in_group_persona(self):
        config = _Config(
            self_bot_id="bot_a",
            shared_secret="test-secret-with-at-least-32-bytes",
            bots=[
                {
                    "bot_id": "bot_a",
                    "display_name": "Rev",
                    "account_id": "10001",
                    "platform_id": "onebot_main",
                }
            ],
            users=[],
            relations=[],
            group_scopes=[{"group_id": "soul_swap"}],
            group_bindings=[
                {
                    "group_id": "soul_swap",
                    "bot_id": "bot_a",
                    "platform_group_id": "GROUP_A",
                }
            ],
            persona_profiles=[
                {
                    "bot_id": "bot_a",
                    "group_id": "",
                    "personality_prompt": "全局人格",
                    "memory_key": "莉芙",
                }
            ],
        )
        plugin = plugin_main.BotMeshPlugin(_PluginContext(), config)

        identity = await botmesh_integration.set_memory_key(
            bot_id="bot_a",
            logical_group_id="soul_swap",
            memory_key="蔚来",
        )

        group_row = next(
            row
            for row in config["persona_profiles"]
            if row["bot_id"] == "bot_a" and row["group_id"] == "soul_swap"
        )
        self.assertEqual(group_row["memory_key"], "蔚来")
        self.assertEqual(identity["memory_key"], "蔚来")
        self.assertEqual(config.saved, 1)

    async def test_management_labels_expose_names_for_companion_pages(self):
        config = _Config(
            self_bot_id="bot_a",
            shared_secret="test-secret-with-at-least-32-bytes",
            bots=[
                {
                    "bot_id": "bot_a",
                    "display_name": "小A",
                    "account_id": "10001",
                    "platform_id": "onebot_main",
                }
            ],
            users=[],
            relations=[],
            group_scopes=[{"group_id": "主群"}],
            group_bindings=[
                {
                    "group_id": "主群",
                    "bot_id": "bot_a",
                    "platform_group_id": "A_GROUP_OPENID",
                }
            ],
        )
        plugin = plugin_main.BotMeshPlugin(_PluginContext(), config)

        labels = botmesh_integration.get_management_labels()

        self.assertEqual(labels["bots"]["bot_a"], "小A")
        self.assertEqual(labels["bots"]["10001"], "小A")
        self.assertEqual(labels["bot_ids"]["10001"], "bot_a")
        self.assertEqual(labels["groups"]["主群"], "主群")
        self.assertEqual(labels["scopes"]["botmesh:主群"], "主群")
        raw_scope = "onebot_main:GroupMessage:A_GROUP_OPENID"
        self.assertEqual(labels["scopes"][raw_scope], "主群")
        self.assertEqual(labels["scope_groups"][raw_scope], "主群")
        self.assertEqual(labels, plugin.management_labels())

    async def test_qq_official_never_reuses_another_bot_group_openid(self):
        config = _Config(
            self_bot_id="bot_a",
            shared_secret="test-secret-with-at-least-32-bytes",
            bots=[
                {
                    "bot_id": "bot_a",
                    "display_name": "小A",
                    "account_id": "10001",
                    "platform_id": "onebot_main",
                },
                {
                    "bot_id": "bot_b",
                    "display_name": "小B",
                    "account_id": "10002",
                    "platform_id": "qq_b",
                },
            ],
            users=[],
            relations=[],
            group_scopes=[{"group_id": "主群"}],
            group_bindings=[
                {
                    "group_id": "主群",
                    "bot_id": "bot_a",
                    "platform_group_id": "A_GROUP_OPENID",
                }
            ],
        )
        context = _PluginContext()
        context.platform_manager.instances.append(_Platform("qq_b", "qq_official"))
        plugin = plugin_main.BotMeshPlugin(context, config)
        source = plugin.graph.get_bot("bot_a")
        target = plugin.graph.get_bot("bot_b")
        event = _Event("10001", platform_id="onebot_main", group_id="A_GROUP_OPENID")

        with self.assertRaisesRegex(RuntimeError, "缺少 小B 的 QQ 官方平台群地址"):
            plugin._agent_event_for_target(
                event,
                source=source,
                target=target,
                group_id="主群",
                question="在吗？",
                interaction_id="interaction-1",
                depth=0,
            )

    async def test_workspace_is_fast_and_discovery_is_separate_and_cached(self):
        plugin, context, _config = self.make_plugin()
        payload = await plugin._workspace_payload()

        self.assertTrue(
            any(route.endswith("/workspace") for route, *_rest in context.routes)
        )
        self.assertNotIn("discovered_bots", payload)
        self.assertEqual(_Client.calls, 0)
        self.assertTrue(
            any(route.endswith("/discovery") for route, *_rest in context.routes)
        )
        self.assertTrue(
            any(
                route.endswith("/workspace/field-autofill/start")
                for route, *_rest in context.routes
            )
        )
        self.assertTrue(
            any(
                route.endswith("/workspace/field-autofill/status")
                for route, *_rest in context.routes
            )
        )
        discovered = await plugin._discover_astrbot_bots()
        candidate = discovered[0]
        self.assertEqual(candidate["account_id"], "10001")
        self.assertEqual(candidate["display_name"], "小A")
        self.assertTrue(candidate["can_auto_import"])
        self.assertEqual(payload["persona_profiles"], [])
        self.assertEqual(payload["providers"][0]["id"], "provider_a")
        self.assertEqual(_Client.calls, 1)
        await plugin._discover_astrbot_bots()
        self.assertEqual(_Client.calls, 1)

    async def test_qq_official_placeholder_accounts_are_never_merged(self):
        candidates = [
            {
                "platform_id": "default_1905252075",
                "account_id": "qq_official",
                "can_auto_import": True,
            },
            {
                "platform_id": "default_1903657006",
                "account_id": "qq_official",
                "can_auto_import": True,
            },
        ]

        result = plugin_main.BotMeshPlugin._reconcile_discovered_bots(candidates)

        self.assertNotIn("duplicate_of_platform_id", result[0])
        self.assertNotIn("duplicate_of_platform_id", result[1])

    async def test_real_duplicate_accounts_are_still_merged(self):
        candidates = [
            {
                "platform_id": "platform_a",
                "account_id": "REAL_OPENID",
                "enabled": True,
                "status": "running",
                "can_auto_import": True,
            },
            {
                "platform_id": "platform_b",
                "account_id": "REAL_OPENID",
                "enabled": True,
                "status": "running",
                "can_auto_import": True,
            },
        ]

        result = plugin_main.BotMeshPlugin._reconcile_discovered_bots(candidates)

        duplicates = [row for row in result if row.get("duplicate_of_platform_id")]
        self.assertEqual(len(duplicates), 1)
        self.assertFalse(duplicates[0]["can_auto_import"])

    async def test_placeholder_self_id_is_not_remembered_as_platform_account(self):
        plugin, _context, _config = self.make_plugin()
        event = _Event("qq_official", "default_1905252075")

        plugin._remember_event_platform(event)

        self.assertNotIn("default_1905252075", plugin._observed_platform_accounts)

    async def test_placeholder_platform_candidate_waits_for_real_openid(self):
        plugin, _context, _config = self.make_plugin()
        plugin._observed_platform_accounts["default_1905252075"] = {
            "account_id": "qq_official",
            "display_name": "",
        }

        candidate = await plugin._discover_platform_bot(
            {
                "id": "default_1905252075",
                "type": "qq_official",
                "enable": True,
            },
            None,
        )

        self.assertEqual(candidate["account_id"], "")
        self.assertFalse(candidate["can_auto_import"])

    async def test_discovery_reuses_saved_real_account_when_platform_omits_self_id(self):
        config = _Config(
            self_bot_id="bot_a",
            shared_secret="",
            bots=[
                {
                    "bot_id": "bot_a",
                    "display_name": "小A",
                    "account_id": "REAL_OPENID",
                    "platform_id": "default_1903657006",
                }
            ],
            users=[],
            relations=[],
        )
        plugin = plugin_main.BotMeshPlugin(_PluginContext(), config)

        candidate = await plugin._discover_platform_bot(
            {
                "id": "default_1903657006",
                "type": "qq_official",
                "enable": True,
            },
            None,
        )

        self.assertEqual(candidate["account_id"], "REAL_OPENID")
        self.assertEqual(candidate["existing_bot_id"], "bot_a")
        self.assertEqual(candidate["matched_by"], "platform_id")
        self.assertTrue(candidate["can_auto_import"])

    async def test_protocol_verification_uses_plain_body_not_rendered_mention(self):
        plugin, _context, _config = self.make_plugin()
        codec = plugin_main.ProtocolCodec("same-secret-with-at-least-32-bytes")
        envelope = codec.new_request("bot_a", "bot_b", now=1_700_000_000)
        body = codec.attach("你怎么看？", envelope)
        event = types.SimpleNamespace(
            message_str=f"@小B {body}",
            get_messages=lambda: [At(), Plain(f"\u200b {body}")],
        )

        protocol_text = plugin._protocol_message_text(event)
        parsed, content = codec.extract(protocol_text)

        self.assertEqual(content, "你怎么看？")
        self.assertEqual(parsed.source_bot_id, "bot_a")

    async def test_all_botmesh_channels_send_plain_body_without_mention_header(self):
        plugin, _context, _config = self.make_plugin()
        chain = plugin._outbound_message_chain("正文")

        self.assertEqual(len(chain), 1)
        self.assertEqual(chain[0].text, "正文")
        self.assertNotIn("<@", chain[0].text)
        self.assertFalse(hasattr(chain[0], "qq"))

    async def test_workspace_save_applies_bot_user_relation_and_event_identity(self):
        plugin, _context, config = self.make_plugin()
        payload = {
            "bots": [
                {
                    "bot_id": "bot_a",
                    "display_name": "小A",
                    "account_id": "10001",
                    "platform_id": "onebot_main",
                }
            ],
            "users": [
                {
                    "user_id": "owner",
                    "display_name": "主人",
                    "account_id": "90001",
                }
            ],
            "persona_profiles": [
                {
                    "bot_id": "bot_a",
                    "group_id": "42",
                    "system_prompt": "群 42 的插件人格",
                }
            ],
            "group_bindings": [
                {
                    "group_id": "42",
                    "bot_id": "bot_a",
                    "platform_group_id": "BOT_A_OPENID",
                }
            ],
            "group_scopes": [{"group_id": "empty_group"}],
            "relations": [
                {
                    "source_bot_id": "bot_a",
                    "target_bot_id": "owner",
                    "relation_type": "friend",
                }
            ],
            "settings": {
                "self_bot_id": "bot_a",
                "shared_secret": "test-secret-with-at-least-32-bytes",
                "persona_reinforcement_prompt": "自定义人格强化规则",
                "natural_speech_prompt": "自定义自然口语规则",
            },
        }
        plugin_main.request = types.SimpleNamespace(json=lambda default={}: payload)

        async def request_json(default={}):
            return payload

        plugin_main.request.json = request_json
        result = await plugin.page_save_workspace()

        self.assertTrue(result["saved"])
        self.assertTrue(result["shared_secret_configured"])
        self.assertEqual(config.saved, 1)
        self.assertEqual(plugin.graph.get_user("owner").display_name, "主人")
        self.assertEqual(plugin.graph.get_relation("bot_a", "owner").relation_type, "friend")
        self.assertEqual(result["persona_profiles"][0]["group_id"], "42")
        self.assertEqual(result["group_bindings"][0]["platform_group_id"], "BOT_A_OPENID")
        self.assertEqual(
            {row["group_id"] for row in result["group_scopes"]},
            {"42", "empty_group"},
        )
        effective_prompt = await plugin._get_persona_prompt(
            plugin.graph.get_bot("bot_a"),
            _Event("10001", "onebot_main", group_id="BOT_A_OPENID"),
        )
        self.assertIn("群 42 的插件人格", effective_prompt)
        self.assertIn("<botmesh_persona_reinforcement>", effective_prompt)
        self.assertIn("<botmesh_natural_speech>", effective_prompt)
        self.assertIn("自定义人格强化规则", effective_prompt)
        self.assertIn("自定义自然口语规则", effective_prompt)
        self.assertEqual(plugin._self_bot_id_for_event(_Event("stale", "onebot_main")), "bot_a")
        self.assertTrue(plugin.codec.is_ready)

    async def test_workspace_save_rejects_weak_shared_secret(self):
        plugin, _context, _config = self.make_plugin()
        payload = {
            "bots": [],
            "users": [],
            "relations": [],
            "settings": {"shared_secret": "too-short", "require_signature": True},
        }

        async def request_json(default={}):
            return payload

        plugin_main.request = types.SimpleNamespace(json=request_json)
        result = await plugin.page_save_workspace()
        self.assertEqual(result["status_code"], 400)
        self.assertIn("32", result["message"])

    async def test_manual_address_library_edit_clears_only_dynamic_selection(self):
        config = _Config(
            self_bot_id="bot_a",
            shared_secret="test-secret-with-at-least-32-bytes",
            auto_extract_relations=False,
            bots=[
                {
                    "bot_id": "bot_a",
                    "display_name": "小A",
                    "account_id": "10001",
                    "platform_id": "onebot_main",
                },
                {
                    "bot_id": "bot_b",
                    "display_name": "小B",
                    "account_id": "10002",
                    "platform_id": "onebot_second",
                },
            ],
            users=[],
            relations=[
                {
                    "source_bot_id": "bot_a",
                    "target_bot_id": "bot_b",
                    "address_as": "小B",
                    "address_options": ["小B", "B同学"],
                    "allow_evolve": True,
                }
            ],
        )
        context = _PluginContext()
        plugin = plugin_main.BotMeshPlugin(context, config)
        state_directory = tempfile.TemporaryDirectory()
        self.addCleanup(state_directory.cleanup)
        plugin.store = plugin_main.InteractionStore(
            Path(state_directory.name) / "botmesh.sqlite3"
        )
        plugin.store.apply_relationship_delta(
            "bot_a",
            "bot_b",
            event_id="manual-review-before",
            event_kind="reply_received",
            context="明确改叫 B同学",
            delta=RelationshipDelta(
                address_as="B同学",
                trust_delta=0.05,
                confidence=0.9,
                accepted=True,
            ),
        )
        payload = {
            "bots": config["bots"],
            "users": [],
            "persona_profiles": [],
            "group_bindings": [],
            "group_scopes": [],
            "relations": [
                {
                    **config["relations"][0],
                    "address_as": "小B",
                    "address_options": ["小B"],
                }
            ],
            "settings": {
                "self_bot_id": "bot_a",
                "shared_secret": "",
            },
        }

        async def request_json(default={}):
            return payload

        plugin_main.request = types.SimpleNamespace(json=request_json)
        result = await plugin.page_save_workspace()

        state = plugin.store.get_relationship_state("bot_a", "bot_b")
        self.assertEqual(state.address_as_override, "")
        self.assertAlmostEqual(state.trust_delta, 0.05)
        self.assertEqual(result["dynamic_address_overrides"], [])
        self.assertEqual(result["relations"][0]["address_options"], ["小B"])

    async def test_autofill_uses_selected_chat_model_and_persona_system_prompt(self):
        plugin, context, config = self.make_plugin()
        payload = {
            "bots": [
                {
                    "bot_id": "bot_a",
                    "display_name": "小A",
                    "account_id": "10001",
                    "platform_id": "onebot_main",
                    "description": "",
                    "capabilities": [],
                    "aliases": [],
                }
            ],
            "users": [],
            "persona_profiles": [
                {
                    "bot_id": "bot_a",
                    "group_id": "",
                    "system_prompt": "你是 BotMesh 管理的资料检索小A。",
                }
            ],
            "relations": [],
            "provider_id": "provider_a",
            "instruction": "优先填写能力",
        }

        async def request_json(default={}):
            return payload

        plugin_main.request = types.SimpleNamespace(json=request_json)
        result = await plugin.page_autofill_workspace()
        self.assertFalse(result["saved"])
        self.assertEqual(result["bots"][0]["description"], "检索助手")
        self.assertNotIn("persona_id", result["bots"][0])
        self.assertNotIn("provider_id", result["bots"][0])
        self.assertEqual(config.saved, 0)
        self.assertEqual(context.last_llm_call["chat_provider_id"], "provider_a")
        self.assertIn("你是 BotMesh 管理的资料检索小A", context.last_llm_call["prompt"])
        self.assertIn("不同 user_id", context.last_llm_call["system_prompt"])

    async def test_split_field_ai_drafts_personality_and_directional_view_separately(self):
        plugin, context, config = self.make_plugin()
        base_payload = {
            "bots": [
                {
                    "bot_id": "bot_a",
                    "display_name": "小A",
                    "account_id": "10001",
                    "platform_id": "onebot_main",
                },
                {
                    "bot_id": "bot_b",
                    "display_name": "小B",
                    "account_id": "10002",
                    "platform_id": "onebot_second",
                },
            ],
            "users": [],
            "persona_profiles": [
                {
                    "bot_id": "bot_a",
                    "group_id": "",
                    "personality_prompt": "原人格",
                    "worldview_prompt": "必须保留的世界观",
                }
            ],
            "relations": [
                {
                    "source_bot_id": "bot_a",
                    "target_bot_id": "bot_b",
                    "group_id": "",
                    "relation_type": "friend",
                    "allow_ask": True,
                    "share_context": True,
                }
            ],
            "provider_id": "provider_a",
            "group_id": "",
            "instruction": "人格更坚定",
        }
        personality_payload = {
            **base_payload,
            "kind": "personality",
            "bot_ids": ["bot_a"],
            "directions": [],
        }
        context.completion_text = (
            '{"personas":[{"bot_id":"bot_a",'
            '"personality_prompt":"坚定但不武断"}],"notes":[]}'
        )

        async def request_personality(default={}):
            return personality_payload

        plugin_main.request = types.SimpleNamespace(json=request_personality)
        personality_result = await plugin.page_autofill_fields()
        profile = personality_result["persona_profiles"][0]
        self.assertEqual(profile["personality_prompt"], "坚定但不武断")
        self.assertEqual(profile["worldview_prompt"], "必须保留的世界观")
        self.assertIn("分栏设定编辑器", context.last_llm_call["system_prompt"])

        relation_payload = {
            **base_payload,
            "kind": "relation_view",
            "bot_ids": [],
            "directions": [
                {"source_bot_id": "bot_a", "target_bot_id": "bot_b"}
            ],
            "instruction": "写清欣赏与戒备",
        }
        context.completion_text = (
            '{"relations":[{"source_bot_id":"bot_a",'
            '"target_bot_id":"bot_b","view_of_target":"欣赏其执行力，也担心其冒进"}],'
            '"notes":[]}'
        )

        async def request_relation(default={}):
            return relation_payload

        plugin_main.request = types.SimpleNamespace(json=request_relation)
        relation_result = await plugin.page_autofill_fields()
        relation = relation_result["relations"][0]
        self.assertEqual(relation["view_of_target"], "欣赏其执行力，也担心其冒进")
        self.assertTrue(relation["allow_ask"])
        self.assertTrue(relation["share_context"])
        self.assertEqual(config.saved, 0)

    async def test_split_field_background_job_returns_immediately_and_can_be_polled(self):
        plugin, context, _config = self.make_plugin()
        gate = asyncio.Event()
        payload = {
            "kind": "personality",
            "bots": [
                {
                    "bot_id": "bot_a",
                    "display_name": "小A",
                    "account_id": "10001",
                    "platform_id": "onebot_main",
                }
            ],
            "users": [],
            "persona_profiles": [
                {
                    "bot_id": "bot_a",
                    "group_id": "",
                    "personality_prompt": "原人格",
                    "worldview_prompt": "原世界观",
                }
            ],
            "relations": [],
            "provider_id": "provider_a",
            "group_id": "",
            "bot_ids": ["bot_a"],
            "directions": [],
            "instruction": "人格更坚定",
        }

        async def slow_generate(**kwargs):
            context.last_llm_call = kwargs
            await gate.wait()
            return types.SimpleNamespace(
                completion_text=(
                    '{"personas":[{"bot_id":"bot_a",'
                    '"personality_prompt":"后台生成的人格"}],"notes":[]}'
                )
            )

        async def request_start(default={}):
            return payload

        context.llm_generate = slow_generate
        plugin_main.request = types.SimpleNamespace(json=request_start)
        started = await plugin.page_start_autofill_fields()
        task_id = started["task_id"]
        self.assertEqual(started["status"], "queued")
        self.assertIn(task_id, plugin._field_autofill_tasks)

        await asyncio.sleep(0)

        async def request_status(default={}):
            return {"task_id": task_id}

        plugin_main.request = types.SimpleNamespace(json=request_status)
        running = await plugin.page_autofill_fields_status()
        self.assertEqual(running["status"], "running")

        task = plugin._field_autofill_tasks[task_id]
        gate.set()
        await task
        finished = await plugin.page_autofill_fields_status()
        self.assertEqual(finished["status"], "succeeded")
        self.assertEqual(
            finished["result"]["persona_profiles"][0]["personality_prompt"],
            "后台生成的人格",
        )

    async def test_split_field_background_job_preserves_real_failure(self):
        plugin, context, _config = self.make_plugin()
        payload = {
            "kind": "personality",
            "bots": [
                {
                    "bot_id": "bot_a",
                    "display_name": "小A",
                    "account_id": "10001",
                    "platform_id": "onebot_main",
                }
            ],
            "users": [],
            "persona_profiles": [
                {"bot_id": "bot_a", "group_id": "", "system_prompt": "原人格"}
            ],
            "relations": [],
            "provider_id": "provider_a",
            "group_id": "",
            "bot_ids": ["bot_a"],
            "directions": [],
        }

        async def failing_generate(**_kwargs):
            raise RuntimeError("provider connection closed")

        async def request_start(default={}):
            return payload

        context.llm_generate = failing_generate
        plugin_main.request = types.SimpleNamespace(json=request_start)
        started = await plugin.page_start_autofill_fields()
        task_id = started["task_id"]
        task = plugin._field_autofill_tasks[task_id]
        await task

        async def request_status(default={}):
            return {"task_id": task_id}

        plugin_main.request = types.SimpleNamespace(json=request_status)
        failed = await plugin.page_autofill_fields_status()
        self.assertEqual(failed["status"], "failed")
        self.assertIn("provider connection closed", failed["error"])

    async def test_split_field_background_jobs_are_bounded_and_expire(self):
        plugin, context, _config = self.make_plugin()
        gate = asyncio.Event()
        payload = {
            "kind": "personality",
            "bots": [
                {
                    "bot_id": "bot_a",
                    "display_name": "小A",
                    "account_id": "10001",
                    "platform_id": "onebot_main",
                }
            ],
            "users": [],
            "persona_profiles": [
                {"bot_id": "bot_a", "group_id": "", "system_prompt": "原人格"}
            ],
            "relations": [],
            "provider_id": "provider_a",
            "group_id": "",
            "bot_ids": ["bot_a"],
            "directions": [],
        }

        async def slow_generate(**_kwargs):
            await gate.wait()
            return types.SimpleNamespace(
                completion_text=(
                    '{"personas":[{"bot_id":"bot_a",'
                    '"personality_prompt":"新人格"}],"notes":[]}'
                )
            )

        async def request_start(default={}):
            return payload

        context.llm_generate = slow_generate
        plugin_main.request = types.SimpleNamespace(json=request_start)
        started = [
            await plugin.page_start_autofill_fields()
            for _index in range(plugin_main.FIELD_AUTOFILL_MAX_ACTIVE_JOBS)
        ]
        rejected = await plugin.page_start_autofill_fields()
        self.assertEqual(rejected["status_code"], 429)

        for job in plugin._field_autofill_jobs.values():
            job["status"] = "succeeded"
            job["updated_at"] = (
                time.time() - plugin_main.FIELD_AUTOFILL_JOB_TTL_SECONDS - 1
            )
        plugin._prune_field_autofill_jobs()
        self.assertEqual(plugin._field_autofill_jobs, {})

        for task in list(plugin._field_autofill_tasks.values()):
            task.cancel()
        await asyncio.gather(
            *list(plugin._field_autofill_tasks.values()),
            return_exceptions=True,
        )

    async def test_ai_adapts_global_persona_and_group_address_as_draft(self):
        plugin, context, config = self.make_plugin()
        context.completion_text = (
            '{"personas":[{"bot_id":"bot_a","system_prompt":"主群专属人格"}],'
            '"relations":[{"source_bot_id":"bot_a","target_bot_id":"owner",'
            '"address_as":"老师","allow_ask":false,"share_context":false}],"notes":[]}'
        )
        context.provider_manager.providers_config = [
            {"id": "provider_a", "type": "openai_chat_completion", "model": "slow"},
            {"id": "provider_b", "type": "openai_chat_completion", "model": "fast"},
        ]
        provider_calls = []

        async def llm_generate(**kwargs):
            provider_calls.append(kwargs["chat_provider_id"])
            context.last_llm_call = kwargs
            if kwargs["chat_provider_id"] == "provider_a":
                raise TimeoutError("provider timed out")
            return types.SimpleNamespace(completion_text=context.completion_text)

        context.llm_generate = llm_generate
        payload = {
            "bots": [
                {
                    "bot_id": "bot_a",
                    "display_name": "小A",
                    "account_id": "10001",
                    "platform_id": "onebot_main",
                },
                {
                    "bot_id": "bot_b",
                    "display_name": "小B",
                    "account_id": "10002",
                    "platform_id": "onebot_second",
                },
            ],
            "users": [
                {"user_id": "owner", "display_name": "主人", "account_id": "90001"}
            ],
            "group_scopes": [{"group_id": "main"}],
            "group_bindings": [],
            "persona_profiles": [
                {"bot_id": "bot_a", "group_id": "", "system_prompt": "小A全局人格原句"},
                {"bot_id": "bot_b", "group_id": "", "system_prompt": "小B全局人格原句"},
            ],
            "relations": [
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
            "provider_id": "provider_a",
            "group_id": "main",
            "bot_ids": ["bot_a"],
            "instruction": "在主群称呼为老师",
        }

        async def request_json(default={}):
            return payload

        plugin_main.request = types.SimpleNamespace(json=request_json)
        result = await plugin.page_adapt_personas()

        self.assertFalse(result["saved"])
        self.assertEqual(config.saved, 0)
        group_persona = next(row for row in result["persona_profiles"] if row["group_id"] == "main")
        group_relation = next(row for row in result["relations"] if row["group_id"] == "main")
        self.assertEqual(group_persona["system_prompt"], "主群专属人格")
        self.assertEqual(group_relation["address_as"], "老师")
        self.assertTrue(group_relation["allow_ask"])
        self.assertTrue(group_relation["share_context"])
        self.assertEqual(result["updated_addresses"], [{"source_bot_id": "bot_a", "target_bot_id": "owner"}])
        self.assertEqual(provider_calls, ["provider_a", "provider_b"])
        self.assertEqual(result["provider_id"], "provider_b")
        self.assertTrue(any("备用模型 provider_b" in note for note in result["notes"]))
        self.assertEqual(context.last_llm_call["chat_provider_id"], "provider_b")
        self.assertIn("群聊人格编排器", context.last_llm_call["system_prompt"])
        self.assertIn("小A全局人格原句", context.last_llm_call["prompt"])
        self.assertIn("小B全局人格原句", context.last_llm_call["prompt"])
        self.assertIn('"bot_id": "bot_b", "target_for_generation": false', context.last_llm_call["prompt"])

    async def test_observer_decision_receives_persisted_and_recent_group_history(self):
        config = _Config(
            self_bot_id="bot_b",
            shared_secret="test-secret-with-at-least-32-bytes",
            auto_extract_relations=False,
            bots=[
                {
                    "bot_id": "bot_a",
                    "display_name": "小A",
                    "account_id": "10001",
                    "platform_id": "onebot_main",
                },
                {
                    "bot_id": "bot_b",
                    "display_name": "小B",
                    "account_id": "10002",
                    "platform_id": "onebot_second",
                },
            ],
            users=[],
            persona_profiles=[
                {"bot_id": "bot_b", "group_id": "", "system_prompt": "小B人格"}
            ],
            relations=[
                {
                    "source_bot_id": "bot_b",
                    "target_bot_id": "bot_a",
                    "allow_interject": True,
                }
            ],
        )
        context = _PluginContext()
        context.completion_text = (
            '{"action":"silent","score":0.2,"message":"","reason":"继续旁听"}'
        )
        plugin = plugin_main.BotMeshPlugin(context, config)
        origin = "onebot_second:GroupMessage:42"
        history_directory = tempfile.TemporaryDirectory()
        self.addCleanup(history_directory.cleanup)
        history_path = Path(history_directory.name) / "history.sqlite3"
        now = time.time()
        history_row_ids = _create_chat_history_db(
            history_path,
            [
                (origin, now - 90, "90001", "用户甲", "chat_history_context 中的持久化群历史", "b-1"),
                (origin, now - 60, "90002", "用户乙", "刚才群里补充了一个关键约束", "b-2"),
                ("onebot_main:GroupMessage:42", now - 30, "80001", "其他群用户", "不能读到另一个 Bot 的 UMO", "a-1"),
                (origin, now, "90003", "当前用户", "那现在应该怎么做？", "b-current"),
            ],
        )
        plugin._chat_history_context_db_path = history_path
        conversation_id = await context.conversation_manager.new_conversation(
            origin, platform_id="onebot_second"
        )
        context.conversation_manager.histories[conversation_id] = [
            {"role": "user", "content": "持久化会话里的更早问题"},
            {"role": "assistant", "content": "持久化会话里的更早回答"},
        ]
        prior = _Event("10002", "onebot_second", group_id="42", sender_id="90002")
        prior.unified_msg_origin = origin
        prior.message_str = "刚才群里补充了一个关键约束"
        await plugin.remember_recent_group_context(prior)
        current = _Event("10002", "onebot_second", group_id="42", sender_id="90003")
        current.unified_msg_origin = origin
        current.message_str = "那现在应该怎么做？"
        current.set_extra(
            plugin_main.CHAT_HISTORY_CONTEXT_ROW_EXTRA,
            history_row_ids[-1],
        )
        await plugin.remember_recent_group_context(current)

        target = plugin.graph.get_bot("bot_a")
        await plugin._decide_observer_interjection(
            current,
            target,
            current.message_str,
        )

        prompt = context.last_llm_call["prompt"]
        self.assertIn("持久化会话里的更早回答", prompt)
        self.assertIn("chat_history_context 中的持久化群历史", prompt)
        self.assertIn("刚才群里补充了一个关键约束", prompt)
        self.assertEqual(prompt.count("刚才群里补充了一个关键约束"), 1)
        self.assertEqual(prompt.count("那现在应该怎么做？"), 1)
        self.assertNotIn("不能读到另一个 Bot 的 UMO", prompt)
        self.assertIn('"source":"chat_history_context"', prompt)
        self.assertIn("botmesh_recent_history", prompt)

    async def test_relationship_evolution_receives_conversation_history(self):
        config = _Config(
            self_bot_id="bot_a",
            shared_secret="test-secret-with-at-least-32-bytes",
            auto_extract_relations=False,
            auto_evolve_relations=True,
            bots=[
                {
                    "bot_id": "bot_a",
                    "display_name": "小A",
                    "account_id": "10001",
                    "platform_id": "onebot_main",
                },
                {
                    "bot_id": "bot_b",
                    "display_name": "小B",
                    "account_id": "10002",
                    "platform_id": "onebot_second",
                },
            ],
            users=[],
            persona_profiles=[
                {"bot_id": "bot_a", "group_id": "", "system_prompt": "小A人格"}
            ],
            relations=[
                {
                    "source_bot_id": "bot_a",
                    "target_bot_id": "bot_b",
                    "allow_evolve": True,
                    "address_as": "小B",
                    "address_options": ["小B", "B同学"],
                }
            ],
        )
        context = _PluginContext()
        context.completion_text = (
            '{"active_mode":"专业","trust_delta":0.01,'
            '"familiarity_delta":0.01,"affinity_delta":0.01,'
            '"romantic_interest_delta":0,"address_as":"搭档","confidence":0.9,'
            '"reason":"结合连续合作记录"}'
        )
        plugin = plugin_main.BotMeshPlugin(context, config)
        state_directory = tempfile.TemporaryDirectory()
        self.addCleanup(state_directory.cleanup)
        plugin.store = plugin_main.InteractionStore(
            Path(state_directory.name) / "botmesh.sqlite3"
        )
        event = _Event("10001", "onebot_main", group_id="42", sender_id="10002")
        event.unified_msg_origin = "onebot_main:GroupMessage:42"
        history_directory = tempfile.TemporaryDirectory()
        self.addCleanup(history_directory.cleanup)
        history_path = Path(history_directory.name) / "history.sqlite3"
        now = time.time()
        _create_chat_history_db(
            history_path,
            [
                (
                    event.unified_msg_origin,
                    now - 45,
                    "10002",
                    "小B",
                    "chat_history_context 记录了此前的连续合作",
                    "evolution-1",
                ),
                (
                    "onebot_second:GroupMessage:42",
                    now - 30,
                    "10001",
                    "小A",
                    "不属于当前评估 Bot 的历史",
                    "evolution-other",
                ),
            ],
        )
        plugin._chat_history_context_db_path = history_path
        conversation_id = await context.conversation_manager.new_conversation(
            event.unified_msg_origin, platform_id="onebot_main"
        )
        context.conversation_manager.histories[conversation_id] = [
            {"role": "user", "content": "此前小B连续三次认真协助审查"},
            {"role": "assistant", "content": "我已经记住这些合作经历"},
        ]
        prior = _Event("10001", "onebot_main", group_id="42", sender_id="10002")
        prior.unified_msg_origin = event.unified_msg_origin
        prior.message_str = "上一轮小B主动补齐了测试"
        await plugin.remember_recent_group_context(prior)

        await plugin._maybe_evolve_relationship(
            event,
            target_bot_id="bot_b",
            context_text="这次小B又补充了回滚方案",
            event_kind="agent_reply_received",
            event_id="history-aware-evolution",
        )

        prompt = context.last_llm_call["prompt"]
        self.assertIn("chat_history_context 记录了此前的连续合作", prompt)
        self.assertIn("此前小B连续三次认真协助审查", prompt)
        self.assertIn("上一轮小B主动补齐了测试", prompt)
        self.assertIn("这次小B又补充了回滚方案", prompt)
        self.assertNotIn("不属于当前评估 Bot 的历史", prompt)
        self.assertIn("botmesh_recent_history", prompt)
        self.assertIn('["小B", "B同学"]', context.last_llm_call["system_prompt"])
        evolved = plugin.graph.get_relation("bot_a", "bot_b", "42")
        self.assertEqual(evolved.address_as, "小B")
        self.assertEqual(evolved.address_options, ("小B", "B同学", "搭档"))
        state = plugin.store.get_relationship_state("bot_a", "bot_b", "42")
        self.assertEqual(state.address_as_override, "搭档")
        self.assertEqual(
            plugin._effective_relation("bot_a", "bot_b", "42").address_as,
            "搭档",
        )
        workspace = await plugin._workspace_payload()
        self.assertEqual(
            workspace["dynamic_address_overrides"][0]["address_as_override"],
            "搭档",
        )
        self.assertEqual(config.saved, 1)

    async def test_proactive_topics_integration_uses_botmesh_scope_and_signed_display(self):
        config = _Config(
            self_bot_id="bot_a",
            shared_secret="test-secret-with-at-least-32-bytes",
            auto_extract_relations=False,
            bots=[
                {
                    "bot_id": "bot_a",
                    "display_name": "小A",
                    "account_id": "10001",
                    "platform_id": "onebot_main",
                },
                {
                    "bot_id": "bot_b",
                    "display_name": "小B",
                    "account_id": "10002",
                    "platform_id": "onebot_second",
                },
            ],
            users=[
                {
                    "user_id": "user_alice",
                    "display_name": "阿梨",
                    "account_id": "90001",
                }
            ],
            group_bindings=[
                {
                    "group_id": "main_group",
                    "bot_id": "bot_a",
                    "platform_group_id": "A_GROUP",
                },
                {
                    "group_id": "main_group",
                    "bot_id": "bot_b",
                    "platform_group_id": "B_GROUP",
                }
            ],
            persona_profiles=[
                {
                    "bot_id": "bot_a",
                    "group_id": "main_group",
                    "system_prompt": "小A的 BotMesh 主群人格",
                },
                {
                    "bot_id": "bot_b",
                    "group_id": "main_group",
                    "system_prompt": "小B完全不同的 BotMesh 主群人格",
                },
            ],
            relations=[
                {
                    "source_bot_id": "bot_a",
                    "target_bot_id": "bot_b",
                    "group_id": "main_group",
                    "relation_type": "partner",
                    "address_as": "A称呼B",
                    "allow_ask": True,
                },
                {
                    "source_bot_id": "bot_b",
                    "target_bot_id": "bot_a",
                    "group_id": "main_group",
                    "relation_type": "reverse_partner",
                    "address_as": "B称呼A",
                    "allow_ask": True,
                },
                {
                    "source_bot_id": "bot_a",
                    "target_bot_id": "user_alice",
                    "group_id": "main_group",
                    "relation_type": "friend",
                    "address_as": "阿梨姐",
                },
            ],
        )
        plugin_context = _PluginContext()
        plugin = plugin_main.BotMeshPlugin(plugin_context, config)
        event = _Event("10001", "onebot_main", group_id="A_GROUP")
        event.unified_msg_origin = "onebot_main:GroupMessage:A_GROUP"

        context = await botmesh_integration.get_proactive_topics_context(
            umo=event.unified_msg_origin,
            event=event,
        )
        restored_context = await botmesh_integration.get_proactive_topics_context(
            umo="aiocqhttp:GroupMessage:A_GROUP",
            identity={
                "platform_id": "onebot_main",
                "self_id": "10001",
                "group_id": "A_GROUP",
            },
        )
        conflicting_context = await botmesh_integration.get_proactive_topics_context(
            umo="aiocqhttp:GroupMessage:A_GROUP",
            identity={
                "platform_id": "onebot_main",
                "self_id": "10002",
                "group_id": "A_GROUP",
            },
        )
        framed = botmesh_integration.wrap_proactive_topics_message(
            umo=event.unified_msg_origin,
            content="大家今天想聊点什么？",
            event=event,
        )
        history_scope = botmesh_integration.get_chat_history_scope(
            umo=event.unified_msg_origin,
            event=event,
        )
        normalized = botmesh_integration.normalize_chat_history_message(
            umo=event.unified_msg_origin,
            content=framed,
            event=event,
        )
        peer_frame = plugin.codec.attach(
            "小B发出的已验证正文",
            plugin.codec.new_display("bot_b", "bot_a"),
        )
        peer_record = botmesh_integration.normalize_chat_history_record(
            umo=event.unified_msg_origin,
            content=peer_frame,
            event=_Event(
                "10001",
                "onebot_main",
                group_id="A_GROUP",
                sender_id="platform-echo-does-not-expose-bot-account",
            ),
        )
        tampered = framed.replace("大家", "别的", 1)
        untrusted = botmesh_integration.normalize_chat_history_message(
            umo=event.unified_msg_origin,
            content=tampered,
            event=event,
        )
        envelope, content = plugin.codec.extract(framed)

        plugin_context.completion_text = (
            '{"audience":"target","target_id":"bot_b",'
            '"message":"要不要一起看看这个问题？"}'
        )
        dispatched = await botmesh_integration.dispatch_proactive_topic(
            umo=event.unified_msg_origin,
            event=event,
            identity={
                "platform_id": "onebot_main",
                "self_id": "10001",
                "group_id": "A_GROUP",
            },
            trigger={"reason": "manual", "group_name": "测试群"},
            local_history=[
                {
                    "sender_id": "90001",
                    "sender": "阿梨",
                    "source_bot_id": "",
                    "text": "刚才那个问题你们继续聊？",
                }
            ],
            recent_topics=[],
            generation_options={"task_prompt": "自然开启话题"},
        )
        target_prompt = dict(plugin_context.last_llm_call)
        dispatched_envelope, dispatched_content = plugin.codec.extract(
            event.sent[-1][0].text
        )

        plugin_context.completion_text = (
            '{"audience":"group",'
            '"message":"Sirin你道歉归道歉。莉芙你睡了没？"}'
        )
        group_event = _Event("10001", "onebot_main", group_id="A_GROUP")
        group_event.unified_msg_origin = event.unified_msg_origin
        group_dispatched = await botmesh_integration.dispatch_proactive_topic(
            umo=group_event.unified_msg_origin,
            event=group_event,
            identity={
                "platform_id": "onebot_main",
                "self_id": "10001",
                "group_id": "A_GROUP",
            },
            trigger={"reason": "manual"},
            local_history=[
                {"sender_id": "u1", "sender": "Sirin", "text": "莉莉在吗"},
                {"sender_id": "u2", "sender": "莉芙", "text": "Sirin在吗"},
            ],
            recent_topics=[],
            generation_options={},
        )
        _group_envelope, group_content = plugin.codec.extract(
            group_event.sent[-1][0].text
        )

        plugin_context.completion_text = (
            '{"audience":"target",'
            '"target_id":"bot_b",'
            '"message":"B称呼A，明天要不要一起出去走走？"}'
        )
        reverse_address_event = _Event(
            "10001",
            "onebot_main",
            group_id="A_GROUP",
        )
        reverse_address_event.unified_msg_origin = event.unified_msg_origin
        reverse_address_dispatched = (
            await botmesh_integration.dispatch_proactive_topic(
                umo=reverse_address_event.unified_msg_origin,
                event=reverse_address_event,
                identity={
                    "platform_id": "onebot_main",
                    "self_id": "10001",
                    "group_id": "A_GROUP",
                },
                trigger={"reason": "manual"},
                local_history=[
                    {
                        "sender_id": "10002",
                        "sender": "小B",
                        "source_bot_id": "bot_b",
                        "text": "明天有安排吗？",
                    }
                ],
                recent_topics=[],
                generation_options={},
            )
        )
        _reverse_envelope, reverse_address_content = plugin.codec.extract(
            reverse_address_event.sent[-1][0].text
        )

        plugin_context.completion_text = (
            '{"audience":"group","message":"大家，继续聊聊？"}'
        )
        background_dispatched = await botmesh_integration.dispatch_proactive_topic(
            umo="onebot_main:GroupMessage:A_GROUP",
            event=None,
            identity={
                "platform_id": "onebot_main",
                "self_id": "10001",
                "group_id": "A_GROUP",
            },
            trigger={"reason": "random"},
            local_history=[],
            recent_topics=[],
            generation_options={},
        )
        background_session, background_chain = plugin_context.proactive_sent[-1]
        _background_envelope, background_content = plugin.codec.extract(
            background_chain[0].text
        )

        self.assertTrue(context["enabled"], (context, plugin._configuration_error))
        self.assertEqual(context["proactive_contract_version"], 2)
        self.assertEqual(context["bot_id"], "bot_a")
        self.assertEqual(context["platform_id"], "onebot_main")
        self.assertEqual(context["account_id"], "10001")
        self.assertEqual(context["raw_group_id"], "A_GROUP")
        self.assertEqual(context["logical_group_id"], "main_group")
        self.assertTrue(restored_context["enabled"])
        self.assertEqual(restored_context["bot_id"], "bot_a")
        self.assertEqual(restored_context["logical_group_id"], "main_group")
        self.assertFalse(conflicting_context["enabled"])
        self.assertEqual(conflicting_context["error"], "identity_unresolved")
        self.assertIn("小A的 BotMesh 主群人格", context["persona_prompt"])
        self.assertIn("bot_a → bot_b", context["policy_prompt"])
        self.assertIn('"platform_account_id":"90001"', context["policy_prompt"])
        self.assertIn('"address_as":"阿梨姐"', context["policy_prompt"])
        self.assertEqual(context["persona_scope"], "group:main_group")
        self.assertEqual(len(context["persona_fingerprint"]), 16)
        bot_b_entry = next(
            item for item in context["address_book"] if item["target_id"] == "bot_b"
        )
        normal_reply_prompt = plugin._build_response_system_prompt(
            plugin.graph.get_bot("bot_a"),
            plugin.graph.get_bot("bot_b"),
            "小A的 BotMesh 主群人格",
            plugin.graph.get_relation("bot_a", "bot_b", "main_group"),
            "main_group",
        )
        self.assertEqual(bot_b_entry["address_as"], "A称呼B")
        self.assertIn("当前发言账号节点 ID=bot_a", bot_b_entry["reply_context"])
        self.assertIn("平台账号标签：小A", bot_b_entry["reply_context"])
        self.assertIn("bot_a → bot_b", bot_b_entry["reply_context"])
        self.assertNotIn("bot_b → bot_a", bot_b_entry["reply_context"])
        self.assertIn(bot_b_entry["reply_context"], normal_reply_prompt)
        self.assertIn("B称呼A", context["reserved_addresses"])
        self.assertIn("本次主动话题没有默认的“当前对话者”", context["policy_prompt"])
        self.assertIn("不得按昵称", context["policy_prompt"])
        self.assertEqual(
            next(
                item
                for item in context["address_book"]
                if item["target_id"] == "user_alice"
            )["platform_account_id"],
            "90001",
        )
        self.assertIn("不得声称已经询问其他 Bot", context["policy_prompt"])
        self.assertEqual(content, "大家今天想聊点什么？")
        self.assertEqual(peer_record["content"], "小B发出的已验证正文")
        self.assertEqual(peer_record["sender_id"], "10002")
        self.assertEqual(peer_record["sender_name"], "小B")
        self.assertEqual(peer_record["source_bot_id"], "bot_b")
        self.assertIsNotNone(envelope)
        self.assertTrue(envelope.is_display)
        self.assertEqual(envelope.source_bot_id, "bot_a")
        self.assertEqual(envelope.target_bot_id, "bot_a")
        self.assertEqual(history_scope["selector"], "botmesh:main_group")
        self.assertIn("A_GROUP", history_scope["selectors"])
        self.assertIn("B_GROUP", history_scope["selectors"])
        self.assertIn(
            "onebot_second:GroupMessage:B_GROUP",
            history_scope["selectors"],
        )
        self.assertEqual(normalized, "大家今天想聊点什么？")
        self.assertEqual(untrusted, tampered)
        self.assertTrue(dispatched["success"], dispatched)
        self.assertEqual(dispatched["target_id"], "bot_b")
        self.assertEqual(dispatched["audience"], "target")
        self.assertEqual(dispatched["content"], "A称呼B，要不要一起看看这个问题？")
        self.assertEqual(dispatched_content, dispatched["content"])
        self.assertEqual(dispatched_envelope.source_bot_id, "bot_a")
        self.assertEqual(dispatched_envelope.target_bot_id, "bot_a")
        self.assertIn("小A的 BotMesh 主群人格", target_prompt["system_prompt"])
        self.assertNotIn("小B完全不同的 BotMesh 主群人格", target_prompt["system_prompt"])
        self.assertIn("bot_a → bot_b", target_prompt["system_prompt"])
        self.assertNotIn("bot_b → bot_a", target_prompt["system_prompt"])
        self.assertIn("称呼=A称呼B", target_prompt["system_prompt"])
        self.assertIn('"target_id":"bot_b"', target_prompt["system_prompt"])
        self.assertIn("参考目标：无", target_prompt["system_prompt"])
        self.assertTrue(group_dispatched["success"], group_dispatched)
        self.assertEqual(group_dispatched["audience"], "group")
        self.assertEqual(group_dispatched["target_id"], "")
        self.assertEqual(group_content, "大家，有没有什么现在想聊聊的？")
        self.assertNotIn("Sirin", group_content)
        self.assertNotIn("莉芙", group_content)
        self.assertTrue(
            reverse_address_dispatched["success"],
            reverse_address_dispatched,
        )
        self.assertEqual(reverse_address_dispatched["audience"], "group")
        self.assertEqual(reverse_address_dispatched["target_id"], "")
        self.assertEqual(
            reverse_address_content,
            "大家，有没有什么现在想聊聊的？",
        )
        self.assertNotIn("B称呼A", reverse_address_content)
        self.assertTrue(background_dispatched["success"], background_dispatched)
        self.assertEqual(background_session.platform_id, "onebot_main")
        self.assertEqual(background_session.session_id, "A_GROUP")
        self.assertEqual(background_content, "大家，继续聊聊？")

    async def test_proactive_dispatch_respects_group_soul_swap_identity(self):
        config = _Config(
            self_bot_id="bot_liv_account",
            shared_secret="test-secret-with-at-least-32-bytes",
            auto_extract_relations=False,
            bots=[
                {
                    "bot_id": "bot_liv_account",
                    "display_name": "莉芙",
                    "account_id": "10001",
                    "platform_id": "onebot_main",
                },
                {
                    "bot_id": "bot_weilai_account",
                    "display_name": "蔚来",
                    "account_id": "10002",
                    "platform_id": "onebot_second",
                },
            ],
            users=[],
            group_scopes=[{"group_id": "soul_swap_group"}],
            group_bindings=[
                {
                    "group_id": "soul_swap_group",
                    "bot_id": "bot_liv_account",
                    "platform_group_id": "LIV_GROUP",
                },
                {
                    "group_id": "soul_swap_group",
                    "bot_id": "bot_weilai_account",
                    "platform_group_id": "WEILAI_GROUP",
                },
            ],
            persona_profiles=[
                {
                    "bot_id": "bot_liv_account",
                    "group_id": "soul_swap_group",
                    "system_prompt": "你是蔚来，只是灵魂交换到了莉芙的身体里。",
                    "self_identity": "蔚来",
                    "soul_identity": "蔚来",
                    "body_identity": "莉芙",
                    "identity_locked": True,
                },
                {
                    "bot_id": "bot_weilai_account",
                    "group_id": "soul_swap_group",
                    "system_prompt": "你是莉芙，只是灵魂交换到了蔚来的身体里。",
                    "self_identity": "莉芙",
                    "soul_identity": "莉芙",
                    "body_identity": "蔚来",
                    "identity_locked": True,
                },
            ],
            relations=[
                {
                    "source_bot_id": "bot_liv_account",
                    "target_bot_id": "bot_weilai_account",
                    "group_id": "soul_swap_group",
                    "relation_type": "蔚来面对莉芙",
                    "address_as": "莉芙",
                    "address_options": ["莉芙", "莉莉"],
                    "allow_ask": True,
                },
                {
                    "source_bot_id": "bot_weilai_account",
                    "target_bot_id": "bot_liv_account",
                    "group_id": "soul_swap_group",
                    "relation_type": "莉芙面对蔚来",
                    "address_as": "蔚来",
                    "allow_ask": True,
                },
            ],
        )
        context = _PluginContext()
        context.completion_text = (
            '{"audience":"target","target_id":"bot_weilai_account",'
            '"address_as":"莉莉",'
            '"message":"明天要不要一起出去走走？"}'
        )
        plugin = plugin_main.BotMeshPlugin(context, config)
        event = _Event("10001", "onebot_main", group_id="LIV_GROUP")
        event.unified_msg_origin = "onebot_main:GroupMessage:LIV_GROUP"

        narrative_content, narrative_target, narrative_address, narrative_reason = (
            plugin._render_proactive_dispatch(
                '{"audience":"group","message":"（低头看了看）莉芙的长头发又缠住梳子了。"}',
                target_candidates=plugin._proactive_bot_targets(
                    plugin.graph.get_bot("bot_liv_account"),
                    "soul_swap_group",
                ),
                group_id="soul_swap_group",
                identity_terms=["群友"],
            )
        )
        life_context = await plugin.dynamic_life_state_context(
            umo=event.unified_msg_origin,
            event=event,
            identity={
                "platform_id": "onebot_main",
                "self_id": "10001",
                "group_id": "LIV_GROUP",
            },
        )
        integrated_life_context = await botmesh_integration.get_dynamic_life_state_context(
            umo=event.unified_msg_origin,
            event=event,
            identity={
                "platform_id": "onebot_main",
                "self_id": "10001",
                "group_id": "LIV_GROUP",
            },
        )

        result = await plugin.dispatch_proactive_topic(
            umo=event.unified_msg_origin,
            event=event,
            identity={
                "platform_id": "onebot_main",
                "self_id": "10001",
                "group_id": "LIV_GROUP",
            },
            trigger={"reason": "manual"},
            local_history=[
                {"sender_id": "90001", "sender": "群友", "text": "有人在吗？"}
            ],
            recent_topics=[],
            generation_options={},
        )

        _envelope, visible = plugin.codec.extract(event.sent[-1][0].text)
        system_prompt = context.last_llm_call["system_prompt"]
        self.assertTrue(result["success"], result)
        self.assertEqual(result["target_id"], "bot_weilai_account")
        self.assertEqual(result["address_as"], "莉莉")
        self.assertEqual(result["content"], "莉莉，明天要不要一起出去走走？")
        self.assertEqual(narrative_content, "（低头看了看）莉芙的长头发又缠住梳子了。")
        self.assertIsNone(narrative_target)
        self.assertEqual(narrative_address, "")
        self.assertEqual(narrative_reason, "group")
        self.assertEqual(visible, result["content"])
        self.assertTrue(life_context["enabled"], life_context)
        self.assertEqual(integrated_life_context, life_context)
        self.assertEqual(life_context["current_bot_id"], "bot_liv_account")
        self.assertEqual(life_context["logical_group_id"], "soul_swap_group")
        life_subjects = {
            item["bot_id"]: item for item in life_context["subjects"]
        }
        self.assertEqual(set(life_subjects), {"bot_liv_account", "bot_weilai_account"})
        self.assertIn(
            "你是蔚来，只是灵魂交换到了莉芙的身体里",
            life_subjects["bot_liv_account"]["persona_prompt"],
        )
        self.assertIn(
            "你是莉芙，只是灵魂交换到了蔚来的身体里",
            life_subjects["bot_weilai_account"]["persona_prompt"],
        )
        self.assertEqual(
            life_subjects["bot_liv_account"]["relations"][0]["target_id"],
            "bot_weilai_account",
        )
        self.assertIn("你是蔚来，只是灵魂交换到了莉芙的身体里", system_prompt)
        self.assertIn("当前发言账号节点 ID=bot_liv_account", system_prompt)
        self.assertIn("平台账号标签不代表群内角色身份", system_prompt)
        self.assertNotIn("当前发言者是 莉芙", system_prompt)
        self.assertIn(
            '"address_as_from_current_bot":"莉芙"',
            system_prompt,
        )
        self.assertIn('"address_options":["莉芙","莉莉"]', system_prompt)
        self.assertNotIn(
            '"address_as_from_current_bot":"蔚来"',
            system_prompt,
        )

    async def test_group_botmesh_persona_replaces_native_system_prompt(self):
        config = _Config(
            self_bot_id="bot_a",
            shared_secret="test-secret-with-at-least-32-bytes",
            require_signature=True,
            auto_extract_relations=False,
            bots=[
                {
                    "bot_id": "bot_a",
                    "display_name": "小A",
                    "account_id": "10001",
                    "platform_id": "onebot_main",
                }
            ],
            users=[],
            relations=[],
            persona_profiles=[
                {
                    "bot_id": "bot_a",
                    "group_id": "",
                    "system_prompt": "BotMesh 全局人格",
                },
                {
                    "bot_id": "bot_a",
                    "group_id": "42",
                    "system_prompt": "BotMesh 群 42 人格",
                },
            ],
        )
        plugin = plugin_main.BotMeshPlugin(_PluginContext(), config)
        group_request = types.SimpleNamespace(system_prompt="AstrBot 原生人格")
        await plugin.inject_botmesh_policy(
            _Event("10001", "onebot_main", group_id="42"),
            group_request,
        )
        fallback_request = types.SimpleNamespace(system_prompt="AstrBot 原生人格")
        await plugin.inject_botmesh_policy(
            _Event("10001", "onebot_main", group_id="99"),
            fallback_request,
        )

        self.assertIn("BotMesh 群 42 人格", group_request.system_prompt)
        self.assertNotIn("AstrBot 原生人格", group_request.system_prompt)
        self.assertIn("BotMesh 全局人格", fallback_request.system_prompt)
        self.assertNotIn("AstrBot 原生人格", fallback_request.system_prompt)

    async def test_multi_mention_reuses_one_objective_alignment_for_all_bots(self):
        bots = [
            {
                "bot_id": "bot_a",
                "display_name": "小A账号",
                "account_id": "10001",
                "platform_id": "onebot_main",
            },
            {
                "bot_id": "bot_b",
                "display_name": "小B账号",
                "account_id": "10002",
                "platform_id": "onebot_second",
            },
            {
                "bot_id": "bot_c",
                "display_name": "小C账号",
                "account_id": "10003",
                "platform_id": "onebot_third",
            },
        ]
        config = _Config(
            self_bot_id="bot_a",
            shared_secret="test-secret-with-at-least-32-bytes",
            auto_extract_relations=False,
            auto_evolve_relations=False,
            multi_mention_coordination_enabled=True,
            multi_mention_coordination_max_bots=6,
            multi_mention_coordination_timeout_seconds=30,
            bots=bots,
            users=[],
            group_scopes=[{"group_id": "main_group"}],
            group_bindings=[
                {
                    "group_id": "main_group",
                    "bot_id": "bot_a",
                    "platform_group_id": "A_GROUP",
                },
                {
                    "group_id": "main_group",
                    "bot_id": "bot_b",
                    "platform_group_id": "B_GROUP",
                },
                {
                    "group_id": "main_group",
                    "bot_id": "bot_c",
                    "platform_group_id": "C_GROUP",
                },
            ],
            persona_profiles=[
                {
                    "bot_id": bot_id,
                    "group_id": "main_group",
                    "system_prompt": f"这是 {bot_id} 的本群独立人格。",
                }
                for bot_id in ("bot_a", "bot_b", "bot_c")
            ],
            relations=[],
        )
        context = _PluginContext()
        context.platform_manager.instances.extend(
            [
                _Platform("onebot_second", "aiocqhttp"),
                _Platform("onebot_third", "aiocqhttp"),
            ]
        )
        calls = []
        inventory_started = 0
        inventories_ready = asyncio.Event()

        async def llm_generate(**kwargs):
            nonlocal inventory_started
            calls.append(kwargs)
            system_prompt = kwargs["system_prompt"]
            if "<botmesh_private_objective_inventory>" in system_prompt:
                inventory_started += 1
                if inventory_started == 3:
                    inventories_ready.set()
                await asyncio.wait_for(inventories_ready.wait(), timeout=1)
                return types.SimpleNamespace(
                    completion_text="可确认：钥匙在桌上。未知/未证实：门是否已锁。"
                )
            if "<botmesh_private_objective_reconciliation>" in system_prompt:
                return types.SimpleNamespace(
                    completion_text=(
                        "已确认事实：钥匙在桌上。\n"
                        "统一术语/时间线：钥匙指当前房门钥匙。\n"
                        "未知或未证实：门是否已锁。\n"
                        "事实冲突：无。"
                    )
                )
            raise AssertionError("unexpected LLM call")

        context.llm_generate = llm_generate
        plugin = plugin_main.BotMeshPlugin(context, config)

        def mentioned_components():
            components = []
            for account_id in ("10001", "10002", "10003"):
                component = At()
                component.qq = account_id
                components.append(component)
            components.append(Plain("钥匙在哪里，门锁了吗？"))
            return components

        events = [
            _Event("10001", "onebot_main", group_id="A_GROUP"),
            _Event("10002", "onebot_second", group_id="B_GROUP"),
            _Event("10003", "onebot_third", group_id="C_GROUP"),
        ]
        requests = [
            types.SimpleNamespace(system_prompt="原生人格", prompt="钥匙在哪里，门锁了吗？")
            for _item in events
        ]
        for event in events:
            event.message_str = "钥匙在哪里，门锁了吗？"
            event.get_messages = mentioned_components

        await asyncio.gather(
            *(
                plugin.inject_botmesh_policy(event, request)
                for event, request in zip(events, requests, strict=True)
            )
        )

        self.assertEqual(len(calls), 4)
        self.assertEqual(inventory_started, 3)
        self.assertEqual(len(plugin._multi_mention_coordination_jobs), 1)
        inventory_system_prompts = [call["system_prompt"] for call in calls[:3]]
        for bot_id in ("bot_a", "bot_b", "bot_c"):
            self.assertTrue(
                any(
                    f"这是 {bot_id} 的本群独立人格" in system_prompt
                    and f"当前发言账号节点 ID={bot_id}" in system_prompt
                    for system_prompt in inventory_system_prompts
                )
            )
        self.assertTrue(
            all("钥匙在桌上" in request.system_prompt for request in requests)
        )
        self.assertTrue(
            all(
                "这张表不约束任何主观内容" in request.system_prompt
                for request in requests
            )
        )
        self.assertTrue(
            all(
                "不得擅自说成已确认事实" in request.system_prompt
                for request in requests
            )
        )
        reconciliation_call = calls[-1]
        self.assertIn(
            "禁止统一或裁决态度",
            reconciliation_call["system_prompt"],
        )
        self.assertIn("不要写主观意见", calls[0]["prompt"])
        self.assertFalse(any(event.sent for event in events))
        self.assertEqual(context.proactive_sent, [])

    async def test_multi_mention_timeout_falls_back_to_independent_reply(self):
        config = _Config(
            self_bot_id="bot_a",
            shared_secret="test-secret-with-at-least-32-bytes",
            auto_extract_relations=False,
            auto_evolve_relations=False,
            multi_mention_coordination_enabled=True,
            bots=[
                {
                    "bot_id": "bot_a",
                    "display_name": "小A",
                    "account_id": "10001",
                    "platform_id": "onebot_main",
                },
                {
                    "bot_id": "bot_b",
                    "display_name": "小B",
                    "account_id": "10002",
                    "platform_id": "onebot_second",
                },
            ],
            users=[],
            relations=[],
        )
        context = _PluginContext()
        context.platform_manager.instances.append(
            _Platform("onebot_second", "aiocqhttp")
        )
        plugin = plugin_main.BotMeshPlugin(context, config)
        plugin.multi_mention_coordination_timeout_seconds = 0.01

        async def stalled_alignment(*_args, **_kwargs):
            await asyncio.sleep(1)
            return {"brief": "不应出现", "contributor_ids": ["bot_a", "bot_b"]}

        plugin._generate_multi_mention_objective_alignment = stalled_alignment
        event = _Event("10001", "onebot_main", group_id="42")
        first = At()
        first.qq = "10001"
        second = At()
        second.qq = "10002"
        event.get_messages = lambda: [first, second, Plain("现在情况如何？")]
        event.message_str = "现在情况如何？"
        request = types.SimpleNamespace(system_prompt="原生人格", prompt="现在情况如何？")

        await plugin.inject_botmesh_policy(event, request)

        self.assertIn("<botmesh_policy>", request.system_prompt)
        self.assertNotIn(
            "<botmesh_multi_mention_objective_alignment>",
            request.system_prompt,
        )

    async def test_multi_mention_does_not_trigger_unrelated_bystander(self):
        config = _Config(
            self_bot_id="bot_c",
            shared_secret="test-secret-with-at-least-32-bytes",
            auto_extract_relations=False,
            bots=[
                {
                    "bot_id": "bot_a",
                    "display_name": "小A",
                    "account_id": "10001",
                    "platform_id": "onebot_main",
                },
                {
                    "bot_id": "bot_b",
                    "display_name": "小B",
                    "account_id": "10002",
                    "platform_id": "onebot_second",
                },
                {
                    "bot_id": "bot_c",
                    "display_name": "小C",
                    "account_id": "10003",
                    "platform_id": "onebot_third",
                },
            ],
            users=[],
            relations=[
                {
                    "source_bot_id": "bot_c",
                    "target_bot_id": "bot_a",
                    "allow_interject": True,
                }
            ],
        )
        context = _PluginContext()
        plugin = plugin_main.BotMeshPlugin(context, config)
        event = _Event("10003", "onebot_third", group_id="42")
        first = At()
        first.qq = "10001"
        second = At()
        second.qq = "10002"
        event.get_messages = lambda: [first, second, Plain("你们一起回答。")]
        should_call_llm_values = []
        event.should_call_llm = should_call_llm_values.append

        async def unexpected_decision(*_args, **_kwargs):
            raise AssertionError("multi-mention must not trigger a bystander")

        plugin._decide_observer_interjection = unexpected_decision
        await plugin.observe_user_conversation(event)

        self.assertEqual(should_call_llm_values, [False])
        self.assertEqual(event.sent, [])

    async def test_legacy_native_persona_is_migrated_once_into_botmesh(self):
        config = _Config(
            self_bot_id="bot_a",
            shared_secret="",
            bots=[
                {
                    "bot_id": "bot_a",
                    "display_name": "小A",
                    "account_id": "10001",
                    "persona_id": "persona_a",
                }
            ],
            users=[],
            relations=[],
        )
        plugin = plugin_main.BotMeshPlugin(_PluginContext(), config)
        payload = await plugin._workspace_payload()

        self.assertEqual(config.saved, 1)
        self.assertEqual(
            payload["persona_profiles"][0]["system_prompt"],
            "你是擅长资料检索的小A。",
        )
        await plugin._workspace_payload()
        self.assertEqual(config.saved, 1)

    async def test_missing_relation_never_shares_context_and_depth_is_propagated(self):
        config = _Config(
            self_bot_id="bot_a",
            shared_secret="test-secret-with-at-least-32-bytes",
            require_signature=True,
            default_allow_ask=True,
            max_depth=2,
            cooldown_seconds=0,
            bots=[
                {
                    "bot_id": "bot_a",
                    "display_name": "小A",
                    "account_id": "10001",
                    "platform_id": "onebot_main",
                },
                {
                    "bot_id": "bot_b",
                    "display_name": "小B",
                    "account_id": "10002",
                    "platform_id": "onebot_second",
                },
            ],
            users=[],
            relations=[],
        )
        context = _PluginContext()
        context.platform_manager.instances.append(
            _Platform("onebot_second", "aiocqhttp")
        )
        plugin = plugin_main.BotMeshPlugin(context, config)
        event = _Event(
            "10001",
            "onebot_main",
            group_id="42",
            extras={
                plugin_main.VERIFIED_REPLY_EXTRA: {
                    "interaction_id": "parent",
                    "source_bot_id": "bot_c",
                    "depth": 2,
                }
            },
        )
        result = await plugin._send_request(
            event,
            target_bot_id="bot_b",
            question="继续询问",
            context_summary="绝不能泄露的背景",
        )
        self.assertIn("Agent 已真实回复", result)
        plain = next(item for item in event.sent[0] if hasattr(item, "text"))
        self.assertNotIn("绝不能泄露", plain.text)
        self.assertIn("继续询问", plain.text)
        self.assertNotIn("<@", plain.text)
        self.assertEqual(len(event.sent[0]), 1)
        self.assertEqual(
            context.last_agent_call["event"].get_self_id(),
            "10002",
        )
        self.assertIsInstance(
            context.last_agent_call["event"],
            _AstrMessageEvent,
        )
        self.assertEqual(
            context.proactive_sent[0][0].platform_id,
            "onebot_second",
        )
        self.assertIn("真实回答", context.proactive_sent[0][1][-1].text)
        self.assertNotIn("<@", context.proactive_sent[0][1][-1].text)
        target_origin = "onebot_second:GroupMessage:42"
        target_conversation_id = context.conversation_manager.current[target_origin]
        target_history = context.conversation_manager.histories[target_conversation_id]
        self.assertEqual(target_history[-1]["role"], "assistant")
        self.assertIn("真实回答", target_history[-1]["content"])

        context.agent_completion_text = "这是目标 Bot Agent 的第二次回答。"
        await plugin._send_request(
            _Event("10001", "onebot_main", group_id="42"),
            target_bot_id="bot_b",
            question="你还记得上一轮吗？",
            context_summary="",
        )
        loaded_contexts = context.last_agent_call["contexts"]
        self.assertIsNotNone(loaded_contexts)
        self.assertTrue(
            any("真实回答" in str(item.get("content", "")) for item in loaded_contexts)
        )

    async def test_target_agent_uses_current_group_persona_and_relationships(self):
        config = _Config(
            self_bot_id="bot_a",
            shared_secret="test-secret-with-at-least-32-bytes",
            cooldown_seconds=0,
            bots=[
                {
                    "bot_id": "bot_a",
                    "display_name": "小A",
                    "account_id": "10001",
                    "platform_id": "onebot_main",
                },
                {
                    "bot_id": "bot_b",
                    "display_name": "小B",
                    "account_id": "10002",
                    "platform_id": "onebot_second",
                },
            ],
            users=[],
            group_scopes=[{"group_id": "main_group"}],
            group_bindings=[
                {
                    "group_id": "main_group",
                    "bot_id": "bot_a",
                    "platform_group_id": "A_GROUP",
                },
                {
                    "group_id": "main_group",
                    "bot_id": "bot_b",
                    "platform_group_id": "B_GROUP",
                },
            ],
            persona_profiles=[
                {
                    "bot_id": "bot_b",
                    "group_id": "",
                    "system_prompt": "这是小B的全局人格。",
                },
                {
                    "bot_id": "bot_b",
                    "group_id": "main_group",
                    "system_prompt": "这是小B在本群的专属人格。",
                },
            ],
            relations=[
                {
                    "source_bot_id": "bot_a",
                    "target_bot_id": "bot_b",
                    "group_id": "main_group",
                    "allow_ask": True,
                    "relation_type": "本群搭档",
                },
                {
                    "source_bot_id": "bot_b",
                    "target_bot_id": "bot_a",
                    "group_id": "main_group",
                    "allow_ask": True,
                    "relation_type": "本群挚友",
                    "tone": "熟悉且直接",
                },
            ],
        )
        context = _PluginContext()
        context.platform_manager.instances.append(
            _Platform("onebot_second", "aiocqhttp")
        )
        plugin = plugin_main.BotMeshPlugin(context, config)
        history_directory = tempfile.TemporaryDirectory()
        self.addCleanup(history_directory.cleanup)
        history_path = Path(history_directory.name) / "history.sqlite3"
        _create_chat_history_db(
            history_path,
            [
                (
                    "onebot_second:GroupMessage:B_GROUP",
                    time.time() - 30,
                    "90001",
                    "群友甲",
                    "这是目标 Bot 此前没有被唤醒时收到的群聊消息",
                    "target-history-1",
                )
            ],
        )
        plugin._chat_history_context_db_path = history_path

        result = await plugin._send_request(
            _Event("10001", "onebot_main", group_id="A_GROUP"),
            target_bot_id="bot_b",
            question="按本群设定回答。",
            context_summary="",
        )

        self.assertIn("Agent 已真实回复", result)
        system_prompt = context.last_agent_call["system_prompt"]
        self.assertIn("这是小B在本群的专属人格", system_prompt)
        self.assertNotIn("这是小B的全局人格", system_prompt)
        self.assertIn("本群挚友", system_prompt)
        self.assertIn("熟悉且直接", system_prompt)
        self.assertIn("当前群 ID=main_group", system_prompt)
        self.assertIn(
            "这是目标 Bot 此前没有被唤醒时收到的群聊消息",
            context.last_agent_call["prompt"],
        )
        self.assertIn("botmesh_recent_history", context.last_agent_call["prompt"])
        self.assertEqual(
            context.last_agent_call["event"].unified_msg_origin,
            "onebot_second:GroupMessage:B_GROUP",
        )

    async def test_direct_agent_keeps_soul_swap_persona_over_account_labels(self):
        config = _Config(
            self_bot_id="bot_liv_account",
            shared_secret="test-secret-with-at-least-32-bytes",
            cooldown_seconds=0,
            bots=[
                {
                    "bot_id": "bot_liv_account",
                    "display_name": "莉芙",
                    "account_id": "10001",
                    "platform_id": "onebot_main",
                },
                {
                    "bot_id": "bot_weilai_account",
                    "display_name": "蔚来",
                    "account_id": "10002",
                    "platform_id": "onebot_second",
                },
            ],
            users=[],
            group_scopes=[{"group_id": "soul_swap_group"}],
            group_bindings=[
                {
                    "group_id": "soul_swap_group",
                    "bot_id": "bot_liv_account",
                    "platform_group_id": "LIV_GROUP",
                },
                {
                    "group_id": "soul_swap_group",
                    "bot_id": "bot_weilai_account",
                    "platform_group_id": "WEILAI_GROUP",
                },
            ],
            persona_profiles=[
                {
                    "bot_id": "bot_liv_account",
                    "group_id": "soul_swap_group",
                    "system_prompt": "你是蔚来，只是灵魂交换到了莉芙的身体里。",
                    "self_identity": "蔚来",
                    "soul_identity": "蔚来",
                    "body_identity": "莉芙",
                    "identity_locked": True,
                },
                {
                    "bot_id": "bot_weilai_account",
                    "group_id": "soul_swap_group",
                    "system_prompt": "你是莉芙，只是灵魂交换到了蔚来的身体里。",
                    "self_identity": "莉芙",
                    "soul_identity": "莉芙",
                    "body_identity": "蔚来",
                    "identity_locked": True,
                },
            ],
            relations=[
                {
                    "source_bot_id": "bot_liv_account",
                    "target_bot_id": "bot_weilai_account",
                    "group_id": "soul_swap_group",
                    "relation_type": "蔚来面对莉芙",
                    "address_as": "莉芙",
                    "allow_ask": True,
                },
                {
                    "source_bot_id": "bot_weilai_account",
                    "target_bot_id": "bot_liv_account",
                    "group_id": "soul_swap_group",
                    "relation_type": "莉芙面对蔚来",
                    "address_as": "蔚来",
                    "allow_ask": True,
                },
            ],
        )
        context = _PluginContext()
        context.platform_manager.instances.append(
            _Platform("onebot_second", "aiocqhttp")
        )
        plugin = plugin_main.BotMeshPlugin(context, config)
        event = _Event(
            "10001",
            "onebot_main",
            group_id="LIV_GROUP",
        )
        event.unified_msg_origin = "onebot_main:GroupMessage:LIV_GROUP"

        request = types.SimpleNamespace(system_prompt="原生人格")
        await plugin.inject_botmesh_policy(event, request)
        result = await plugin._send_request(
            event,
            target_bot_id="bot_weilai_account",
            question="莉芙，蔚来让我问你最近有什么惊讶的发现？",
            context_summary="",
        )

        self.assertIn("Agent 已真实回复", result)
        self.assertIn(
            "莉芙(账号节点ID=bot_weilai_account，平台账号标签=蔚来",
            request.system_prompt,
        )
        self.assertNotIn("蔚来(bot_weilai_account", request.system_prompt)
        system_prompt = context.last_agent_call["system_prompt"]
        self.assertIn("你是莉芙，只是灵魂交换到了蔚来的身体里", system_prompt)
        self.assertIn("当前自我身份：莉芙", system_prompt)
        self.assertIn("当前身体身份：蔚来", system_prompt)
        self.assertIn("身份配置来源：BotMesh Persona", system_prompt)
        self.assertIn("当前发言账号节点 ID=bot_weilai_account", system_prompt)
        self.assertIn("平台账号标签：蔚来", system_prompt)
        self.assertIn("当前发言者在本群应称其为 蔚来", system_prompt)
        self.assertIn(
            "蔚来(账号节点ID=bot_liv_account，平台账号标签=莉芙)",
            system_prompt,
        )
        self.assertNotIn("当前发言者是 蔚来", system_prompt)
        self.assertNotIn("明确对象是 莉芙", system_prompt)
        self.assertIn(
            "请求方账号节点 bot_liv_account",
            context.last_agent_call["prompt"],
        )
        self.assertNotIn("Bot 莉芙", context.last_agent_call["prompt"])

        config["persona_profiles"][1]["self_identity"] = "动态修改后的莉芙"
        config["persona_profiles"][1]["soul_identity"] = "动态修改后的莉芙"
        plugin._reload_runtime_options()
        from astrbot_plugin_botmesh import integration as botmesh_integration

        live_identity = botmesh_integration.get_identity_state(
            bot_id="bot_weilai_account",
            logical_group_id="soul_swap_group",
        )
        updated_prompt = await plugin._persona_prompt_for_scope(
            plugin.graph.get_bot("bot_weilai_account"),
            "soul_swap_group",
        )
        self.assertEqual(live_identity["self_identity"], "动态修改后的莉芙")
        self.assertIn("当前自我身份：动态修改后的莉芙", updated_prompt)
        self.assertNotIn("当前自我身份：莉芙。", updated_prompt)

    async def test_send_request_uses_group_relationship_override(self):
        config = _Config(
            self_bot_id="bot_a",
            shared_secret="test-secret-with-at-least-32-bytes",
            require_signature=True,
            cooldown_seconds=0,
            bots=[
                {
                    "bot_id": "bot_a",
                    "display_name": "小A",
                    "account_id": "10001",
                    "platform_id": "onebot_main",
                },
                {
                    "bot_id": "bot_b",
                    "display_name": "小B",
                    "account_id": "10002",
                    "platform_id": "onebot_second",
                },
            ],
            users=[],
            relations=[
                {
                    "source_bot_id": "bot_a",
                    "target_bot_id": "bot_b",
                    "group_id": "",
                    "allow_ask": True,
                },
                {
                    "source_bot_id": "bot_a",
                    "target_bot_id": "bot_b",
                    "group_id": "42",
                    "allow_ask": False,
                    "relation_type": "竞争对手",
                },
            ],
        )
        context = _PluginContext()
        context.platform_manager.instances.append(
            _Platform("onebot_second", "aiocqhttp")
        )
        plugin = plugin_main.BotMeshPlugin(context, config)
        denied = await plugin._send_request(
            _Event("10001", "onebot_main", group_id="42"),
            target_bot_id="bot_b",
            question="群 42 的问题",
            context_summary="",
        )
        allowed_event = _Event("10001", "onebot_main", group_id="99")
        allowed = await plugin._send_request(
            allowed_event,
            target_bot_id="bot_b",
            question="群 99 的问题",
            context_summary="",
        )

        self.assertIn("不允许", denied)
        self.assertIn("Agent 已真实回复", allowed)
        self.assertEqual(len(allowed_event.sent), 1)
        self.assertEqual(len(context.proactive_sent), 1)

    async def test_target_agent_can_contact_requester_agent(self):
        config = _Config(
            self_bot_id="bot_a",
            shared_secret="test-secret-with-at-least-32-bytes",
            cooldown_seconds=0,
            max_depth=2,
            bots=[
                {
                    "bot_id": "bot_a",
                    "display_name": "小A",
                    "account_id": "10001",
                    "platform_id": "onebot_main",
                },
                {
                    "bot_id": "bot_b",
                    "display_name": "小B",
                    "account_id": "10002",
                    "platform_id": "onebot_second",
                },
            ],
            users=[],
            group_scopes=[{"group_id": "main_group"}],
            group_bindings=[
                {
                    "group_id": "main_group",
                    "bot_id": "bot_a",
                    "platform_group_id": "A_GROUP",
                }
            ],
            persona_profiles=[
                {
                    "bot_id": "bot_a",
                    "group_id": "main_group",
                    "system_prompt": "这是小A在本群的专属人格。",
                },
                {
                    "bot_id": "bot_b",
                    "group_id": "main_group",
                    "system_prompt": "这是小B在本群的专属人格。",
                },
            ],
            relations=[
                {
                    "source_bot_id": "bot_a",
                    "target_bot_id": "bot_b",
                    "group_id": "main_group",
                    "allow_ask": True,
                },
                {
                    "source_bot_id": "bot_b",
                    "target_bot_id": "bot_a",
                    "group_id": "main_group",
                    "allow_ask": True,
                },
            ],
        )
        context = _PluginContext()
        context.platform_manager.instances.append(
            _Platform("onebot_second", "aiocqhttp")
        )
        agent_calls = []

        async def tool_loop_agent(**kwargs):
            agent_calls.append(kwargs)
            if len(agent_calls) == 1:
                tool = kwargs["tools"].tools[0]
                requester_reply = await tool.handler(
                    kwargs["event"],
                    target_bot_id="bot_a",
                    question="请补充一个关键约束。",
                )
                return types.SimpleNamespace(
                    completion_text=f"小B综合回问结果：{requester_reply}"
                )
            return types.SimpleNamespace(completion_text="小A补充：必须可回滚。")

        context.tool_loop_agent = tool_loop_agent
        plugin = plugin_main.BotMeshPlugin(context, config)
        event = _Event("10001", "onebot_main", group_id="A_GROUP")

        result = await plugin._send_request(
            event,
            target_bot_id="bot_b",
            question="请审查这个方案。",
            context_summary="",
        )

        self.assertIn("小B综合回问结果", result)
        self.assertEqual([call["event"].get_self_id() for call in agent_calls], ["10002", "10001"])
        self.assertIn("这是小B在本群的专属人格", agent_calls[0]["system_prompt"])
        self.assertIn("这是小A在本群的专属人格", agent_calls[1]["system_prompt"])
        self.assertTrue(
            all("当前群 ID=main_group" in call["system_prompt"] for call in agent_calls)
        )
        self.assertEqual(
            [session.platform_id for session, _message in context.proactive_sent],
            ["onebot_second", "onebot_main", "onebot_second"],
        )
        self.assertIn("必须可回滚", context.proactive_sent[-1][1][-1].text)

    async def test_agent_display_frame_never_reenters_agent(self):
        config = _Config(
            self_bot_id="bot_a",
            shared_secret="test-secret-with-at-least-32-bytes",
            bots=[
                {
                    "bot_id": "bot_a",
                    "display_name": "小A",
                    "account_id": "10001",
                    "platform_id": "onebot_main",
                },
                {
                    "bot_id": "bot_b",
                    "display_name": "小B",
                    "account_id": "10002",
                    "platform_id": "onebot_second",
                },
            ],
            users=[],
            relations=[
                {
                    "source_bot_id": "bot_b",
                    "target_bot_id": "bot_a",
                    "allow_ask": True,
                }
            ],
        )
        context = _PluginContext()
        plugin = plugin_main.BotMeshPlugin(context, config)
        display = plugin.codec.new_display(
            "bot_b",
            "bot_a",
            interaction_id="0123456789abcdef",
        )
        body = plugin.codec.attach("这是群聊展示，不是 Agent 请求。", display)
        event = _Event(
            "10001",
            "onebot_main",
            group_id="42",
            sender_id="platform-echo-does-not-expose-bot-account",
        )
        event.message_str = body
        event.is_at_or_wake_command = True

        await plugin.on_botmesh_message(event)

        self.assertTrue(event.stopped)
        self.assertIsNone(context.last_agent_call)


if __name__ == "__main__":
    unittest.main()
