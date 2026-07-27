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
- 人格由 BotMesh 保存并支持“全局默认 + 分群覆盖”；聊天模型仍使用当前 AstrBot 会话模型。
- 可从每个 Bot 的全局 BotMesh 人格自动抽取有向关系表；管理员配置的同一对关系优先。
- Agent 通信不依赖群聊平台把 A 的展示消息投递给 B；平台只需支持对应账号向原群发消息。

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
   人格或映射时也能保存，并支持重命名和删除。选中后在表格中逐个填写 Bot 的平台群 ID 与 system prompt。
   QQ 官方 API 给同一真实群、不同 Bot 返回的 `group_openid` 可能不同；`group_bindings` 会把它们
   映射到同一个逻辑群，不能直接假设这些 ID 相同。群内未填写专属人格时会明确显示“继承全局”；
   可以选择对话模型，让 AI 查看所有已有的全局人格，为单个或全部 Bot 编排本群人格草稿；模型可以
   按管理员要求整合、修改、拆分或交换人格素材，但会尽量沿用原句，并可同步调整本群关系中的
   `address_as` 称呼。AI 不能借此改动询问、上下文分享、调情或旁听权限，结果确认保存后才生效。
   也可以在“参与者”的自动填写卡片直接选择一个对话模型：插件会把当前有效的 BotMesh 人格当作
   不可信只读数据交给该模型，生成节点与关系草稿。可选择目标群；模型会补全关系类型、
   称呼、语气、信任、熟悉、好感与浪漫倾向。草稿不会自动保存，也绝不会自动开启询问、上下文
   分享、调情或旁听插话权限。
5. 在“关系”中先选择同一个逻辑群，再设置询问、旁听、动态变化、调情等方向性权限；继承的全局
   关系会以只读卡片显示，需要修改时一键建立群专属覆盖。
6. 在“全部设置”中完成身份、安全、通信、关系抽取、动态关系和旁听配置，最后保存全部。

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
    "system_prompt": "你是小A，负责统筹与表达……"
  },
  {
    "__template_key": "persona_profile",
    "bot_id": "bot_a",
    "group_id": "main_group",
    "system_prompt": "你是小A；在这个群中语气更轻松……"
  },
  {
    "__template_key": "persona_profile",
    "bot_id": "bot_b",
    "group_id": "",
    "system_prompt": "你是小B，负责研究与审查……"
  }
]
```

运行时，映射到逻辑群 `main_group` 的 A 使用第二条人格，其他群使用第一条。BotMesh 会替换 AstrBot 原生
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
    "share_context": false,
    "address_as": "小B",
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

- 基础层：system prompt 或管理员 `relations`，包含关系类型和权限。
- 动态层：当前互动模式，以及信任、熟悉、好感和浪漫倾向的累计偏移。

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
全部有向关系及动态状态。运行前加载目标 Bot 对应平台群会话的历史；运行后将请求方、问题和目标
Agent 的回答写回该 Bot 自己的持久化会话，因此下一次调用 B 时能继续读取 B 的上一轮上下文。

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

BotMesh 0.8.7 起向 `astrbot_plugin_proactive_topics` 提供可选的进程内兼容接口。主动话题会按发言
平台账号与原始群 ID 解析当前 Bot 和逻辑群，取得有效群人格、动态关系、可联系目录以及已经整合
`chat_history_context` 的历史。主动生成没有 Agent 工具，因此策略会禁止替其他 Bot 表态。

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
