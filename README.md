# BotMesh

BotMesh 是一个面向 AstrBot 的多 Bot 关系网与 Agent 互通插件。

本插件由 Sirin 发起并维护，使用 OpenAI Codex 协助开发与迭代。

它解决的核心问题是：当 Bot A 想知道 Bot B 的意见时，A 不能按照 B 的人设猜测回答，
而是必须通过 `botmesh_ask` 把问题交给 B 的独立 Agent。群聊只负责展示，不再负责唤醒或传输请求：

```text
Bot A Agent -> botmesh_ask -> Bot B Agent
Bot A 平台账号 -> 问题正文（群聊展示）
Bot B Agent -> 使用 B 的有效 BotMesh 人格、B 的群聊模型和 Agent 循环处理
Bot B 平台账号 -> 回答正文（群聊展示）
Bot B Agent -> 把同一回答作为工具结果返回 Bot A Agent
BotMesh -> 把本次请求与回答写入 Bot B 在当前群的持久化会话上下文
```

特别地，B 的回复确实由 B 的平台账号发到原群，但不再添加 `<@openid>` 或原生 `At` 消息头；
A 不依赖这条群消息继续执行，而是直接接收 B Agent 的返回值。展示消息带不可见的 `DSP`
防回流帧，只用于阻止平台把同一文本再次送进普通 LLM，不承载 Agent 问答数据。

## 当前版本范围

- 面向 OneBot v11 / `aiocqhttp` 与 QQ 官方 API / `qq_official` 群聊。
- 一个 AstrBot 实例挂载两个或多个参与 Bot 平台账号；插件按 `platform_id` 路由目标 Agent 与发言账号。
- 参与 Agent 直连的 Bot 必须由同一个 AstrBot 实例承载；当前版本不跨进程模拟或冒充远端 Bot。
- 同一实例统一配置 `bots`、`group_scopes`、`group_bindings`、`persona_profiles` 和 `relations`。
- `self_bot_id` 是无法从事件账号识别时的默认/备用身份；多平台实例通常会自动匹配。
- 使用有向关系边；`A -> B` 允许询问并不自动代表 `B -> A` 允许询问。
- 支持“全局默认 + 分群覆盖”：同一方向可为不同群分别设置关系、数值与权限。
- 人格与结构化身份都由 BotMesh 保存并支持“全局默认 + 分群覆盖”；聊天模型仍使用当前 AstrBot 会话模型。结构化身份包括当前自我、灵魂/操控者、身体和防历史覆盖策略，供 Memory 动态读取。
- 可从每个 Bot 的全局 BotMesh 人格自动抽取有向关系表；管理员配置的同一对关系优先。
- Agent 通信不依赖群聊平台把 A 的展示消息投递给 B；平台只需支持对应账号向原群发消息。

## 多 Bot 同时 @ 的客观事实对齐

当同一条群消息明确 @ 两个或更多已登记 Bot 时，BotMesh 会在它们公开回复前执行一次私下事实会商：

1. 所有参与 Bot 使用自己的当前群 Persona、世界观和近期群历史，并行提交与本题有关的客观事实清单。
2. 固定选出的协调 Bot 只归并人物身份、设定状态、已发生事件、时间线、地点、数字、专有名词、明确约束和未知/冲突项。
3. 同一份共享事实表注入所有被 @ Bot 的最终回复；每个 Bot 随后仍按自己的 Persona 与有向关系独立表达。

事实对齐不会统一态度、喜恶、价值判断、情绪、评价、建议或语气。客观证据不足时统一标为未知，多个来源冲突时保留为“事实冲突”，协调 Bot 不会为了看起来一致而强行选边。内部清单和事实表不会发送到群聊，也不会触发未被 @ 的旁听 Bot。

同一条消息分别到达多个平台账号时会复用一个会商任务，避免每个账号重复调用整轮模型。默认最多 6 个 Bot 并行提交事实清单；超过上限时，其余被 @ Bot 仍会收到共享事实表，但不再额外提交清单。可在统一管理页的“多 Bot 客观事实对齐”中调整开关、上限、总超时和 Token 预算。会商超时或模型失败时自动回退为各 Bot 原有的独立回复，不阻断正常对话。

## 安装

将整个目录放入：

