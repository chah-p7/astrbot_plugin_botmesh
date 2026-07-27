from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import time
import types
import unittest
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
            "astrbot.core.utils": utils,
            "astrbot.core.utils.astrbot_path": path_module,
        }
    )


_install_astrbot_stubs()

from astrbot_plugin_botmesh import main as plugin_main
from astrbot_plugin_botmesh import integration as botmesh_integration


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

    def meta(self):
        return self._meta

    def get_client(self):
        return _Client()


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
        known = {
            platform.meta().id for platform in self.platform_manager.get_insts()
        }
        if session.platform_id not in known:
            return False
        self.proactive_sent.append((session, message))
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
        self.assertEqual(
            await plugin._get_persona_prompt(
                plugin.graph.get_bot("bot_a"),
                _Event("10001", "onebot_main", group_id="BOT_A_OPENID"),
            ),
            "群 42 的插件人格",
        )
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

    async def test_ai_adapts_global_persona_and_group_address_as_draft(self):
        plugin, context, config = self.make_plugin()
        context.completion_text = (
            '{"personas":[{"bot_id":"bot_a","system_prompt":"主群专属人格"}],'
            '"relations":[{"source_bot_id":"bot_a","target_bot_id":"owner",'
            '"address_as":"老师","allow_ask":false,"share_context":false}],"notes":[]}'
        )
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
        self.assertEqual(context.last_llm_call["chat_provider_id"], "provider_a")
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
                }
            ],
        )
        context = _PluginContext()
        context.completion_text = (
            '{"active_mode":"专业","trust_delta":0.01,'
            '"familiarity_delta":0.01,"affinity_delta":0.01,'
            '"romantic_interest_delta":0,"confidence":0.9,'
            '"reason":"结合连续合作记录"}'
        )
        plugin = plugin_main.BotMeshPlugin(context, config)
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
            users=[],
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
                }
            ],
            relations=[
                {
                    "source_bot_id": "bot_a",
                    "target_bot_id": "bot_b",
                    "group_id": "main_group",
                    "relation_type": "partner",
                    "address_as": "小B",
                    "allow_ask": True,
                }
            ],
        )
        plugin = plugin_main.BotMeshPlugin(_PluginContext(), config)
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
        tampered = framed.replace("大家", "别的", 1)
        untrusted = botmesh_integration.normalize_chat_history_message(
            umo=event.unified_msg_origin,
            content=tampered,
            event=event,
        )
        envelope, content = plugin.codec.extract(framed)

        self.assertTrue(context["enabled"])
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
        self.assertIn("不得声称已经询问其他 Bot", context["policy_prompt"])
        self.assertEqual(content, "大家今天想聊点什么？")
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
