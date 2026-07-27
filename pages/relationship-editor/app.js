const bridge = window.AstrBotPluginPage;

const elements = {
  addBot: document.getElementById("addBotButton"),
  addRelation: document.getElementById("addRelationButton"),
  addUser: document.getElementById("addUserButton"),
  autofill: document.getElementById("autofillButton"),
  autofillProvider: document.getElementById("autofillProviderId"),
  autofillGroup: document.getElementById("autofillGroupId"),
  autofillInstruction: document.getElementById("autofillInstruction"),
  knownGroupIds: document.getElementById("knownGroupIds"),
  discoveryList: document.getElementById("discoveryList"),
  importAll: document.getElementById("importAllButton"),
  nodeCount: document.getElementById("nodeCount"),
  nodeList: document.getElementById("nodeList"),
  createPersonaGroup: document.getElementById("createPersonaGroupButton"),
  createRelationGroup: document.getElementById("createRelationGroupButton"),
  deletePersonaGroup: document.getElementById("deletePersonaGroupButton"),
  deleteRelationGroup: document.getElementById("deleteRelationGroupButton"),
  personaGroupInput: document.getElementById("personaGroupInput"),
  personaGroupScope: document.getElementById("personaGroupScope"),
  personaAdaptAll: document.getElementById("personaAdaptAllButton"),
  personaAdaptCard: document.getElementById("personaAdaptCard"),
  personaAdaptInstruction: document.getElementById("personaAdaptInstruction"),
  personaAdaptProvider: document.getElementById("personaAdaptProviderId"),
  personaList: document.getElementById("personaList"),
  personaScopeNote: document.getElementById("personaScopeNote"),
  relationGroupInput: document.getElementById("relationGroupInput"),
  relationGroupScope: document.getElementById("relationGroupScope"),
  relationList: document.getElementById("relationList"),
  relationScopeNote: document.getElementById("relationScopeNote"),
  renamePersonaGroup: document.getElementById("renamePersonaGroupButton"),
  renameRelationGroup: document.getElementById("renameRelationGroupButton"),
  reload: document.getElementById("reloadButton"),
  save: document.getElementById("saveButton"),
  selfBot: document.getElementById("selfBot"),
  settingsList: document.getElementById("settingsList"),
  status: document.getElementById("status"),
  summary: document.getElementById("workspaceSummary"),
  tabs: [...document.querySelectorAll(".tab")],
  panels: {
    discover: document.getElementById("discoverPanel"),
    nodes: document.getElementById("nodesPanel"),
    personas: document.getElementById("personasPanel"),
    relations: document.getElementById("relationsPanel"),
    settings: document.getElementById("settingsPanel"),
  },
};

const state = {
  bots: [],
  users: [],
  personaProfiles: [],
  relations: [],
  settings: {},
  settingSpecs: [],
  providers: [],
  knownGroupIds: [],
  groupBindings: [],
  groupScopes: [],
  observedGroupBindings: [],
  discoveredBots: [],
  sharedSecretConfigured: false,
  fallbackSharedSecretConfigured: false,
  currentTab: "discover",
  loading: false,
  saving: false,
  autofilling: false,
  personaAdapting: false,
  discoveryLoading: false,
  discoveryInitialized: false,
  activeGroupId: "",
};

const accountIdPlaceholders = new Set(["qq_official", "unknown_selfid", "unknown_self_id"]);

function isPlaceholderAccountId(value) {
  return accountIdPlaceholders.has(String(value || "").trim().toLowerCase());
}

function setStatus(message = "", kind = "") {
  elements.status.textContent = message;
  if (kind) elements.status.dataset.kind = kind;
  else delete elements.status.dataset.kind;
}