```text
AstrBot/data/plugins/astrbot_plugin_botmesh
```

然后在 AstrBot WebUI 中重载或启用插件。

## 统一管理页面

插件提供独立的“BotMesh 统一管理”页面，不需要在关系条目中反复手打 `bot_id`：

1. 打开 AstrBot WebUI 的插件详情页，进入 BotMesh 的“统一管理”。
2. “自动发现”会在后台读取 AstrBot 已有的平台配置；首次尚无 Bot 节点时，可识别账号会自动加入
   编辑区，已有配置则可一键导入或同步。
3. 在“参与者”中补充能力与别名，也可添加普通用户节点；模型和原生 Persona 不在节点里重复配置。
4. 在“群聊配置”中单独新建逻辑群，再从“选择已有群”下拉框打开；逻辑群是正式配置，尚未填写
   人格或映射时也能保存，并支持重命名和删除。选中后在表格中逐个填写 Bot 的平台群 ID、独立人格提示词与世界观提示词。
   QQ 官方 API 给同一真实群、不同 Bot 返回的 `group_openid` 可能不同；`group_bindings` 会把它们
   映射到同一个逻辑群，不能直接假设这些 ID 相同。群内未填写专属人格时会明确显示“继承全局”；
   可以选择对话模型，按管理员要求分别填写人格或世界观分栏；也可让 AI 查看所有已有的全局人格与世界观，为单个或全部 Bot 编排本群草稿。模型可以
   按管理员要求整合、修改、拆分或交换设定素材，但会尽量沿用原句，并可同步调整本群关系中的
   `address_as` 称呼。AI 不能借此改动询问、上下文分享、调情或旁听权限，结果确认保存后才生效。
   也可以在“参与者”的自动填写卡片直接选择一个对话模型：插件会把当前有效的 BotMesh 人格当作
   不可信只读数据交给该模型，生成节点与关系草稿。可选择目标群；模型会补全关系类型、
   称呼、语气、对目标的看法/认识、信任、熟悉、好感与浪漫倾向。关系页也能按要求单独生成有向的看法/认识草稿。草稿不会自动保存，也绝不会自动开启询问、上下文
   分享、调情或旁听插话权限。人格、世界观和关系看法的分栏生成会在服务端后台执行，管理页通过短请求查询进度；单次生成最长可运行 5 分钟，短暂的网络中断会自动重试查询，不会中止已经开始的模型任务。
5. 在“关系”中先选择同一个逻辑群，再设置询问、旁听、动态变化、调情等方向性权限；继承的全局
   关系会以只读卡片显示，需要修改时一键建立群专属覆盖。
6. 在“全部设置”中可编辑自动附加的“人格认知强化”和“自然人类表达 / 去 AI 化”提示词，并完成身份、安全、通信、关系抽取、动态关系和旁听配置，最后保存全部。

页面先读取 BotMesh 与 Provider 配置并立即开放编辑，再在后台读取 `platform_manager` 中的
全部平台配置，因此单个平台连接较慢时不会卡住整个页面。“刷新平台”只刷新探测结果，不会覆盖
尚未保存的编辑内容。OneBot v11 在线时还会查询 `get_login_info` 得到机器人 QQ；平台未暴露自身
账号时，该行仍会显示，点击操作会明确说明暂时不能导入的原因。

自动导入会把 AstrBot 的 `platform_id` 持久化到 Bot 节点。后续识别优先按 `platform_id` 对齐，
再以账号 ID 作为兼容回退；因此平台重连、账号信息暂时不可用或重复点击导入时都会同步同一节点，
而不会无提示地创建重复 Bot。多个平台配置暴露同一个真实账号时会在发现区归并显示。
QQ 官方尚未获得真实 OpenID 时可能暂时返回 `qq_official` 或 `unknown_selfid`；这些占位值
不会用于账号匹配或同账号归并，并允许在多个待识别 Bot 行中临时重复，避免把不同的
`default_...` 平台配置误判为同一个 Bot。内部 `bot_id` 仍保持唯一；自动导入会用平台 ID
生成不同的临时 Bot ID，而不是创建无法区分的同名关系节点。
平台本轮没有再次返回 self OpenID 时，自动发现会复用该平台已经保存的真实账号，不会把已完成
映射的 Bot 降级显示为“账号未就绪”。
它会阻止自己指向自己、已不存在的参与者和同一范围内重复的 A → B；同一方向的全局行与不同
群专属行可以并存。
保存后会立即刷新运行中的关系图。A → B 与 B → A 仍需分别建立，后者不会被自动脑补。

AstrBot 原生 `_conf_schema.json` 的 `options` 是静态选项，不能动态引用同一配置中的 `bots`
条目，所以基础配置里的 `relations` 字段仍是文本输入；需要动态下拉框时请使用统一管理页面。
首次安装或这次升级后需要重载一次插件，AstrBot 才会发现新增的 Page 目录。若插件详情页没有
显示该页面，请升级到支持 Plugin Pages 的 AstrBot 版本；旧版本仍可继续使用命令和文本配置。

### 普通用户节点

普通用户使用独立的 `users` 模板，不会被当作 Bot，也不会触发“阻止 Bot 无协议消息”的防循环
规则。建立 `bot_a -> owner` 等关系后，当账号匹配的用户与该 Bot 对话时，关系类型、称呼、语气、
信任与好感会进入 Bot 的系统上下文。普通用户不会出现在 `botmesh_ask` 可联系目录中，也不能被
插件伪装成 Bot 回答。调情等亲密表达仍受方向性管理员策略和逐次对话边界限制。

## 两个 Bot 的最小配置

假设：

- Bot A：QQ `10001`
- Bot B：QQ `10002`

在承载这两个平台账号的同一个 AstrBot 实例中配置：

```json
[
  {
    "__template_key": "bot",
    "bot_id": "bot_a",
    "display_name": "小A",
    "account_id": "10001",
    "description": "负责统筹与表达",
    "capabilities": ["planning", "writing"],
    "aliases": ["阿A"]
  },
  {
    "__template_key": "bot",
    "bot_id": "bot_b",
    "display_name": "小B",
    "account_id": "10002",
    "description": "负责研究与审查",
    "capabilities": ["research", "review"],
    "aliases": ["研究员B"]
  }
]
```

先在 `group_scopes` 中建立可独立保存的逻辑群：

```json
[
  {
    "__template_key": "group_scope",
    "group_id": "main_group"
  }
]
```

QQ 官方 API 下再用 `group_bindings` 把不同 Bot 看到的 `group_openid` 归入该逻辑群：

```json
[
  {
    "__template_key": "group_binding",
    "group_id": "main_group",
    "bot_id": "bot_a",
    "platform_group_id": "A_看到的_group_openid"
  },
  {
    "__template_key": "group_binding",
    "group_id": "main_group",
    "bot_id": "bot_b",
    "platform_group_id": "B_看到的_group_openid"
  }
]
```

再在 `persona_profiles` 中配置插件人格；群 ID 留空的是全局默认，非空值使用逻辑群 ID：

```json
[
  {
    "__template_key": "persona_profile",
    "bot_id": "bot_a",
    "group_id": "",
    "personality_prompt": "你是小A，性格沉稳，负责统筹与表达……",
    "worldview_prompt": "你生活在近未来都市，重视可验证的事实……"
  },
  {
    "__template_key": "persona_profile",
    "bot_id": "bot_a",
    "group_id": "main_group",
    "personality_prompt": "在这个群中更放松，也更愿意开玩笑……",
    "worldview_prompt": "",
    "self_identity": "小A",
    "soul_identity": "小A",
    "body_identity": "小B",
    "memory_key": "小A",
    "identity_note": "本群处于灵魂互换状态，账号名只用于路由",
    "identity_locked": true
  },
  {
    "__template_key": "persona_profile",
    "bot_id": "bot_b",
    "group_id": "",
    "personality_prompt": "你是小B，负责研究与审查……",
    "worldview_prompt": "你相信严谨的反证比快速赞同更重要……"
  }
]
```