function splitList(value) {
  return String(value ?? "")
    .split(/[,，\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function participants() {
  return [
    ...state.bots.map((node) => ({ ...node, node_id: node.bot_id, node_type: "bot" })),
    ...state.users.map((node) => ({ ...node, node_id: node.user_id, node_type: "user" })),
  ];
}

function participantLabel(nodeId) {
  const node = participants().find((item) => item.node_id === nodeId);
  if (!node) return nodeId || "未选择";
  const type = node.node_type === "bot" ? "Bot" : "用户";
  const account = node.account_id ? ` · ${node.account_id}` : "";
  return `${node.display_name || node.node_id} (${node.node_id}${account}) · ${type}`;
}

function makeField(labelText, control, className = "field") {
  const label = document.createElement("label");
  label.className = className;
  const title = document.createElement("span");
  title.textContent = labelText;
  label.append(title, control);
  return label;
}

function textControl(row, field, options = {}) {
  const control = options.multiline
    ? document.createElement("textarea")
    : document.createElement("input");
  control.className = "control";
  if (!options.multiline) control.type = options.type || "text";
  control.value = Array.isArray(row[field]) ? row[field].join(", ") : (row[field] ?? "");
  if (options.placeholder) control.placeholder = options.placeholder;
  if (options.maxLength) control.maxLength = options.maxLength;
  control.addEventListener("input", () => {
    row[field] = options.list ? splitList(control.value) : control.value;
  });
  return control;
}

function nodeIdControl(node, field) {
  const control = document.createElement("input");
  control.className = "control";
  control.maxLength = 64;
  control.value = node[field] ?? "";
  let previous = control.value;
  control.addEventListener("input", () => {
    const next = control.value;
    node[field] = next;
    for (const relation of state.relations) {
      if (relation.source_bot_id === previous) relation.source_bot_id = next;
      if (relation.target_bot_id === previous) relation.target_bot_id = next;
    }
    for (const profile of state.personaProfiles) {
      if (profile.bot_id === previous) profile.bot_id = next;
    }
    for (const binding of state.groupBindings) {
      if (binding.bot_id === previous) binding.bot_id = next;
    }
    if (state.settings.self_bot_id === previous) state.settings.self_bot_id = next;
    previous = next;
  });
  return control;
}

function numberControl(row, field, min, max, step = 1) {
  const control = document.createElement("input");
  control.className = "control";
  control.type = "number";
  control.min = String(min);
  control.max = String(max);
  control.step = String(step);
  control.value = String(row[field] ?? "");
  control.addEventListener("input", () => {
    const value = Number(control.value);
    if (Number.isFinite(value)) row[field] = value;
  });
  return control;
}

function selectControl(row, field, options, emptyLabel = "留空 / 自动") {
  const control = document.createElement("select");
  control.className = "control";
  if (emptyLabel !== null) {
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = emptyLabel;
    control.append(empty);
  }
  for (const item of options) {
    const option = document.createElement("option");
    option.value = item.value;
    option.textContent = item.label;
    control.append(option);
  }
  const current = String(row[field] ?? "");
  if (current && !options.some((item) => item.value === current)) {
    const unknown = document.createElement("option");
    unknown.value = current;
    unknown.textContent = `${current}（当前值）`;
    control.append(unknown);
  }
  control.value = current;
  control.addEventListener("change", () => {
    row[field] = control.value;
  });
  return control;
}

function toggleControl(row, field, labelText) {
  const label = document.createElement("label");
  label.className = "toggle";
  const input = document.createElement("input");
  input.type = "checkbox";
  input.checked = Boolean(row[field]);
  input.addEventListener("change", () => {
    row[field] = input.checked;
  });
  const title = document.createElement("span");
  title.textContent = labelText;
  label.append(input, title);
  return label;
}

function uniqueNodeId(base) {
  const ids = new Set(participants().map((node) => node.node_id));
  const normalized = String(base || "node")
    .replace(/[^A-Za-z0-9_.-]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 58) || "node";
  if (!ids.has(normalized)) return normalized;
  let suffix = 2;
  while (ids.has(`${normalized}_${suffix}`)) suffix += 1;
  return `${normalized}_${suffix}`;
}

function botForCandidate(candidate) {
  const byPlatform = candidate.platform_id
    ? state.bots.find((bot) => bot.platform_id === candidate.platform_id)
    : null;
  if (byPlatform) return byPlatform;
  return candidate.account_id
    ? state.bots.find((bot) => bot.account_id === candidate.account_id)
    : null;
}

function reconcileDiscovery() {
  for (const candidate of state.discoveredBots) {
    const bot = botForCandidate(candidate);
    candidate.imported = Boolean(bot);
    candidate.existing_bot_id = bot?.bot_id || "";
    candidate.sync_needed = Boolean(
      bot
      && !candidate.duplicate_of_platform_id
      && ((candidate.platform_id && !bot.platform_id)
        || (bot.platform_id === candidate.platform_id
          && candidate.account_id
          && bot.account_id !== candidate.account_id)),
    );
  }
}

function importDiscovered(candidate, quiet = false) {
  if (candidate.duplicate_of_platform_id) {
    if (!quiet) setStatus(`${candidate.platform_id} 与 ${candidate.duplicate_of_platform_id} 使用同一账号，已自动归并。`);
    return "duplicate";
  }
  const existing = botForCandidate(candidate);
  if (existing) {
    let changed = false;
    if (candidate.platform_id && !existing.platform_id) {
      existing.platform_id = candidate.platform_id;
      changed = true;
    }
    if (
      existing.platform_id === candidate.platform_id
      && candidate.account_id
      && existing.account_id !== candidate.account_id
      && !state.bots.some((bot) => bot !== existing && bot.account_id === candidate.account_id)
    ) {
      existing.account_id = candidate.account_id;
      changed = true;
    }
    candidate.imported = true;
    candidate.existing_bot_id = existing.bot_id;
    candidate.sync_needed = false;
    if (!quiet) setStatus(
      changed ? `${existing.display_name} 的平台映射已同步；保存后生效。` : `${existing.display_name} 已与该平台同步。`,
      changed ? "success" : "",
    );
    return changed ? "updated" : "unchanged";
  }
  if (!candidate.account_id) {
    if (!quiet) setStatus(`${candidate.platform_id} 尚未暴露机器人账号，需先连接平台或手动添加。`, "error");
    return "unavailable";
  }
  const bot = {
    __template_key: "bot",
    bot_id: uniqueNodeId(candidate.suggested_bot_id),
    display_name: candidate.display_name || candidate.platform_id,
    account_id: candidate.account_id,
    platform_id: candidate.platform_id || "",
    description: `从 AstrBot 平台 ${candidate.platform_id} 自动导入`,
    capabilities: [],
    aliases: [],
  };
  state.bots.push(bot);
  if (!state.settings.self_bot_id) state.settings.self_bot_id = bot.bot_id;
  candidate.imported = true;
  candidate.existing_bot_id = bot.bot_id;
  candidate.sync_needed = false;
  return "added";
}

function renderDiscovery() {
  elements.discoveryList.replaceChildren();
  reconcileDiscovery();
  if (state.discoveryLoading) {
    const loading = document.createElement("div");
    loading.className = "empty-state discovery-loading";
    loading.innerHTML = "<h3>正在后台识别平台…</h3><p>你可以继续编辑其他区域，识别完成后这里会自动更新。</p>";
    elements.discoveryList.append(loading);
  }
  if (!state.discoveredBots.length) {
    if (state.discoveryLoading) return;
    const empty = document.createElement("div");
    empty.className = "empty-state discovery-empty";
    empty.innerHTML = "<h3>没有读取到平台配置</h3><p>请先在 AstrBot 的平台页面添加并启用机器人平台。</p>";
    elements.discoveryList.append(empty);
    return;
  }
  for (const candidate of state.discoveredBots) {
    const card = document.createElement("article");
    card.className = "discovery-card";
    const top = document.createElement("div");
    top.className = "discovery-top";
    const copy = document.createElement("div");
    const title = document.createElement("h3");
    title.textContent = candidate.display_name;
    const meta = document.createElement("p");
    meta.textContent = `${candidate.platform_type} · ${candidate.platform_id}`;
    copy.append(title, meta);
    const badge = document.createElement("span");
    badge.className = `node-badge ${candidate.enabled ? "badge-bot" : ""}`;
    badge.textContent = candidate.enabled ? candidate.status : "已停用";
    top.append(copy, badge);
    const account = document.createElement("div");
    account.className = "account-line";
    account.textContent = candidate.account_id
      ? `账号：${candidate.account_id}`
      : "账号：尚未从平台获得";
    if (candidate.existing_bot_id) account.textContent += ` · Bot：${candidate.existing_bot_id}`;
    if (candidate.duplicate_of_platform_id) account.textContent += ` · 同账号归并至 ${candidate.duplicate_of_platform_id}`;
    const button = document.createElement("button");
    button.className = "button button-secondary button-small";
    button.type = "button";
    button.disabled = state.loading || state.saving || state.autofilling || state.personaAdapting || state.discoveryLoading;
    button.textContent = candidate.duplicate_of_platform_id
      ? "同账号已归并"
      : candidate.sync_needed
        ? "同步映射"
        : candidate.imported
          ? "已同步（查看）"
          : candidate.can_auto_import
            ? "导入为 Bot"
            : "账号未就绪（查看原因）";
    button.addEventListener("click", () => {
      const result = importDiscovered(candidate);
      if (result === "added" || result === "updated") {
        renderParticipantChanges();
        setStatus(result === "added" ? "已加入编辑区；点击“保存全部”后写入 BotMesh。" : "平台映射已同步；点击“保存全部”后写入 BotMesh。", "success");
      }
    });
    card.append(top, account, button);
    elements.discoveryList.append(card);
  }
}

function optionList(items) {
  return items.map((item) => ({ value: item.id, label: item.name || item.id }));
}

function deleteNode(nodeType, index) {
  const rows = nodeType === "bot" ? state.bots : state.users;
  const id = nodeType === "bot" ? rows[index].bot_id : rows[index].user_id;
  rows.splice(index, 1);
  state.relations = state.relations.filter(
    (relation) => relation.source_bot_id !== id && relation.target_bot_id !== id,
  );
  if (nodeType === "bot") {
    state.personaProfiles = state.personaProfiles.filter(
      (profile) => profile.bot_id !== id,
    );
    state.groupBindings = state.groupBindings.filter(
      (binding) => binding.bot_id !== id,
    );
  }
  if (state.settings.self_bot_id === id) state.settings.self_bot_id = "";
  renderAll();
  setStatus(`已移除 ${id} 及其关联关系；保存后生效。`);
}

function makeNodeCard(node, nodeType, index) {
  const isBot = nodeType === "bot";
  const card = document.createElement("article");
  card.className = "node-card";
  const head = document.createElement("header");
  head.className = "card-head";
  const titleWrap = document.createElement("div");
  titleWrap.className = "node-title";
  const badge = document.createElement("span");
  badge.className = `node-badge ${isBot ? "badge-bot" : "badge-user"}`;
  badge.textContent = isBot ? "BOT" : "普通用户";
  const title = document.createElement("strong");
  title.textContent = node.display_name || (isBot ? node.bot_id : node.user_id) || "未命名";
  titleWrap.append(badge, title);
  const remove = document.createElement("button");
  remove.className = "delete-button";
  remove.type = "button";
  remove.textContent = "删除";
  remove.addEventListener("click", () => deleteNode(nodeType, index));
  head.append(titleWrap, remove);

  const body = document.createElement("div");
  body.className = "card-body";
  body.append(
    makeField(isBot ? "Bot ID" : "用户节点 ID", nodeIdControl(node, isBot ? "bot_id" : "user_id")),
    makeField("显示名称", textControl(node, "display_name", { maxLength: 80 })),
    makeField("平台账号 ID", textControl(node, "account_id", { maxLength: 128 })),
  );
  if (isBot) {
    body.append(
      makeField("AstrBot 平台 ID", textControl(node, "platform_id", { maxLength: 128, placeholder: "自动导入时填写" })),
      makeField("能力标签", textControl(node, "capabilities", { list: true, placeholder: "research, writing" })),
    );
  }
  body.append(
    makeField("别名", textControl(node, "aliases", { list: true, placeholder: "多个别名用逗号分隔" }), "field field-wide"),
    makeField("描述", textControl(node, "description", { multiline: true, maxLength: 500 }), "field field-wide"),
  );
  card.append(head, body);
  return card;
}

function renderNodes() {
  const cards = [
    ...state.bots.map((node, index) => makeNodeCard(node, "bot", index)),
    ...state.users.map((node, index) => makeNodeCard(node, "user", index)),
  ];
  elements.nodeList.replaceChildren(...cards);
  if (!cards.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = "<h3>还没有参与者</h3><p>从“自动发现”导入已有 Bot，或手动添加 Bot / 普通用户。</p>";
    elements.nodeList.append(empty);
  }
}

function configuredGroupIds() {
  const values = new Set(state.knownGroupIds.map((value) => String(value || "").trim()).filter(Boolean));
  for (const row of state.groupScopes) if (row.group_id) values.add(String(row.group_id));
  for (const row of state.groupBindings) if (row.group_id) values.add(String(row.group_id));
  for (const row of state.personaProfiles) if (row.group_id) values.add(String(row.group_id));
  for (const row of state.relations) if (row.group_id) values.add(String(row.group_id));
  return [...values].sort((left, right) => left.localeCompare(right, "zh-CN", { numeric: true }));
}

function renderScopeSelect(control, currentValue) {
  const options = [{ value: "", label: "全局默认" }];
  for (const groupId of configuredGroupIds()) options.push({ value: groupId, label: `群 ${groupId}` });
  if (currentValue && !options.some((item) => item.value === currentValue)) {
    options.push({ value: currentValue, label: `群 ${currentValue}` });
  }
  control.replaceChildren(...options.map((item) => {
    const option = document.createElement("option");
    option.value = item.value;
    option.textContent = item.label;
    return option;
  }));
  control.value = currentValue;
}

function defaultPersonaPrompt(bot) {
  return `你是 ${bot.display_name || bot.bot_id}（bot_id=${bot.bot_id}）。请按照这里补充人格、表达方式和边界。`;
}

function makePersonaRow(bot, groupId) {
  const tr = document.createElement("tr");
  let exact = state.personaProfiles.find(
    (row) => row.bot_id === bot.bot_id && String(row.group_id || "") === groupId,
  ) || null;
  const globalProfile = groupId
    ? state.personaProfiles.find((row) => row.bot_id === bot.bot_id && !row.group_id) || null
    : null;

  const identityCell = document.createElement("th");
  identityCell.scope = "row";
  const botName = document.createElement("strong");
  botName.textContent = bot.display_name || bot.bot_id;
  const botId = document.createElement("small");
  botId.textContent = `${bot.bot_id}${bot.account_id ? ` · ${bot.account_id}` : ""}`;
  identityCell.append(botName, botId);

  const mappingCell = document.createElement("td");
  if (!groupId) {
    mappingCell.className = "mapping-not-applicable";
    mappingCell.textContent = "—";
  } else {
    let binding = state.groupBindings.find(
      (row) => row.bot_id === bot.bot_id && String(row.group_id || "") === groupId,
    ) || null;
    const mappingInput = document.createElement("input");
    mappingInput.className = "control platform-group-input";
    mappingInput.maxLength = 128;
    mappingInput.placeholder = "该 Bot 收到的 group_openid";
    mappingInput.value = binding?.platform_group_id || "";
    const listId = `observed-groups-${Math.random().toString(36).slice(2)}`;
    const choices = document.createElement("datalist");
    choices.id = listId;
    const observed = state.observedGroupBindings.filter((row) => row.bot_id === bot.bot_id);
    choices.append(...observed.map((row) => {
      const option = document.createElement("option");
      option.value = row.platform_group_id;
      return option;
    }));
    mappingInput.setAttribute("list", listId);
    mappingInput.addEventListener("input", () => {
      const value = mappingInput.value.trim();
      if (!value) {
        if (binding) {
          const index = state.groupBindings.indexOf(binding);
          if (index >= 0) state.groupBindings.splice(index, 1);
          binding = null;
        }
        return;
      }
      if (!binding) {
        binding = {
          __template_key: "group_binding",
          group_id: groupId,
          bot_id: bot.bot_id,
          platform_group_id: value,
        };
        state.groupBindings.push(binding);
      } else {
        binding.platform_group_id = value;
      }
    });
    const mappingHint = document.createElement("small");
    mappingHint.className = "cell-hint";
    mappingHint.textContent = observed.length
      ? `已发现 ${observed.length} 个，可从输入建议中选`
      : "让该 Bot 在群里收到消息后会自动发现";
    mappingCell.append(mappingInput, choices, mappingHint);
  }

  const sourceCell = document.createElement("td");
  const sourceBadge = document.createElement("span");
  sourceBadge.className = "config-source";
  sourceCell.append(sourceBadge);

  const promptCell = document.createElement("td");
  const prompt = document.createElement("textarea");
  prompt.className = "control persona-table-prompt";
  prompt.maxLength = 50000;
  prompt.placeholder = "填写该 Bot 的身份、性格、表达方式与边界；留空表示尚未配置。";
  prompt.value = exact?.system_prompt || globalProfile?.system_prompt || "";
  promptCell.append(prompt);

  const actionCell = document.createElement("td");
  actionCell.className = "persona-actions";
  const action = document.createElement("button");
  action.type = "button";
  action.className = "button button-quiet button-small";
  actionCell.append(action);
  if (groupId) {
    const aiAction = document.createElement("button");
    aiAction.type = "button";
    aiAction.className = "button button-secondary button-small";
    aiAction.textContent = "AI 从全局改写";
    aiAction.disabled = !globalProfile || state.loading || state.saving || state.autofilling || state.personaAdapting;
    aiAction.title = globalProfile ? "生成该 Bot 的群专属人格与群内称呼草稿" : "请先填写该 Bot 的全局人格";
    aiAction.addEventListener("click", () => void adaptPersonas([bot.bot_id]));
    actionCell.append(aiAction);
  }

  function updatePresentation() {
    const inherited = Boolean(groupId && !exact && globalProfile);
    sourceBadge.className = `config-source ${exact ? "is-exact" : inherited ? "is-inherited" : "is-empty"}`;
    sourceBadge.textContent = exact
      ? (groupId ? "群专属" : "全局人格")
      : inherited ? "继承全局" : "未配置";
    action.textContent = exact
      ? (groupId ? "改用全局" : "删除")
      : (groupId ? "建立群专属" : "建立全局人格");
  }

  function createExact(value) {
    exact = {
      __template_key: "persona_profile",
      bot_id: bot.bot_id,
      group_id: groupId,
      system_prompt: value,
    };
    state.personaProfiles.push(exact);
    updatePresentation();
  }

  prompt.addEventListener("input", () => {
    if (!exact) createExact(prompt.value);
    else exact.system_prompt = prompt.value;
  });
  action.addEventListener("click", () => {
    if (exact) {
      const index = state.personaProfiles.indexOf(exact);
      if (index >= 0) state.personaProfiles.splice(index, 1);
      renderAll();
      setStatus(groupId ? `${bot.display_name || bot.bot_id} 已改为继承全局人格；保存后生效。` : `${bot.display_name || bot.bot_id} 的全局人格已移除；保存后生效。`);
      return;
    }
    const initial = globalProfile?.system_prompt || defaultPersonaPrompt(bot);
    createExact(initial);
    prompt.value = initial;
    prompt.focus();
  });

  updatePresentation();
  tr.append(identityCell, mappingCell, sourceCell, promptCell, actionCell);
  return tr;
}

function renderPersonas() {
  const groupId = state.activeGroupId;
  renderScopeSelect(elements.personaGroupScope, groupId);
  elements.personaAdaptCard.hidden = !groupId;
  elements.personaAdaptAll.disabled = !groupId
    || !state.bots.some((bot) => state.personaProfiles.some((row) => row.bot_id === bot.bot_id && !row.group_id))
    || state.loading || state.saving || state.autofilling || state.personaAdapting;
  elements.personaScopeNote.textContent = groupId
    ? `正在配置逻辑群“${groupId}”。每个 Bot 的平台群 ID 可以不同；映射完成后，它们会使用同一套群人格与关系。`
    : "正在配置全局默认人格。群聊没有专属覆盖时，会使用这里的内容。";
  if (!state.bots.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = "<h3>还没有 Bot</h3><p>请先从“自动发现”导入 Bot，或在“参与者”中添加。</p>";
    elements.personaList.replaceChildren(empty);
    return;
  }
  const tableWrap = document.createElement("div");
  tableWrap.className = "config-table-wrap";
  const table = document.createElement("table");
  table.className = "config-table persona-table";
  table.innerHTML = "<thead><tr><th>机器人</th><th>该 Bot 的平台群 ID</th><th>人格来源</th><th>System Prompt</th><th>操作</th></tr></thead>";
  const tbody = document.createElement("tbody");
  tbody.append(...state.bots.map((bot) => makePersonaRow(bot, groupId)));
  table.append(tbody);
  tableWrap.append(table);
  elements.personaList.replaceChildren(tableWrap);
}

function participantSelect(row, field, index) {
  const options = participants().map((node) => ({
    value: node.node_id,
    label: participantLabel(node.node_id),
  }));
  const control = selectControl(row, field, options, null);
  for (const option of control.options) {
    const other = field === "source_bot_id" ? row.target_bot_id : row.source_bot_id;
    if (option.value === other) option.disabled = true;
  }
  control.addEventListener("change", () => {
    const otherField = field === "source_bot_id" ? "target_bot_id" : "source_bot_id";
    if (row[field] === row[otherField]) {
      row[otherField] = participants().find((node) => node.node_id !== row[field])?.node_id || "";
    }
    renderRelations(index);
  });
  return control;
}

function makeRelationCard(entry, groupId) {
  const { row, index, inherited } = entry;
  const card = document.createElement("article");
  card.className = "relation-card";
  const head = document.createElement("header");
  head.className = "card-head";
  const direction = document.createElement("div");
  direction.className = "direction";
  const source = document.createElement("span");
  source.className = "direction-label";
  source.textContent = participantLabel(row.source_bot_id);
  const arrow = document.createElement("span");
  arrow.className = "direction-arrow";
  arrow.textContent = "→";
  const target = document.createElement("span");
  target.className = "direction-label";
  target.textContent = participantLabel(row.target_bot_id);
  direction.append(source, arrow, target);
  const scope = document.createElement("span");
  scope.className = "node-badge";
  scope.textContent = inherited ? "继承全局" : row.group_id ? `群 ${row.group_id}` : "全局";
  direction.append(scope);
  const remove = document.createElement("button");
  remove.className = "delete-button";
  remove.type = "button";
  remove.textContent = inherited ? "建立群专属" : (groupId && row.group_id ? "删除群专属" : "删除");
  remove.addEventListener("click", () => {
    if (inherited) {
      state.relations.push({ ...row, group_id: groupId });
      setStatus(`${row.source_bot_id} → ${row.target_bot_id} 已建立群 ${groupId} 专属关系；保存后生效。`);
    } else {
      state.relations.splice(index, 1);
    }
    renderAll();
  });
  head.append(direction, remove);

  const body = document.createElement("div");
  body.className = "card-body";
  body.append(
    makeField("关系发起方", participantSelect(row, "source_bot_id", index), "field field-wide"),
    makeField("关系目标", participantSelect(row, "target_bot_id", index), "field field-wide"),
    makeField("关系类型", textControl(row, "relation_type", { maxLength: 80 })),
    makeField("对目标的称呼", textControl(row, "address_as", { maxLength: 80 })),
    makeField("旁听候选权重", numberControl(row, "interject_priority", 0.01, 100, 0.1)),
    makeField("信任度（0–1）", numberControl(row, "trust", 0, 1, 0.05)),
    makeField("熟悉度（0–1）", numberControl(row, "familiarity", 0, 1, 0.05)),
    makeField("好感度（-1–1）", numberControl(row, "affinity", -1, 1, 0.05)),
    makeField("浪漫兴趣（0–1）", numberControl(row, "romantic_interest", 0, 1, 0.05)),
    makeField("面对目标时的语气", textControl(row, "tone", { multiline: true, maxLength: 500 }), "field field-full"),
  );
  const toggles = document.createElement("div");
  toggles.className = "toggle-grid";
  toggles.append(
    toggleControl(row, "allow_ask", "允许询问目标 Bot"),
    toggleControl(row, "share_context", "允许分享背景摘要"),
    toggleControl(row, "allow_evolve", "允许关系动态变化"),
    toggleControl(row, "allow_interject", "允许旁听并插话"),
    toggleControl(row, "allow_flirt", "允许该方向调情"),
  );
  body.append(toggles);
  if (inherited) {
    for (const control of body.querySelectorAll("input, select, textarea")) control.disabled = true;
    card.classList.add("is-inherited");
  }
  card.append(head, body);
  return card;
}

function relationEntriesForGroup(groupId) {
  if (!groupId) {
    return state.relations
      .map((row, index) => ({ row, index, inherited: false }))
      .filter((entry) => !entry.row.group_id);
  }
  const exactByDirection = new Map();
  state.relations.forEach((row, index) => {
    if (String(row.group_id || "") === groupId) {
      exactByDirection.set(`${row.source_bot_id}\u0000${row.target_bot_id}`, { row, index, inherited: false });
    }
  });
  const result = [];
  const included = new Set();
  state.relations.forEach((row, index) => {
    if (row.group_id) return;
    const key = `${row.source_bot_id}\u0000${row.target_bot_id}`;
    result.push(exactByDirection.get(key) || { row, index, inherited: true });
    included.add(key);
  });
  for (const [key, entry] of exactByDirection) if (!included.has(key)) result.push(entry);
  return result;
}

function renderRelations() {
  const groupId = state.activeGroupId;
  renderScopeSelect(elements.relationGroupScope, groupId);
  elements.relationScopeNote.textContent = groupId
    ? `正在查看逻辑群“${groupId}”的有效关系。“继承全局”的卡片只读，点击“建立群专属”后可修改。`
    : "正在配置全局默认关系。群聊没有同方向专属关系时，会继承这里的关系。";
  const cards = relationEntriesForGroup(groupId).map((entry) => makeRelationCard(entry, groupId));
  elements.relationList.replaceChildren(...cards);
  if (!cards.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = `<h3>这个范围还没有关系</h3><p>${groupId ? "可新增群专属关系；没有覆盖的方向会继续使用全局默认。" : "至少添加两个参与者后创建一条有向关系。"}</p>`;
    elements.relationList.append(empty);
  }
  elements.addRelation.disabled = participants().length < 2 || state.loading || state.saving || state.autofilling || state.personaAdapting;
}

function settingOptions(type) {
  if (type === "bot_select") {
    return state.bots.map((bot) => ({ value: bot.bot_id, label: `${bot.display_name || bot.bot_id} (${bot.bot_id})` }));
  }
  if (type === "provider_select") return optionList(state.providers);
  return [];
}

function makeSettingField(spec) {
  const key = spec.key;
  if (spec.type === "bool") return toggleControl(state.settings, key, spec.label);
  let control;
  if (["bot_select", "provider_select"].includes(spec.type)) {
    control = selectControl(state.settings, key, settingOptions(spec.type));
  } else if (spec.type === "int" || spec.type === "float") {
    control = numberControl(state.settings, key, spec.min, spec.max, spec.step || (spec.type === "int" ? 1 : 0.01));
  } else {
    const secretConfigured = key === "shared_secret"
      ? state.sharedSecretConfigured
      : key === "fallback_shared_secret" && state.fallbackSharedSecretConfigured;
    control = textControl(state.settings, key, {
      type: spec.type === "secret" ? "password" : "text",
      placeholder: spec.type === "secret" && secretConfigured
        ? (key === "fallback_shared_secret" ? "已设置；留空保持，输入 CLEAR 清除" : "已设置；留空保持原值")
        : "",
      maxLength: 256,
    });
  }
  return makeField(spec.label, control, "field settings-field");
}

function renderSettings() {
  const grouped = new Map();
  for (const spec of state.settingSpecs) {
    if (spec.inline_only) continue;
    if (!grouped.has(spec.group)) grouped.set(spec.group, []);
    grouped.get(spec.group).push(spec);
  }
  const groups = [];
  for (const [name, specs] of grouped) {
    const group = document.createElement("section");
    group.className = "settings-group";
    const heading = document.createElement("h3");
    heading.textContent = name;
    const grid = document.createElement("div");
    grid.className = "settings-grid";
    grid.append(...specs.map(makeSettingField));
    group.append(heading, grid);
    groups.push(group);
  }
  elements.settingsList.replaceChildren(...groups);
}

function renderAutofillProvider() {
  const options = state.providers.map((item) => ({
    value: item.id,
    label: item.name || item.id,
  }));
  const configured = state.settings.autofill_provider_id || "";
  const current = options.some((item) => item.value === configured)
    ? configured
    : options[0]?.value || "";
  for (const control of [elements.autofillProvider, elements.personaAdaptProvider]) {
    control.replaceChildren();
    for (const item of options) {
      const option = document.createElement("option");
      option.value = item.value;
      option.textContent = item.label;
      control.append(option);
    }
    if (!options.length) {
      const option = document.createElement("option");
      option.value = "";
      option.textContent = "没有可用模型";
      control.append(option);
    }
    control.value = current;
  }
  state.settings.autofill_provider_id = current;
}

function switchTab(tabName) {
  state.currentTab = tabName;
  for (const [name, panel] of Object.entries(elements.panels)) panel.hidden = name !== tabName;
  for (const tab of elements.tabs) tab.classList.toggle("is-active", tab.dataset.tab === tabName);
}

function renderHeader() {
  const total = state.bots.length + state.users.length;
  elements.nodeCount.textContent = String(total);
  elements.summary.textContent = `${state.bots.length} 个 Bot · ${state.users.length} 个普通用户 · ${state.groupScopes.length} 个逻辑群 · ${state.personaProfiles.length} 条人格 · ${state.relations.length} 条关系`;
  const self = state.bots.find((bot) => bot.bot_id === state.settings.self_bot_id);
  elements.selfBot.textContent = `本机 Bot：${self ? `${self.display_name} (${self.bot_id})` : state.settings.self_bot_id || "未设置"}`;
  for (const button of [elements.reload, elements.save, elements.addBot, elements.addUser, elements.addRelation, elements.createPersonaGroup, elements.createRelationGroup, elements.renamePersonaGroup, elements.renameRelationGroup, elements.deletePersonaGroup, elements.deleteRelationGroup, elements.importAll, elements.autofill, elements.personaAdaptAll]) {
    button.disabled = state.loading || state.saving || state.autofilling || state.personaAdapting
      || (button === elements.importAll && state.discoveryLoading)
      || (button === elements.autofill && state.bots.length === 0);
  }
  const hasActiveGroup = Boolean(state.activeGroupId);
  for (const button of [elements.renamePersonaGroup, elements.renameRelationGroup, elements.deletePersonaGroup, elements.deleteRelationGroup]) {
    button.disabled = button.disabled || !hasActiveGroup;
  }
}

function renderAll() {
  renderHeader();
  renderDiscovery();
  renderNodes();
  renderPersonas();
  renderRelations();
  renderSettings();
  renderAutofillProvider();
  switchTab(state.currentTab);
}

function renderParticipantChanges() {
  renderHeader();
  renderDiscovery();
  renderNodes();
  renderPersonas();
  renderRelations();
  renderSettings();
  renderAutofillProvider();
  switchTab(state.currentTab);
}

function emptyRelation(sourceId, targetId) {
  return {
    __template_key: "relation",
    source_bot_id: sourceId,
    target_bot_id: targetId,
    group_id: "",
    relation_type: "acquaintance",
    allow_ask: true,
    trust: 0.5,
    tone: "",
    share_context: false,
    address_as: "",
    familiarity: 0,
    affinity: 0,
    romantic_interest: 0,
    allow_flirt: false,
    allow_interject: false,
    allow_evolve: true,
    interject_priority: 1,
  };
}

function findUnusedDirection(groupId = "") {
  const nodes = participants();
  const used = new Set(state.relations.map((row) => `${row.source_bot_id}\u0000${row.target_bot_id}\u0000${row.group_id || ""}`));
  for (const source of nodes) {
    for (const target of nodes) {
      if (source.node_id !== target.node_id && !used.has(`${source.node_id}\u0000${target.node_id}\u0000${groupId}`)) {
        return [source.node_id, target.node_id];
      }
    }
  }
  return null;
}

function validateWorkspace() {
  const nodes = participants();
  const ids = new Set();
  const accounts = new Set();
  const platforms = new Set();
  for (const [index, node] of nodes.entries()) {
    if (!/^[A-Za-z0-9_.-]{1,64}$/.test(node.node_id || "")) throw new Error(`第 ${index + 1} 个参与者的节点 ID 无效。`);
    if (!node.account_id) throw new Error(`${node.node_id} 缺少平台账号 ID。`);
    if (ids.has(node.node_id)) throw new Error(`节点 ID 重复：${node.node_id}`);
    if (!isPlaceholderAccountId(node.account_id) && accounts.has(node.account_id)) {
      throw new Error(`平台账号重复：${node.account_id}`);
    }
    if (node.node_type === "bot" && node.platform_id) {
      if (platforms.has(node.platform_id)) throw new Error(`AstrBot 平台 ID 重复：${node.platform_id}`);
      platforms.add(node.platform_id);
    }
    ids.add(node.node_id);
    if (!isPlaceholderAccountId(node.account_id)) accounts.add(node.account_id);
  }
  const botIds = new Set(state.bots.map((bot) => bot.bot_id));
  const scopeIds = new Set();
  for (const [index, row] of state.groupScopes.entries()) {
    const groupId = String(row.group_id || "").trim();
    if (!groupId || groupId.length > 128) throw new Error(`第 ${index + 1} 个逻辑群 ID 无效。`);
    if (scopeIds.has(groupId)) throw new Error(`逻辑群 ID 重复：${groupId}`);
    scopeIds.add(groupId);
  }
  const logicalBindings = new Set();
  const platformBindings = new Set();
  for (const [index, row] of state.groupBindings.entries()) {
    const groupId = String(row.group_id || "").trim();
    const botId = String(row.bot_id || "").trim();
    const platformGroupId = String(row.platform_group_id || "").trim();
    if (!groupId || groupId.length > 128) throw new Error(`第 ${index + 1} 条群聊映射的逻辑群 ID 无效。`);
    if (!scopeIds.has(groupId)) throw new Error(`第 ${index + 1} 条群聊映射引用了不存在的逻辑群。`);
    if (!botIds.has(botId)) throw new Error(`第 ${index + 1} 条群聊映射引用了不存在的 Bot。`);
    if (!platformGroupId || platformGroupId.length > 128) throw new Error(`第 ${index + 1} 条群聊映射的平台群 ID 无效。`);
    const logicalKey = `${groupId}\u0000${botId}`;
    const platformKey = `${botId}\u0000${platformGroupId}`;
    if (logicalBindings.has(logicalKey)) throw new Error(`群 ${groupId} 中的 ${botId} 出现了重复映射。`);
    if (platformBindings.has(platformKey)) throw new Error(`${botId} 的平台群 ID ${platformGroupId} 被映射了多次。`);
    logicalBindings.add(logicalKey);
    platformBindings.add(platformKey);
  }
  const personaKeys = new Set();
  for (const [index, row] of state.personaProfiles.entries()) {
    if (!botIds.has(row.bot_id)) throw new Error(`第 ${index + 1} 条人格引用了不存在的 Bot。`);
    if (String(row.group_id || "").length > 128) throw new Error(`第 ${index + 1} 条人格的群 ID 过长。`);
    if (row.group_id && !scopeIds.has(String(row.group_id))) throw new Error(`第 ${index + 1} 条人格引用了不存在的逻辑群。`);
    const prompt = String(row.system_prompt || "").trim();
    if (!prompt) throw new Error(`第 ${index + 1} 条人格内容不能为空。`);
    if (prompt.length > 50000) throw new Error(`第 ${index + 1} 条人格不能超过 50000 个字符。`);
    const key = `${row.bot_id}\u0000${row.group_id || ""}`;
    if (personaKeys.has(key)) throw new Error(`人格重复：${row.bot_id}（${row.group_id ? `群 ${row.group_id}` : "全局"}）`);
    personaKeys.add(key);
  }
  const relations = new Set();
  for (const [index, row] of state.relations.entries()) {
    if (!ids.has(row.source_bot_id) || !ids.has(row.target_bot_id)) throw new Error(`第 ${index + 1} 条关系引用了不存在的参与者。`);
    if (row.source_bot_id === row.target_bot_id) throw new Error(`第 ${index + 1} 条关系不能指向自己。`);
    if (String(row.group_id || "").length > 128) throw new Error(`第 ${index + 1} 条关系的群 ID 过长。`);
    if (row.group_id && !scopeIds.has(String(row.group_id))) throw new Error(`第 ${index + 1} 条关系引用了不存在的逻辑群。`);
    const key = `${row.source_bot_id}\u0000${row.target_bot_id}\u0000${row.group_id || ""}`;
    if (relations.has(key)) throw new Error(`关系重复：${row.source_bot_id} → ${row.target_bot_id}（${row.group_id ? `群 ${row.group_id}` : "全局"}）`);
    relations.add(key);
  }
}

function loadPayload(payload) {
  state.bots = Array.isArray(payload?.bots) ? payload.bots : [];
  state.users = Array.isArray(payload?.users) ? payload.users : [];
  state.relations = Array.isArray(payload?.relations) ? payload.relations : [];
  state.groupBindings = Array.isArray(payload?.group_bindings) ? payload.group_bindings : [];
  state.groupScopes = Array.isArray(payload?.group_scopes) ? payload.group_scopes : [];
  if (state.activeGroupId && !state.groupScopes.some((row) => row.group_id === state.activeGroupId)) {
    state.activeGroupId = "";
  }
  state.observedGroupBindings = Array.isArray(payload?.observed_group_bindings) ? payload.observed_group_bindings : [];
  state.settings = payload?.settings && typeof payload.settings === "object" ? payload.settings : {};
  state.settingSpecs = Array.isArray(payload?.setting_specs) ? payload.setting_specs : [];
  state.personaProfiles = Array.isArray(payload?.persona_profiles) ? payload.persona_profiles : [];
  state.providers = Array.isArray(payload?.providers) ? payload.providers : [];
  state.knownGroupIds = Array.isArray(payload?.known_group_ids) ? payload.known_group_ids : [];
  elements.knownGroupIds.replaceChildren(...state.knownGroupIds.map((groupId) => {
    const option = document.createElement("option");
    option.value = groupId;
    return option;
  }));
  if (Array.isArray(payload?.discovered_bots)) state.discoveredBots = payload.discovered_bots;
  state.sharedSecretConfigured = Boolean(payload?.shared_secret_configured);
  state.fallbackSharedSecretConfigured = Boolean(payload?.fallback_shared_secret_configured);
  reconcileDiscovery();
}

async function loadWorkspace() {
  state.loading = true;
  renderHeader();
  setStatus("正在读取 BotMesh 配置…");
  try {
    const payload = await bridge.apiGet("workspace");
    loadPayload(payload);
    const configurationError = payload.configuration_error || payload.protocol_configuration_error || "";
    setStatus(
      configurationError
        ? `当前配置有错误：${configurationError}`
        : "配置已读取；平台状态将在后台更新。",
      configurationError ? "error" : "success",
    );
  } catch (error) {
    setStatus(`读取失败：${error.message}`, "error");
  } finally {
    state.loading = false;
    renderAll();
    if (!state.discoveryLoading) void loadDiscovery(false);
  }
}

async function loadDiscovery(force = false) {
  if (state.discoveryLoading) return;
  state.discoveryLoading = true;
  renderHeader();
  renderDiscovery();
  if (force) setStatus("正在后台刷新平台状态；当前编辑内容不会被覆盖。");
  try {
    const payload = await bridge.apiGet(force ? "discovery/refresh" : "discovery");
    state.discoveredBots = Array.isArray(payload?.discovered_bots) ? payload.discovered_bots : [];
    reconcileDiscovery();
    let added = 0;
    if (!state.discoveryInitialized && state.bots.length === 0) {
      for (const candidate of state.discoveredBots) {
        if (importDiscovered(candidate, true) === "added") added += 1;
      }
    }
    state.discoveryInitialized = true;
    setStatus(
      added
        ? `已自动把 ${added} 个现有 Bot 加入编辑区；检查后点击“保存全部”。`
        : `平台识别完成：读取到 ${state.discoveredBots.length} 个平台配置。`,
      added ? "success" : "",
    );
  } catch (error) {
    setStatus(`平台识别失败：${error.message}。其他配置仍可正常编辑和保存。`, "error");
  } finally {
    state.discoveryLoading = false;
    renderParticipantChanges();
  }
}

async function saveWorkspace() {
  try {
    validateWorkspace();
  } catch (error) {
    setStatus(error.message, "error");
    return;
  }
  state.saving = true;
  renderHeader();
  setStatus("正在原子保存全部配置并刷新运行图…");
  try {
    const payload = await bridge.apiPost("workspace/save", {
      bots: state.bots,
      users: state.users,
      group_scopes: state.groupScopes,
      group_bindings: state.groupBindings,
      persona_profiles: state.personaProfiles,
      relations: state.relations,
      settings: state.settings,
    });
    loadPayload(payload);
    reconcileDiscovery();
    setStatus("已保存，新的节点、关系和设置已立即应用。", "success");
  } catch (error) {
    setStatus(`保存失败：${error.message}`, "error");
  } finally {
    state.saving = false;
    renderAll();
  }
}

async function autofillWorkspace() {
  try {
    validateWorkspace();
  } catch (error) {
    setStatus(error.message, "error");
    return;
  }
  state.autofilling = true;
  renderHeader();
  setStatus("正在调用所选对话模型，并把 BotMesh 人格作为只读数据分析…");
  try {
    const payload = await bridge.apiPost("workspace/autofill", {
      bots: state.bots,
      users: state.users,
      persona_profiles: state.personaProfiles,
      relations: state.relations,
      provider_id: elements.autofillProvider.value || "",
      group_id: elements.autofillGroup.value || "",
      instruction: elements.autofillInstruction.value || "",
    });
    state.bots = Array.isArray(payload?.bots) ? payload.bots : state.bots;
    state.users = Array.isArray(payload?.users) ? payload.users : state.users;
    state.personaProfiles = Array.isArray(payload?.persona_profiles) ? payload.persona_profiles : state.personaProfiles;
    state.relations = Array.isArray(payload?.relations) ? payload.relations : state.relations;
    const notes = Array.isArray(payload?.notes) && payload.notes.length
      ? `；注意：${payload.notes.join("；")}`
      : "";
    state.currentTab = "nodes";
    setStatus(
      `AI 草稿已生成：补全 ${payload.updated_nodes || 0} 个节点，补全 ${payload.updated_relations || 0} 条已有关系，新增 ${payload.added_relations || 0} 条关系。请检查后点击“保存全部”${notes}`,
      "success",
    );
  } catch (error) {
    setStatus(`AI 自动填写失败：${error.message}`, "error");
  } finally {
    state.autofilling = false;
    renderAll();
  }
}

async function adaptPersonas(botIds) {
  const groupId = state.activeGroupId;
  if (!groupId) {
    setStatus("请先选择一个逻辑群；全局人格不能用该功能覆盖。", "error");
    return;
  }
  try {
    validateWorkspace();
  } catch (error) {
    setStatus(error.message, "error");
    return;
  }
  const targets = [...new Set(botIds)].filter((botId) =>
    state.personaProfiles.some((row) => row.bot_id === botId && !row.group_id),
  );
  if (!targets.length) {
    setStatus("所选 Bot 没有全局人格，请先在“全局默认”范围填写。", "error");
    return;
  }
  const providerId = elements.personaAdaptProvider.value || "";
  const instruction = elements.personaAdaptInstruction.value || "";
  state.personaAdapting = true;
  renderAll();
  setStatus(`正在调用所选模型，为逻辑群“${groupId}”改写 ${targets.length} 个 Bot 的人格与群内称呼…`);
  try {
    const payload = await bridge.apiPost("workspace/persona-adapt", {
      bots: state.bots,
      users: state.users,
      group_scopes: state.groupScopes,
      group_bindings: state.groupBindings,
      persona_profiles: state.personaProfiles,
      relations: state.relations,
      provider_id: providerId,
      group_id: groupId,
      bot_ids: targets,
      instruction,
    });
    state.personaProfiles = Array.isArray(payload?.persona_profiles)
      ? payload.persona_profiles
      : state.personaProfiles;
    state.relations = Array.isArray(payload?.relations)
      ? payload.relations
      : state.relations;
    const updatedBots = Array.isArray(payload?.updated_bot_ids) ? payload.updated_bot_ids.length : 0;
    const updatedAddresses = Array.isArray(payload?.updated_addresses) ? payload.updated_addresses.length : 0;
    const notes = Array.isArray(payload?.notes) && payload.notes.length
      ? `；注意：${payload.notes.join("；")}`
      : "";
    state.currentTab = "personas";
    setStatus(
      `AI 草稿已生成：${updatedBots} 个群专属人格，${updatedAddresses} 个群内称呼。请检查后点击“保存全部”${notes}`,
      "success",
    );
  } catch (error) {
    setStatus(`AI 群人格改写失败：${error.message}`, "error");
  } finally {
    state.personaAdapting = false;
    renderAll();
  }
}

for (const tab of elements.tabs) tab.addEventListener("click", () => switchTab(tab.dataset.tab));
elements.reload.addEventListener("click", () => loadDiscovery(true));
elements.save.addEventListener("click", saveWorkspace);
elements.autofill.addEventListener("click", autofillWorkspace);
elements.autofillProvider.addEventListener("change", () => {
  state.settings.autofill_provider_id = elements.autofillProvider.value;
});
elements.personaAdaptProvider.addEventListener("change", () => {
  state.settings.autofill_provider_id = elements.personaAdaptProvider.value;
});
elements.personaAdaptAll.addEventListener("click", () => {
  const botIds = state.bots
    .filter((bot) => state.personaProfiles.some((row) => row.bot_id === bot.bot_id && !row.group_id))
    .map((bot) => bot.bot_id);
  void adaptPersonas(botIds);
});
elements.importAll.addEventListener("click", () => {
  let count = 0;
  let updated = 0;
  for (const candidate of state.discoveredBots) {
    const result = importDiscovered(candidate, true);
    if (result === "added") count += 1;
    if (result === "updated") updated += 1;
  }
  renderParticipantChanges();
  setStatus(
    count || updated ? `已新增 ${count} 个、同步 ${updated} 个 Bot；请检查后保存。` : "所有可识别 Bot 均已同步。",
    count || updated ? "success" : "",
  );
});
elements.addBot.addEventListener("click", () => {
  state.bots.push({ __template_key: "bot", bot_id: uniqueNodeId("new_bot"), display_name: "新 Bot", account_id: "", platform_id: "", description: "", capabilities: [], aliases: [] });
  state.currentTab = "nodes";
  renderParticipantChanges();
});
elements.addUser.addEventListener("click", () => {
  state.users.push({ __template_key: "user", user_id: uniqueNodeId("user"), display_name: "普通用户", account_id: "", description: "", aliases: [] });
  state.currentTab = "nodes";
  renderParticipantChanges();
});
function createLogicalGroup(kind) {
  const input = kind === "persona" ? elements.personaGroupInput : elements.relationGroupInput;
  const groupId = String(input.value || "").trim();
  if (!groupId) {
    setStatus("请输入一个逻辑群名称，例如“主群”。", "error");
    return;
  }
  if (groupId.length > 128) {
    setStatus("逻辑群名称不能超过 128 个字符。", "error");
    return;
  }
  if (state.groupScopes.some((row) => row.group_id === groupId)) {
    setStatus(`逻辑群“${groupId}”已经存在，请直接从“选择已有群”下拉框打开。`, "error");
    return;
  }
  state.groupScopes.push({ __template_key: "group_scope", group_id: groupId });
  if (!state.knownGroupIds.includes(groupId)) state.knownGroupIds.push(groupId);
  state.activeGroupId = groupId;
  input.value = "";
  renderAll();
  setStatus(`已新建逻辑群“${groupId}”；即使暂未填写人格或映射，保存后也会保留。`, "success");
}

function renameActiveGroup() {
  const current = state.activeGroupId;
  if (!current) return;
  const value = window.prompt("输入新的逻辑群 ID / 名称", current);
  if (value === null) return;
  const next = String(value).trim();
  if (!next || next.length > 128) {
    setStatus("新的逻辑群 ID 必须为 1–128 个字符。", "error");
    return;
  }
  if (next !== current && state.groupScopes.some((row) => row.group_id === next)) {
    setStatus(`逻辑群“${next}”已经存在。`, "error");
    return;
  }
  for (const row of state.groupScopes) if (row.group_id === current) row.group_id = next;
  for (const row of state.groupBindings) if (row.group_id === current) row.group_id = next;
  for (const row of state.personaProfiles) if (row.group_id === current) row.group_id = next;
  for (const row of state.relations) if (row.group_id === current) row.group_id = next;
  state.knownGroupIds = state.knownGroupIds.map((value) => value === current ? next : value);
  state.activeGroupId = next;
  renderAll();
  setStatus(`逻辑群已从“${current}”重命名为“${next}”；保存后生效。`, "success");
}

function deleteActiveGroup() {
  const groupId = state.activeGroupId;
  if (!groupId) return;
  if (!window.confirm(`删除逻辑群“${groupId}”及其专属人格、映射和关系？全局配置不会删除。`)) return;
  state.groupScopes = state.groupScopes.filter((row) => row.group_id !== groupId);
  state.groupBindings = state.groupBindings.filter((row) => row.group_id !== groupId);
  state.personaProfiles = state.personaProfiles.filter((row) => row.group_id !== groupId);
  state.relations = state.relations.filter((row) => row.group_id !== groupId);
  state.knownGroupIds = state.knownGroupIds.filter((value) => value !== groupId);
  state.activeGroupId = "";
  renderAll();
  setStatus(`逻辑群“${groupId}”已从草稿中删除；点击“保存全部”后生效。`);
}

elements.personaGroupScope.addEventListener("change", () => {
  state.activeGroupId = elements.personaGroupScope.value;
  renderAll();
});
elements.relationGroupScope.addEventListener("change", () => {
  state.activeGroupId = elements.relationGroupScope.value;
  renderAll();
});
elements.createPersonaGroup.addEventListener("click", () => createLogicalGroup("persona"));
elements.createRelationGroup.addEventListener("click", () => createLogicalGroup("relation"));
elements.renamePersonaGroup.addEventListener("click", renameActiveGroup);
elements.renameRelationGroup.addEventListener("click", renameActiveGroup);
elements.deletePersonaGroup.addEventListener("click", deleteActiveGroup);
elements.deleteRelationGroup.addEventListener("click", deleteActiveGroup);
elements.addRelation.addEventListener("click", () => {
  const groupId = state.activeGroupId;
  const direction = findUnusedDirection(groupId);
  if (!direction) {
    setStatus("所有可用的有向参与者组合都已存在。", "error");
    return;
  }
  const relation = emptyRelation(direction[0], direction[1]);
  relation.group_id = groupId;
  state.relations.push(relation);
  renderHeader();
  renderRelations();
});

if (!bridge) {
  setStatus("未检测到 AstrBot Plugin Page 桥接环境。请从 BotMesh 插件详情页打开。", "error");
  for (const button of document.querySelectorAll("button")) button.disabled = true;
} else {
  await bridge.ready();
  await loadWorkspace();
}