运行时，映射到逻辑群 `main_group` 的 A 使用第二条群人格，并因群世界观留空而继续继承全局世界观；结构化身份也按相同规则逐字段继承。`memory_key` 表示记忆跟随的稳定人物/意识：角色换到另一个账号后，只要新账号使用同一个键，主观认识、承诺和自身发言就会随之接回。它不是账号 ID，修改 Persona 文案也不需要改键。BotMesh Memory 每次请求都会读取这里的当前值，不维护第二份身份配置。`identity_locked` 只阻止聊天历史覆盖身份，管理员保存的新配置始终立即优先。其他群使用全局配置。旧版合并的 `system_prompt` 会自动迁入人格栏。BotMesh 会替换 AstrBot 原生
Persona system prompt，但不会改变当前会话选择的聊天模型。升级时，旧节点上的 `persona_id` 会被
读取一次并自动迁入全局 BotMesh 人格，之后不再作为运行时人格来源。

允许 A 询问 B：

```json
[
  {
    "__template_key": "relation",
    "source_bot_id": "bot_a",
    "target_bot_id": "bot_b",
    "relation_type": "colleague",
    "allow_ask": true,
    "trust": 0.8,
    "tone": "友好、直接，可以指出问题",
    "view_of_target": "把小B视为可靠而敏锐的搭档，但觉得对方偶尔会过度谨慎",
    "share_context": false,
    "address_as": "小B",
    "address_options": ["小B", "B同学", "搭档"],
    "familiarity": 0.8,
    "affinity": 0.6,
    "romantic_interest": 0.0,
    "allow_flirt": false,
    "allow_evolve": true,
    "allow_interject": false,
    "interject_priority": 1.0
  }
]
```

如果还要允许 B 主动询问 A，需要再添加一条独立的 `bot_b -> bot_a` 关系。

## 动态关系

`auto_evolve_relations=true` 时，插件会在收到已验证的 BotMesh 请求、回复或旁听插话后，
从当前 Bot 的视角评估 `self -> 对方` 是否应发生小幅变化。关系由两层组成：

- 基础层：system prompt 或管理员 `relations`，包含关系类型、权限和所有可能称呼。
- 动态层：当前互动模式、当前选用称呼，以及信任、熟悉、好感和浪漫倾向的累计偏移。

统一管理页用一个多行文本框保存每个有向关系的全部可能称呼；每行一个，首行为默认称呼。旧配置的
单值 `address_as` 会自动成为第一项。动态评估可以根据上下文选用库中的其他称呼；如果互动明确建立
了新的稳定称呼，它会立即追加到当前群关系的称呼库、写回配置并立即生效，管理员之后仍可在同一
文本框中审阅、排序或删除。删除称呼并保存会同时撤销对应动态选择，不会从历史状态中复活。

群聊中的动态层也按群隔离：同一对参与者在群 A 积累的好感或紧张模式不会带到群 B。群专属基础
关系存在时优先使用；不存在时回退到全局基础关系，但动态偏移仍记在当前群自己的范围中。

单次变化受 `relation_evolution_max_step` 限制，低于置信度阈值的判断不会落库。当前互动模式
（例如“专业”“玩笑”“紧张”“安慰”“克制”）在 `dynamic_mode_ttl_seconds` 后回到常态，长期
数值仍保留。动态层永远不能修改 `allow_ask`、`share_context`、`allow_interject`、
`allow_flirt` 或基础关系类型。

每次动态关系评估都会优先按当前 Bot 的完整 UMO 只读查询
`astrbot_plugin_chat_history_context` 的持久化群历史，并结合 AstrBot 当前会话历史及 BotMesh 本次运行
期间实际收到的近期群消息。三种来源会去重并交错保留近期记录；历史按 Bot、平台会话和群隔离，
受 `relationship_context_max_chars` 限制。`chat_history_context` 未安装、数据库不存在或读取失败时会
自动使用后两种来源，不影响正常互动。

管理员可用 `/botmesh reset <目标Bot>` 把本 Bot 指向目标的动态状态恢复到基础层；历史变化事件
仍作为审计记录保留。

只有由 BotMesh Agent 路由完成的互动或经过签名验证的兼容协议互动才会推动 Bot 人际关系，普通用户对某个 Bot 的转述不会直接
改变它与另一个 Bot 的长期关系，避免用一句“B 讨厌你”投毒关系表。
动态评估通常会为每次已验证的 Bot 互动增加一次短 JSON 模型调用；不需要时可关闭
`auto_evolve_relations`。

## 旁听插话

要允许 B 在用户和 A 聊天时偶尔加入，需要在独立的 `bot_b -> bot_a` 行开启：

```json
{
  "__template_key": "relation",
  "source_bot_id": "bot_b",
  "target_bot_id": "bot_a",
  "relation_type": "friend",
  "allow_ask": true,
  "allow_interject": true,
  "interject_priority": 1.0,
  "allow_evolve": true,
  "allow_flirt": false
}
```

当用户在群里明确原生 `@A` 时，B 可以旁听，但不会自动说话。流程为：

```text
用户 -> @A + 消息
所有有 B/C/... -> A 插话权限的 Bot 做确定性候选选择
唯一候选 -> 结合自己的有效 BotMesh 人格、持久化会话历史和近期群消息判断相关性；默认 silent
达到 observer_min_score -> 候选发送插话正文 + 已签名 OBS 标记
A -> 验证来源、权限与签名后，将插话放入正常对话上下文
```

同一目标/会话有冷却时间，并有每小时上限；发送记录落库，因此重启不会清空限频。多个 Bot
同时具备旁听资格时，每条用户消息也只有一个候选，不会集体抢话。若 `allow_flirt=false`，
旁听判断会明确禁止把普通友善升级成调情。调情必须在两个方向的关系行都设置
`allow_flirt=true`，单向兴趣或单方配置不够。
只有被选中的候选会调用一次旁听判断模型，其他 Bot 不产生这次判断费用。
旁听历史只查询该旁听 Bot 自己的完整 UMO，不会跨 Bot 或跨群读取。若启用了
`chat_history_context_enabled`，其持久化白名单群记录可在 BotMesh 重启后继续使用；AstrBot 普通会话
历史也可恢复，BotMesh 自己额外收集的近期消息则从本次启动开始累计。

## 从 system prompt 生成关系表

`auto_extract_relations=true` 时，插件会读取每个 Bot 的全局 BotMesh system prompt，
并为每个主体分别抽取关系。例如 A 的 prompt 里写着“把研究员B当作从小认识的朋友”，且
`研究员B` 已登记为 B 的唯一别名，关系表会写入一行：

```text
bot_a -> bot_b | 青梅竹马 | 来源=system_prompt | 置信度=...
```

如果 B 的 prompt 没有表达对 A 的关系，插件不会擅自补出 `bot_b -> bot_a`。每行还可保存
主体对目标的称呼、信任度、熟悉度、好感度、浪漫倾向、语气、证据摘要及 prompt 哈希。

目标映射只接受 `bot_id`、显示名或全网唯一的 `aliases`。无法确定“谁对应谁”的名字进入
“未解析提及”，不会硬猜。关系明细可能来自私有角色设定，因此查询和同步命令均限制为管理员：

```text
/botmesh sync
/botmesh table
```

`/botmesh sync` 是管理员指令，会强制重新读取全部 system prompt；平时自动同步只在 prompt
哈希变化时调用模型。若希望完全确定、节省抽取调用，可直接在人格 prompt 中放结构化区块：

```xml
<botmesh_relations>
[
  {
    "target_bot_id": "bot_b",
    "relation_type": "青梅竹马",
    "address_as": "小B",
    "trust": 0.9,
    "familiarity": 0.95,
    "affinity": 0.8,
    "romantic_interest": 0.6,
    "tone": "熟稔、会互相打趣",
    "confidence": 1.0,
    "evidence": "角色设定明确说明"
  }
]
</botmesh_relations>
```

自由文本抽取会把截断后的全局 BotMesh system prompt 发送给当前会话模型。如果角色设定不能
发送给该模型，请使用上面的结构化区块，或关闭 `auto_extract_relations` 后只维护显式配置。分群
关系建议通过统一管理页选择目标群后执行 AI 自动填写，不会把一个群的人格误写成全局推断关系。

同一 AstrBot 实例中已导入并配置 BotMesh 人格的多个 Bot 都可以抽取各自的出向关系，并作为
彼此可调用的独立 Agent 运行。当前 Agent 直连运行时不支持跨 AstrBot 实例路由。

显式 `relations` 配置是校正层：同一 `source_bot_id -> target_bot_id` 同时存在时，管理员配置
整行覆盖推断行。推断内容默认只塑造关系语气，不授予权限：`inferred_allow_ask=false`，且
`share_context`、`allow_flirt` 永远不会因模型抽取自动开启。即使表里存在浪漫倾向，也不等于
目标同意调情；后续互动仍需由目标 Bot 逐次接受邀请。

填写一个高强度随机 `shared_secret`。Agent 请求本身在进程内直连；该密钥用于 `DSP` 展示防回流帧、
旁听插话帧以及接收旧版本协议消息。例如可以在本地生成：

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

密钥至少需要 32 个 UTF-8 字节，且必须是专门生成的随机值，不要复用 SSH、WebUI 或平台密码。
BotMesh 0.5.0 新发送的消息使用 128-bit HMAC 标签；`accept_legacy_signatures` 默认关闭，只应在
迁移旧实例时短期开启。

无中断轮换步骤：

1. 在 `fallback_shared_secret` 填入新密钥，当前 `shared_secret` 暂不改变。
2. 把新密钥提升为 `shared_secret`，并把旧密钥填入 `fallback_shared_secret`。
3. 确认展示和旁听正常后，在统一管理页的备用密钥框输入 `CLEAR` 清除备用密钥。

发送始终使用当前密钥，接收会同时接受当前和备用密钥。管理 API 不返回密钥原文或密钥哈希。

最后：

- A/B 必须是同一 AstrBot 实例中的平台账号，运行时会按 `platform_id` 和 `event.get_self_id()` 自动选择当前 Bot，
  `self_bot_id` 只作为无法识别账号时的回退值。
- `require_signature = true`。
- `require_native_mention = false`（兼容字段，当前已停用）。
- `block_unframed_bot_messages = true`。

## 使用

### 让模型主动询问

插件会向每轮 LLM 请求注入一条规则：涉及其他 Bot 的观点、偏好、状态、承诺或决定时，
必须调用 `botmesh_ask`，不能代替目标回答。

工具参数：

```text
botmesh_ask(
  target_bot_id,
  question,
  context_summary=""
)
```

只有显式关系边设置了 `share_context=true` 时，`context_summary` 才会发送给目标 Bot；没有关系边
时即使 `default_allow_ask=true` 也不会分享背景。摘要还会受 `max_context_summary_chars` 限制。

`botmesh_ask` 会等待目标 Agent 完成，而不是返回“请稍后等待”。目标 Agent 在深度上限内还会获得
`botmesh_contact_agent`，因此 B 确实可以按自己的判断再联系 A；每次嵌套联系仍独立检查方向性关系、
上下文分享权限、冷却和深度，并由对应 Bot 账号把问答发到群聊。

目标 Agent 使用当前逻辑群的专属 Persona（不存在时才回退全局 Persona），并注入该 Bot 在本群的
全部有向关系及动态状态。运行前加载目标 Bot 对应平台群会话的历史；BotMesh 0.8.8 起还会直接读取
`astrbot_plugin_chat_history_context` 中目标 Bot 当前完整 UMO 的白名单群记录，并补入本次运行期间
实际收到但尚未持久化的近期消息。运行后将请求方、问题和目标 Agent 的回答写回该 Bot 自己的
持久化会话，因此下一次调用 B 时能继续读取 B 的上一轮上下文。

BotMesh 同时向 `chat_history_context` 提供逻辑群选择器和全部绑定别名。管理员在逻辑群任一 Bot
会话执行一次 `/historywatch add`，白名单即可覆盖同一逻辑群内不同 Bot 的平台群 ID，包括 QQ 官方
API 为不同 Bot 返回不同 `group_openid` 的情况。经过签名验证的 BotMesh 展示消息会先提取可见正文
再持久化，隐藏 `DSP` 传输帧不会进入历史上下文。

### 手动测试

`/botmesh ask` 仅限管理员。在 A 所在群发送：

```text
/botmesh ask bot_b 你怎么看这个方案？
```

预期群聊顺序：

```text
A账号：你怎么看这个方案？
B账号：我认为……
```

其他命令：

```text
/botmesh list
/botmesh relation bot_b
/botmesh table
/botmesh sync
/botmesh reset bot_b
/botmesh recent 10
/botmesh help
```

## 主动话题兼容

BotMesh 0.8.7 起向 `astrbot_plugin_proactive_topics` 提供可选的进程内兼容接口。0.8.9 起该接口还接受
主动话题持久化的平台 ID、Bot 账号与原始群 ID；即使定时任务在重启后没有原始事件、UMO 首段只是
适配器类型，也不会把它误当成平台配置 ID。接口会返回解析后的身份供主动话题二次核对，再取得有效群人格、动态关系、可联系目录以及已经整合
`chat_history_context` 的历史。主动生成没有 Agent 工具，因此策略会禁止替其他 Bot 表态。

0.8.10 起，主动话题策略会同时提供 `platform_account_id → target_id → address_as` 精确称呼通讯录。
主动话题没有默认当前对话者：只有历史 `sender_id` 与平台账号完全一致时才允许使用对应专属称呼；
无精确匹配时只能面向全群，禁止按昵称猜测或串用其他关系对象的称呼。

0.8.11 起，主动话题不再自行维护一套简化的 Bot 间回复语义。BotMesh 会把正常回复所用的“当前
发言者、明确对象、逻辑群、有效群 Persona 与当前 Bot 指向对象的单向关系”上下文直接交给兼容层；
模型只选择精确 `target_id`，发送层确定性添加该方向的 `address_as`。接口同时返回 Persona 作用域、
指纹及全关系称呼保留字，供主动话题在发送前拒绝反向或串用称呼。经过签名验证的展示帧也会返回
可信来源 Bot 的账号和显示名，避免平台回流缺少真实发送账号时丢失身份。
该能力通过主动话题兼容契约 v2 暴露；应与主动话题 2.0.3 或更高版本配套使用。

0.8.12 起提供 `dispatch_proactive_topic` 单入口。主动话题插件只提交触发原因、当前 Bot/群身份、
本地近期消息和生成参数；BotMesh 自己解析有效群 Persona、读取持久化历史、使用正常回复共用的
单向关系上下文、调用模型、添加 `当前 Bot → 明确对象` 的 `address_as`、附加签名展示帧并通过当前
Bot 的平台会话发送。主动话题不再生成、渲染、签名或发送 BotMesh 模式的消息。

明确对象只可能是本地近期消息中最后一个经签名展示帧恢复、且 `source_bot_id` 与配置账号同时精确
匹配的 Bot；正文里的姓名、昵称或称呼不会参与身份推断。没有唯一可信对象时只能生成全群话题。
模型若没有返回约定的结构化结果，BotMesh 会直接发送无专属称呼的全群兜底话题，不再让
`/主动话题 测试` 因正文姓名拦截而失败。该派发接口应与主动话题 2.1.0 或更高版本配套使用。

0.8.13 起，主动派发全链路使用统一 `trace_id` 记录集成入口、Bot/群作用域、Persona 作用域和指纹、
可信来源 Bot、最终关系方向、`address_as`、模型草稿渲染原因、签名来源及平台发送路由。合法 JSON
正文若仍自行包含关系网名称、任一方向称呼或本轮历史发送者名称，不会原样发送，也不会让测试失败，
而是在 BotMesh 内降级为无专属称呼的全群话题。应与主动话题 2.1.1 配套使用以获得完整调用链日志。

0.8.14 修正目标候选过严的问题。最新消息不是签名 Bot 时，不再强制只能面向全群；BotMesh 会把
当前 Bot 在当前逻辑群中的全部出向 Bot 关系作为精确候选交给模型，模型只能返回其中一个
`target_id`。最终称呼仍由 BotMesh 按该候选的 `当前 Bot → 目标 Bot` 关系确定性添加，正文姓名不参与
身份解析。签名历史中的最新 Bot 只作为参考目标，不再是唯一可选目标。

0.8.15 修正群 Persona 与平台账号角色不一致时的主动派发身份冲突。平台账号的静态 `display_name`
只用于定位账号节点，不再被描述为当前群角色身份；当前发言者身份以有效群 Persona 为准。候选目标
会显式携带当前方向群关系的 `address_as`，模型只选择 `target_id`，发送层仍按同一条关系确定性添加
称呼，因此灵魂互换等分群角色覆盖不会被账号原名反向覆盖。

0.8.18 将正文姓名校验收窄到消息开头的手写收件人。模型仍不能绕过 `target_id` 和关系称呼库自行
指定发给谁，但可在动作、场景或灵魂互换叙事中正常提及 Persona 角色名，不会再把已经生成好的
完整话题替换成固定短句。管理页的 AI 群人格改写若遇到 Provider 超时或断网，会依次尝试其余
可用对话模型，并在返回草稿中注明实际使用的备用模型。

0.8.16 将单一称呼扩展为可人工审阅的多值称呼库。后台关系卡片使用一个多行文本框保存全部可能
称呼，首行为默认值；动态关系模型可结合上下文选择已有项，或把明确形成的新称呼立即追加到当前群
方向的称呼库。主动派发只接受库中的精确称呼并由发送层校验，普通回复共享同一关系上下文。数据库
自动迁移旧动态状态；管理员删除候选或恢复默认时，其他信任、好感与互动模式状态不受影响。

0.8.17 将同一套身份隔离扩展到 BotMesh 直连询问、递归 Agent 通信、旁听与关系演化。平台账号
`display_name` 只作为路由标签；当前发言者身份只取有效群 Persona，对方称呼只取当前方向的群关系。
签名的 source/target 账号节点 ID 优先于问题正文与历史中的姓名描述，因此灵魂互换群不会在 Bot 互问时
被全局账号身份反向覆盖。

主动正文会使用当前 BotMesh 密钥附加以自己为目标的隐藏 `DSP` 展示帧。所有 Bot 都会把它当作可信
展示而不是新的 Bot 请求，因而不会产生自动回复循环；正文仍可被 BotMesh 的近期历史收集器读取。
主动话题插件不存在时，此接口不会改变 BotMesh 的正常行为。

## 安全与防循环

- Agent 请求与回答在同一进程中直接传递，不从群聊正文反解析，也不会因伪造一条 `@Bot` 消息而执行。
- 群聊展示使用 HMAC-SHA256 签名的不可见 `DSP` 帧；它只让平台回流事件立即停止，不承载 Agent 数据。
- 旁听插话和旧版本兼容接收仍使用已签名协议帧，签名同时覆盖正文内容。
- 所有 BotMesh 出站通道只发送正文和不可见协议帧，不生成 `<@openid>` 或原生 `At` 组件。
- Agent 路由前必须找到目标的 `platform_id`，回复通过该平台实例发送，不能借 A 的账号冒充 B。
- Agent 问答、旧协议回复与旁听插话都只发送正文，不添加原生 `@`。
- 相同互动 ID 的同类事件只处理一次。
- 限制最大互动深度和同一对 Bot 的询问频率。
- `DSP` 回流和已登记 Bot 的普通消息不会进入普通 LLM，防止展示消息形成第二条回复链或无限循环。
- B 生成回答失败时仍会用自己的平台账号返回明确失败状态，不会由 A 猜测 B 的意见。

## 数据

互动审计数据保存在：

```text
data/plugin_data/astrbot_plugin_botmesh/botmesh.sqlite3
```

记录包括互动 ID、A/B 身份、问题、回答、状态、深度和错误信息；同一数据库还保存从
system prompt 推断出的有向关系表、无法解析的名字和每个 BotMesh 人格的 prompt 哈希。
动态关系状态、增量事件和旁听插话审计也保存在该数据库中；互动正文在关系事件表里只保存摘要
哈希，不重复保存原文。

## 已知限制

- MVP 尚未提供拖拽式关系图页面；当前使用配置页、system prompt 抽取和 `/botmesh table`。
- 当前 Agent 路由是同一 AstrBot 进程内直连；A/B 分属不同 AstrBot 实例时会明确报错，不会回退为人设模拟。
- 目标 Bot 会运行完整的 `tool_loop_agent`，但默认只挂载 `botmesh_contact_agent`，不会自动继承主 Agent 的全部工具。
- 旁听 MVP 只识别用户明确原生 `@A` 的群聊消息，不会猜测一条没有提及的普通群消息在跟谁说话。
- 平台/协议端必须把用户 `@A` 的群消息同时投递给旁听 Bot；若只向被提及账号投递，B 无法旁听。
- `block_unframed_bot_messages=true` 时，登记在关系网中的 Bot 不能通过普通消息触发彼此；真实问答必须走 Agent 通道。
