const realmColors = ["#d64a4a", "#5f8ee8", "#50ad6f"];
const classRealmOrder = [
  { realmId: 1, realmName: "Albion", label: "알비온", color: realmColors[0] },
  { realmId: 3, realmName: "Hibernia", label: "하이버니아", color: realmColors[2] },
  { realmId: 2, realmName: "Midgard", label: "미드가드", color: realmColors[1] }
];
const realmNames = new Map([
  ["Albion", "알비온"],
  ["Midgard", "미드가드"],
  ["Hibernia", "하이버니아"],
  ["None", "없음"],
  ["Unknown", "없음"]
]);
let latestLive = null;
let latestHistory = null;
let latestActivity = null;
let latestHerald = null;
let latestOperator = null;
let latestOperatorLatency = null;
let latestDynamicQuests = null;
let latestDynamicQuestSeed = null;
let latestDynamicQuestStoryCache = null;
let latestDynamicQuestStoryConfig = null;
let latestDynamicQuestDifficulty = null;
const latestClassHistory = new Map();
const heraldDetailCache = new Map();
let currentHeraldClassRange = "now";
const heraldFilters = {
  character: { search: "", realm: "all", sort: "rp" },
  guild: { search: "", realm: "all", sort: "rp" }
};
const characterRankMetrics = {
  rp: { title: "캐릭터 RP 랭킹", valueLabel: "RP", valueKey: "realmPoints" },
  bp: { title: "캐릭터 BP 랭킹", valueLabel: "BP", valueKey: "bountyPoints" },
  playerKills: { title: "플레이어킬 랭킹", valueLabel: "킬", valueKey: "totalPlayerKills" },
  deathBlows: { title: "데스블로우 랭킹", valueLabel: "데스블로우", valueKey: "totalDeathBlows" },
  soloKills: { title: "솔로킬 랭킹", valueLabel: "솔로킬", valueKey: "totalSoloKills" },
  pvpDeaths: { title: "PvP 사망 랭킹", valueLabel: "사망", valueKey: "pvpDeaths" },
  level: { title: "캐릭터 레벨 랭킹", valueLabel: "레벨", valueKey: "level" },
  recent: { title: "최근 접속 랭킹", valueLabel: "최근", valueKey: "lastPlayed" },
  name: { title: "캐릭터 이름순", valueLabel: "이름", valueKey: "name" }
};

async function getJson(url) {
  const response = await fetch(url, { cache: "no-store" });

  if (!response.ok) {
    throw new Error(`${url} returned ${response.status}`);
  }

  return response.json();
}

async function getJsonWithLatency(url) {
  const startedAt = performance.now();
  const value = await getJson(url);
  return {
    value,
    latencyMs: Math.max(0, Math.round(performance.now() - startedAt))
  };
}

function setText(id, value) {
  const element = document.getElementById(id);

  if (element) {
    element.textContent = value;
  }
}

function resizeCanvas(canvas) {
  const ratio = window.devicePixelRatio || 1;
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  canvas.width = Math.max(1, Math.floor(width * ratio));
  canvas.height = Math.max(1, Math.floor(height * ratio));

  const ctx = canvas.getContext("2d");
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);

  return { ctx, width, height };
}

function clearChart(canvas, title) {
  const { ctx, width, height } = resizeCanvas(canvas);
  ctx.clearRect(0, 0, width, height);

  if (title) {
    ctx.fillStyle = "#aaa399";
    ctx.font = "14px system-ui";
    ctx.fillText(title, 12, 26);
  }

  return { ctx, width, height };
}

function chartError(canvasId, message) {
  const canvas = document.getElementById(canvasId);
  const { ctx } = clearChart(canvas, message);
  ctx.fillStyle = "#c97cc7";
  ctx.fillRect(12, 38, 36, 3);
}

function drawLegend(ctx, series, x, y, maxWidth) {
  ctx.font = "13px system-ui";
  let cursorX = x;
  let cursorY = y;

  series.forEach((item, index) => {
    const label = item.label || `Series ${index + 1}`;
    const itemWidth = 26 + ctx.measureText(label).width + 18;

    if (cursorX > x && cursorX + itemWidth > x + maxWidth) {
      cursorX = x;
      cursorY += 20;
    }

    ctx.fillStyle = item.color || realmColors[index % realmColors.length];
    ctx.fillRect(cursorX, cursorY - 10, 18, 4);
    ctx.fillStyle = "#f1efe8";
    ctx.fillText(label, cursorX + 26, cursorY);
    cursorX += itemWidth;
  });

  return cursorY + 6;
}

function drawLineChart(canvasId, series) {
  const canvas = document.getElementById(canvasId);
  const points = series[0]?.values.length || 0;

  if (points < 1) {
    clearChart(canvas, "데이터가 더 필요합니다");
    return;
  }

  const { ctx, width, height } = clearChart(canvas);
  const padding = 34;
  const values = series.flatMap(item => item.values);
  const max = Math.max(1, ...values);
  const allZero = values.every(value => value <= 0);
  const legendBottom = drawLegend(ctx, series, padding, 20, width - padding * 2);
  const chartTop = Math.max(padding + 16, legendBottom + 14);
  const chartHeight = Math.max(1, height - padding - chartTop);

  ctx.strokeStyle = "#34302a";
  ctx.lineWidth = 1;

  for (let i = 0; i < 4; i++) {
    const y = chartTop + (chartHeight * i / 3);
    ctx.beginPath();
    ctx.moveTo(padding, y);
    ctx.lineTo(width - padding, y);
    ctx.stroke();
  }

  series.forEach((item, index) => {
    ctx.strokeStyle = item.color || realmColors[index % realmColors.length];
    ctx.lineWidth = 2;
    ctx.beginPath();

    item.values.forEach((value, pointIndex) => {
      const x = points === 1
        ? width / 2
        : padding + ((width - padding * 2) * pointIndex / (points - 1));
      const overlapOffset = series.length > 1 ? (index - ((series.length - 1) / 2)) * 4 : 0;
      const zeroOffset = allZero ? index * 9 : overlapOffset;
      const y = height - padding - zeroOffset - (chartHeight * value / max);

      if (pointIndex === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });

    ctx.stroke();

    if (points === 1) {
      const value = item.values[0] || 0;
      const zeroOffset = allZero ? index * 9 : 0;
      const y = height - padding - zeroOffset - (chartHeight * value / max);
      ctx.fillStyle = item.color || realmColors[index % realmColors.length];
      ctx.beginPath();
      ctx.arc(width / 2, y, 4, 0, Math.PI * 2);
      ctx.fill();
    }
  });
}

function drawBarChart(canvasId, labels, values, colors) {
  const canvas = document.getElementById(canvasId);
  if (values.length === 0) {
    clearChart(canvas, "데이터 없음");
    return;
  }

  const { ctx, width, height } = clearChart(canvas);
  const max = Math.max(1, ...values);
  const barWidth = Math.max(12, (width - 40) / Math.max(1, values.length));

  ctx.font = "12px system-ui";

  values.forEach((value, index) => {
    const x = 20 + index * barWidth;
    const barHeight = (height - 70) * value / max;

    ctx.fillStyle = colors[index % colors.length];
    ctx.fillRect(x, height - 34 - barHeight, Math.max(8, barWidth - 8), barHeight);
    ctx.fillStyle = "#f1efe8";
    ctx.fillText(String(value), x, height - 40 - barHeight);
    ctx.fillStyle = "#aaa399";
    ctx.fillText(labels[index].slice(0, 10), x, height - 12);
  });
}

function displayRealmName(name) {
  return realmNames.get(name) || name;
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString("ko-KR");
}

function formatDecimal(value) {
  const number = Number(value || 0);
  return number.toLocaleString("ko-KR", { maximumFractionDigits: number >= 10 ? 0 : 1 });
}

function formatMemoryMb(memoryKb) {
  return formatDecimal(Number(memoryKb || 0) / 1024);
}

function formatBandwidthKbps(value) {
  const kbps = Math.max(0, Number(value || 0));

  if (kbps >= 1024) {
    return `${formatDecimal(kbps / 1024)} MB/s`;
  }

  return `${formatDecimal(kbps)} KB/s`;
}

function formatTime(value) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "-";
  }

  return date.toLocaleTimeString("ko-KR");
}

function formatRealmRank(realmLevel) {
  const value = Math.max(0, Number(realmLevel || 0)) + 10;
  const text = String(value).padStart(2, "0");

  if (value >= 100) {
    return `${text.slice(0, 2)}L${text.slice(2, 3)}`;
  }

  return `${text.slice(0, 1)}L${text.slice(1, 2)}`;
}

function formatDate(value) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "-";
  }

  return date.toLocaleDateString("ko-KR", { month: "short", day: "numeric" });
}

function normalizeSearch(value) {
  return String(value || "").trim().toLocaleLowerCase("ko-KR");
}

function compareText(left, right) {
  return String(left || "").localeCompare(String(right || ""), "ko-KR");
}

function sortableTime(value) {
  const time = new Date(value).getTime();
  return Number.isNaN(time) ? 0 : time;
}

function getPeakPlayers24h() {
  const historyPeak = Math.max(0, ...(latestHistory?.points || []).map(point => Number(point.totalPlayers || 0)));
  return Math.max(Number(latestLive?.totalPlayers || 0), historyPeak);
}

function updatePeakPlayers24h() {
  setText("peakPlayers24h", getPeakPlayers24h());
}

function getCharacterRankMetric() {
  return characterRankMetrics[heraldFilters.character.sort] || characterRankMetrics.rp;
}

function getCharacterRankNumber(item, key) {
  return Number(item?.[key] || 0);
}

function compareCharacterRank(left, right, key) {
  return getCharacterRankNumber(right, key) - getCharacterRankNumber(left, key)
    || Number(right.realmPoints || 0) - Number(left.realmPoints || 0)
    || Number(right.realmLevel || 0) - Number(left.realmLevel || 0)
    || compareText(left.name, right.name);
}

function getCharacterRankValue(item) {
  const metric = getCharacterRankMetric();

  switch (heraldFilters.character.sort) {
    case "recent":
      return formatDate(item.lastPlayed);
    case "name":
      return item.name || "-";
    case "level":
      return `Lv ${formatNumber(item.level)}`;
    default:
      return `${formatNumber(item[metric.valueKey])} ${metric.valueLabel}`;
  }
}

function getRealmInfo(realmId, realmName) {
  return classRealmOrder.find(item => item.realmId === Number(realmId))
    || classRealmOrder.find(item => item.realmName === realmName)
    || { realmId: Number(realmId || 0), realmName: realmName || "Unknown", label: displayRealmName(realmName || "Unknown"), color: "#d7af54" };
}

function setEmptyState(targetId, message) {
  const target = document.getElementById(targetId);

  if (!target) {
    return;
  }

  target.innerHTML = "";

  const empty = document.createElement("p");
  empty.className = "empty-state";
  empty.textContent = message;
  target.appendChild(empty);
}

function createMetric(label, value) {
  const metric = document.createElement("div");
  metric.className = "operator-metric";

  const labelElement = document.createElement("span");
  labelElement.textContent = label;

  const valueElement = document.createElement("strong");
  valueElement.textContent = value;

  metric.append(labelElement, valueElement);
  return metric;
}

function formatPercent(value) {
  return `${formatDecimal(Number(value || 0) * 100)}%`;
}

function startModeLabel(value) {
  if (value === "NpcOffer" || value === 0) {
    return "NPC";
  }

  if (value === "WorldOffer" || value === 1) {
    return "월드";
  }

  if (value === "AutoAccept" || value === 2) {
    return "자동";
  }

  return String(value ?? "-");
}

function realmLabelFromTags(tags, fallback) {
  const tag = (tags || []).find(item => String(item || "").startsWith("realm:"));
  return tag ? displayRealmName(String(tag).slice(6)) : displayRealmName(fallback || "Unknown");
}

function qualityLabel(item) {
  const score = Number(item?.storyQualityScore ?? item?.quality?.totalScore ?? 0);
  const provider = item?.storyProvider || item?.provider || "-";
  const model = item?.storyModel || item?.model || "-";
  return `${formatNumber(score)}점 · ${provider} · ${model}`;
}

function createDynamicQuestRow(title, meta, detail, status) {
  const row = document.createElement("div");
  row.className = "dynamic-quest-row";

  const badge = document.createElement("span");
  badge.className = "dynamic-quest-badge";
  badge.textContent = status || "-";

  const main = document.createElement("div");
  main.className = "dynamic-quest-main";

  const heading = document.createElement("strong");
  heading.textContent = title || "-";

  const metaElement = document.createElement("span");
  metaElement.textContent = meta || "-";

  main.append(heading, metaElement);

  if (detail) {
    const detailElement = document.createElement("p");
    detailElement.textContent = detail;
    main.appendChild(detailElement);
  }

  row.append(badge, main);
  return row;
}

function renderDynamicQuestOffers(snapshot) {
  const list = document.getElementById("dynamicQuestOfferList");
  if (!list) {
    return;
  }

  const quests = snapshot?.quests || [];
  if (quests.length === 0) {
    setEmptyState("dynamicQuestOfferList", "현재 활성 동적 퀘스트가 없습니다");
    return;
  }

  list.innerHTML = "";
  quests.slice(0, 8).forEach((quest) => {
    const mode = startModeLabel(quest.startMode);
    const realm = realmLabelFromTags(quest.tags, quest.realmName);
    const target = quest.targetName ? `${quest.targetName} ${formatNumber(quest.targetCount || 1)}마리` : "-";
    const steps = Array.isArray(quest.nodes) ? `${formatNumber(quest.nodes.length)}스텝` : "-";
    const branch = (quest.tags || []).some(tag => String(tag).includes("branch:")) ? "분기" : "단선";
    list.appendChild(createDynamicQuestRow(
      quest.title,
      `${realm} · ${quest.startNpcName || "NPC 없음"} · ${target}`,
      `${steps} · ${branch} · ${quest.worldRevision || "world"}`,
      mode));
  });
}

function renderDynamicQuestStoryList(cache) {
  const list = document.getElementById("dynamicQuestStoryList");
  if (!list) {
    return;
  }

  const items = cache?.items || [];
  if (items.length === 0) {
    setEmptyState("dynamicQuestStoryList", "캐시된 스토리가 없습니다");
    return;
  }

  list.innerHTML = "";
  items.slice(0, 8).forEach((item) => {
    const scenes = (item.narrativeScenes || []).length;
    const beats = (item.presentationBeats || []).length;
    const mode = startModeLabel(item.startMode);
    const realm = displayRealmName(item.realm || item.realmName || item.preferredRealm || "Unknown");
    const target = item.targetNameHint || item.targetName || "-";
    list.appendChild(createDynamicQuestRow(
      item.title || item.templateId,
      `${realm} · ${target} · ${qualityLabel(item)}`,
      `장면 ${formatNumber(scenes)}개 · 연출 ${formatNumber(beats)}개 · ${item.templateId || ""}`,
      mode));
  });
}

function renderDynamicQuestDifficultyRuns(difficulty) {
  const list = document.getElementById("dynamicQuestDifficultyRuns");
  if (!list) {
    return;
  }

  const runs = difficulty?.latestRuns || [];
  if (runs.length === 0) {
    setEmptyState("dynamicQuestDifficultyRuns", "아직 동적 퀘스트 더미 리포트가 없습니다");
    return;
  }

  list.innerHTML = "";
  runs.forEach((run) => {
    const risk = Number(run.deaths || 0) > 0 || Number(run.targetTimeouts || 0) > 0
      ? "주의"
      : "정상";
    list.appendChild(createDynamicQuestRow(
      run.name,
      `${formatPercent(run.completionRate)} 완료 · ${formatNumber(run.rows)}행 · ${formatDecimal(run.avgElapsedSeconds)}초`,
      `사망 ${formatNumber(run.deaths)} · 타겟제거 ${formatNumber(run.targetRemoved)} · 타임아웃 ${formatNumber(run.targetTimeouts)} · ${run.path || ""}`,
      risk));
  });
}

function applyDynamicQuestOps() {
  const quests = latestDynamicQuests?.quests || [];
  const seed = latestDynamicQuestSeed || {};
  const cache = latestDynamicQuestStoryCache || {};
  const config = latestDynamicQuestStoryConfig || {};
  const difficulty = latestDynamicQuestDifficulty || {};

  setText("dynamicQuestSeedUpdatedAt", seed.startedAt || seed.completedAt ? `시드 ${formatTime(seed.completedAt || seed.startedAt)}` : "Seed");
  const seedMetrics = document.getElementById("dynamicQuestSeedMetrics");
  if (seedMetrics) {
    const autoAccept = quests.filter(quest => quest.startMode === 2 || quest.startMode === "AutoAccept").length;
    const worldOffer = quests.filter(quest => quest.startMode === 1 || quest.startMode === "WorldOffer").length;
    const npcOffer = quests.filter(quest => quest.startMode === 0 || quest.startMode === "NpcOffer").length;
    seedMetrics.innerHTML = "";
    seedMetrics.append(
      createMetric("활성 퀘스트", `${formatNumber(quests.length)}개`),
      createMetric("자동/NPC/월드", `${formatNumber(autoAccept)}/${formatNumber(npcOffer)}/${formatNumber(worldOffer)}`),
      createMetric("이번 시드 생성", `${formatNumber(seed.created)}개`),
      createMetric("캐시 오퍼", `${formatNumber(seed.storyCacheOffered)}개`),
      createMetric("취소", `${formatNumber(seed.cancelledByWorldRevision)}개`),
      createMetric("프리필", `${formatNumber(seed.storyCachePrefilled)}개`));
  }
  renderDynamicQuestOffers(latestDynamicQuests);

  const providerOrder = config.providerOrder || "-";
  setText("dynamicQuestStoryProvider", providerOrder);
  const storyMetrics = document.getElementById("dynamicQuestStoryMetrics");
  if (storyMetrics) {
    const maxTemplates = Number(config.cache?.maxTemplates || 0);
    const totalActive = Number(cache.totalActive || 0);
    const fillRate = maxTemplates > 0 ? totalActive / maxTemplates : 0;
    storyMetrics.innerHTML = "";
    storyMetrics.append(
      createMetric("캐시", `${formatNumber(totalActive)}/${formatNumber(maxTemplates)}`),
      createMetric("오퍼 가능", `${formatNumber(cache.readyActive)}개`),
      createMetric("충전률", formatPercent(fillRate)),
      createMetric("장면/연출 없음", `${formatNumber(cache.missingNarrative)}/${formatNumber(cache.missingPresentation)}`),
      createMetric("최저 기준", `${formatNumber(config.minimumScore)}점`),
      createMetric("Gemini 모델", config.gemini?.model || "-"));
  }
  renderDynamicQuestStoryList(cache);

  setText("dynamicQuestDifficultyUpdatedAt", difficulty.updatedAt ? `갱신 ${formatTime(difficulty.updatedAt)}` : "CSV");
  const difficultyMetrics = document.getElementById("dynamicQuestDifficultyMetrics");
  if (difficultyMetrics) {
    difficultyMetrics.innerHTML = "";
    difficultyMetrics.append(
      createMetric("완료율", formatPercent(difficulty.completionRate)),
      createMetric("성공률", formatPercent(difficulty.okRate)),
      createMetric("평균 시간", `${formatDecimal(difficulty.avgElapsedSeconds)}초`),
      createMetric("사망", `${formatNumber(difficulty.deaths)}회`),
      createMetric("타임아웃", `${formatNumber(difficulty.targetTimeouts)}회`),
      createMetric("소스", `${formatNumber(difficulty.sourceFileCount)}개`));
  }
  renderDynamicQuestDifficultyRuns(difficulty);
}

function statusLabel(status) {
  switch (status) {
    case "danger":
      return "위험";
    case "warning":
      return "주의";
    case "ok":
      return "정상";
    default:
      return status || "-";
  }
}

function getRealmPlayers(realms, realmInfo) {
  const realm = (realms || []).find(item => Number(item.realmId) === realmInfo.realmId)
    || (realms || []).find(item => item.realmName === realmInfo.realmName);

  return Number(realm?.players || 0);
}

function getRealmClasses(classes, realmInfo, options = {}) {
  const valueKey = options.valueKey || "players";

  return (classes || [])
    .filter(item => Number(item.realmId) === realmInfo.realmId || item.realmName === realmInfo.realmName)
    .map(item => ({
      className: item.className || `Class ${item.classId || ""}`.trim(),
      players: Math.max(0, Number(item[valueKey] ?? item.players ?? 0)),
      peakPlayers: Math.max(0, Number(item.peakPlayers || 0))
    }))
    .filter(item => item.players > 0)
    .sort((left, right) => right.players - left.players || left.className.localeCompare(right.className));
}

function renderClassRealmGrid(live, message, targetId = "classRealmGrid", options = {}) {
  const grid = document.getElementById(targetId);

  if (!grid) {
    return;
  }

  grid.innerHTML = "";

  if (message) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = message;
    grid.appendChild(empty);
    return;
  }

  const realms = live?.realms || [];
  const classes = live?.classes || [];
  const emptyText = options.emptyText || "접속 중인 직업 없음";

  classRealmOrder.forEach((realmInfo) => {
    const column = document.createElement("section");
    column.className = "class-realm-column";
    column.style.setProperty("--realm-color", realmInfo.color);
    column.setAttribute("aria-label", `${realmInfo.label} 직업 분포`);

    const heading = document.createElement("div");
    heading.className = "class-realm-heading";

    const name = document.createElement("span");
    name.className = "class-realm-name";
    name.textContent = realmInfo.label;

    const total = document.createElement("span");
    total.className = "class-realm-total";
    total.textContent = options.totalText
      ? options.totalText(getRealmClasses(classes, realmInfo, options), realmInfo)
      : `${formatNumber(getRealmPlayers(realms, realmInfo))}명`;

    heading.append(name, total);
    column.appendChild(heading);

    const realmClasses = getRealmClasses(classes, realmInfo, options);

    if (realmClasses.length === 0) {
      const empty = document.createElement("p");
      empty.className = "empty-state";
      empty.textContent = emptyText;
      column.appendChild(empty);
      grid.appendChild(column);
      return;
    }

    const maxPlayers = Math.max(1, ...realmClasses.map(item => item.players));
    const list = document.createElement("div");
    list.className = "class-list";

    realmClasses.forEach((item) => {
      const row = document.createElement("div");
      row.className = "class-row";

      const main = document.createElement("div");
      main.className = "class-row-main";

      const className = document.createElement("span");
      className.className = "class-name";
      className.title = item.className;
      className.textContent = item.className;

      const count = document.createElement("span");
      count.className = "class-count";
      count.textContent = options.valueText
        ? options.valueText(item)
        : `${formatNumber(item.players)}명`;

      const track = document.createElement("div");
      track.className = "class-bar-track";

      const fill = document.createElement("div");
      fill.className = "class-bar-fill";
      fill.style.setProperty("--bar-width", `${Math.max(3, item.players / maxPlayers * 100).toFixed(1)}%`);

      main.append(className, count);
      track.appendChild(fill);
      row.append(main, track);
      list.appendChild(row);
    });

    column.appendChild(list);
    grid.appendChild(column);
  });
}

function renderHeraldSummary(herald) {
  const grid = document.getElementById("heraldRealmSummary");

  if (!grid) {
    return;
  }

  grid.innerHTML = "";

  const summaries = herald?.realmSummaries || [];

  if (summaries.length === 0) {
    setEmptyState("heraldRealmSummary", "해럴드 데이터를 불러오는 중입니다");
    return;
  }

  classRealmOrder.forEach((realmInfo) => {
    const summary = summaries.find(item => Number(item.realmId) === realmInfo.realmId) || {};
    const section = document.createElement("section");
    section.className = "herald-realm-summary";
    section.style.setProperty("--realm-color", realmInfo.color);

    const heading = document.createElement("div");
    heading.className = "herald-realm-heading";

    const label = document.createElement("span");
    label.className = "realm-label";
    label.textContent = realmInfo.label;

    const online = document.createElement("span");
    online.className = "herald-online";
    online.textContent = `${formatNumber(summary.onlinePlayers)}명`;

    heading.append(label, online);
    section.appendChild(heading);

    const metrics = document.createElement("div");
    metrics.className = "herald-metrics";
    [
      ["캐릭터", summary.characterCount],
      ["50레벨", summary.level50Characters],
      ["길드", summary.guilds],
      ["누적 RP", summary.realmPoints]
    ].forEach(([labelText, value]) => {
      const metric = document.createElement("div");
      metric.className = "herald-metric";

      const metricLabel = document.createElement("span");
      metricLabel.textContent = labelText;

      const metricValue = document.createElement("strong");
      metricValue.textContent = formatNumber(value);

      metric.append(metricLabel, metricValue);
      metrics.appendChild(metric);
    });

    section.appendChild(metrics);
    grid.appendChild(section);
  });
}

function renderHeraldWar(war) {
  const dfOwner = document.getElementById("heraldDfOwner");
  const summaryGrid = document.getElementById("heraldWarSummary");
  const relicList = document.getElementById("heraldRelics");

  if (dfOwner) {
    const realmInfo = getRealmInfo(war?.darknessFallsOwnerRealmId, war?.darknessFallsOwnerRealmName);
    dfOwner.textContent = `DF ${realmInfo.label || "-"}`;
  }

  if (summaryGrid) {
    summaryGrid.innerHTML = "";

    const summaries = war?.realmSummaries || [];

    if (summaries.length === 0) {
      setEmptyState("heraldWarSummary", "전황 데이터를 불러오는 중입니다");
    } else {
      classRealmOrder.forEach((realmInfo) => {
        const summary = summaries.find(item => Number(item.realmId) === realmInfo.realmId) || {};
        const section = document.createElement("section");
        section.className = "war-realm-summary";
        section.style.setProperty("--realm-color", realmInfo.color);

        const heading = document.createElement("div");
        heading.className = "herald-realm-heading";

        const label = document.createElement("span");
        label.className = "realm-label";
        label.textContent = realmInfo.label;

        const siege = document.createElement("span");
        siege.className = "herald-online";
        siege.textContent = `${formatNumber(summary.keepsUnderSiege)} 공성`;

        heading.append(label, siege);
        section.appendChild(heading);

        const metrics = document.createElement("div");
        metrics.className = "war-metrics";
        [
          ["킵", summary.keeps],
          ["타워", summary.towers],
          ["유물", summary.relics],
          ["공성", summary.keepsUnderSiege]
        ].forEach(([labelText, value]) => {
          const metric = document.createElement("div");
          metric.className = "war-metric";

          const metricLabel = document.createElement("span");
          metricLabel.textContent = labelText;

          const metricValue = document.createElement("strong");
          metricValue.textContent = formatNumber(value);

          metric.append(metricLabel, metricValue);
          metrics.appendChild(metric);
        });

        section.appendChild(metrics);
        summaryGrid.appendChild(section);
      });
    }
  }

  if (!relicList) {
    return;
  }

  relicList.innerHTML = "";
  const relics = war?.relics || [];

  if (relics.length === 0) {
    setEmptyState("heraldRelics", "유물 데이터 없음");
    return;
  }

  relics.forEach((relic) => {
    const currentRealm = getRealmInfo(relic.currentRealmId, relic.currentRealmName);
    const originalRealm = getRealmInfo(relic.originalRealmId, relic.originalRealmName);
    const row = document.createElement("div");
    row.className = "relic-row";
    row.style.setProperty("--realm-color", currentRealm.color);

    const realm = document.createElement("span");
    realm.className = "rank-pos realm-label";
    realm.textContent = currentRealm.label.slice(0, 2);

    const main = document.createElement("div");
    main.className = "relic-main";

    const name = document.createElement("span");
    name.className = "relic-name";
    name.textContent = relic.name || "Relic";
    name.title = name.textContent;

    const meta = document.createElement("span");
    meta.className = "relic-meta";
    meta.textContent = `${originalRealm.label} 원소유 · ${relic.type || "-"}`;

    const value = document.createElement("span");
    value.className = "relic-value";
    value.textContent = relic.isCaptured ? "탈취" : "보유";

    main.append(name, meta);
    row.append(realm, main, value);
    relicList.appendChild(row);
  });
}

function renderRankList(targetId, items, renderItem, emptyText) {
  const list = document.getElementById(targetId);

  if (!list) {
    return;
  }

  list.innerHTML = "";

  if (!items || items.length === 0) {
    setEmptyState(targetId, emptyText);
    return;
  }

  items.slice(0, 10).forEach((item) => {
    const row = renderItem.detailKind ? document.createElement("button") : document.createElement("div");
    row.className = "rank-row";

    if (renderItem.detailKind) {
      row.type = "button";
      row.dataset.detailKind = renderItem.detailKind;
      row.dataset.detailName = renderItem.name(item);
      row.setAttribute("aria-label", `${renderItem.name(item)} 상세 보기`);
      row.addEventListener("click", () => loadHeraldDetail(renderItem.detailKind, renderItem.name(item)));
    }

    const position = document.createElement("span");
    position.className = "rank-pos";
    position.textContent = `#${item.rank || ""}`;

    const main = document.createElement("div");
    main.className = "rank-main";

    const name = document.createElement("span");
    name.className = "rank-name";
    name.textContent = renderItem.name(item);
    name.title = name.textContent;

    const meta = document.createElement("span");
    meta.className = "rank-meta";
    meta.textContent = renderItem.meta(item);
    meta.title = meta.textContent;

    const value = document.createElement("span");
    value.className = "rank-value";
    value.textContent = renderItem.value(item);

    main.append(name, meta);
    row.append(position, main, value);
    list.appendChild(row);
  });
}

function getFilteredCharacterRanks(herald) {
  const filter = heraldFilters.character;
  const search = normalizeSearch(filter.search);
  const realm = filter.realm;

  return (herald?.topCharacters || [])
    .filter(item => realm === "all" || String(item.realmId) === realm)
    .filter(item => {
      if (!search) {
        return true;
      }

      return [
        item.name,
        item.guildName,
        item.className,
        item.realmName,
        getRealmInfo(item.realmId, item.realmName).label
      ].some(value => normalizeSearch(value).includes(search));
    })
    .sort((left, right) => {
      switch (filter.sort) {
        case "bp":
          return compareCharacterRank(left, right, "bountyPoints");
        case "playerKills":
          return compareCharacterRank(left, right, "totalPlayerKills");
        case "deathBlows":
          return compareCharacterRank(left, right, "totalDeathBlows");
        case "soloKills":
          return compareCharacterRank(left, right, "totalSoloKills");
        case "pvpDeaths":
          return compareCharacterRank(left, right, "pvpDeaths");
        case "level":
          return Number(right.level || 0) - Number(left.level || 0)
            || Number(right.realmLevel || 0) - Number(left.realmLevel || 0)
            || Number(right.realmPoints || 0) - Number(left.realmPoints || 0);
        case "recent":
          return sortableTime(right.lastPlayed) - sortableTime(left.lastPlayed)
            || Number(right.realmPoints || 0) - Number(left.realmPoints || 0);
        case "name":
          return compareText(left.name, right.name);
        default:
          return Number(right.realmPoints || 0) - Number(left.realmPoints || 0)
            || Number(right.realmLevel || 0) - Number(left.realmLevel || 0)
            || compareText(left.name, right.name);
      }
    })
    .map((item, index) => ({ ...item, rank: index + 1 }));
}

function getFilteredGuildRanks(herald) {
  const filter = heraldFilters.guild;
  const search = normalizeSearch(filter.search);
  const realm = filter.realm;

  return (herald?.topGuilds || [])
    .filter(item => realm === "all" || String(item.realmId) === realm)
    .filter(item => {
      if (!search) {
        return true;
      }

      return [
        item.guildName,
        item.realmName,
        getRealmInfo(item.realmId, item.realmName).label
      ].some(value => normalizeSearch(value).includes(search));
    })
    .sort((left, right) => {
      switch (filter.sort) {
        case "bp":
          return Number(right.bountyPoints || 0) - Number(left.bountyPoints || 0)
            || Number(right.realmPoints || 0) - Number(left.realmPoints || 0);
        case "level":
          return Number(right.guildLevel || 0) - Number(left.guildLevel || 0)
            || Number(right.realmPoints || 0) - Number(left.realmPoints || 0);
        case "name":
          return compareText(left.guildName, right.guildName);
        default:
          return Number(right.realmPoints || 0) - Number(left.realmPoints || 0)
            || Number(right.bountyPoints || 0) - Number(left.bountyPoints || 0)
            || compareText(left.guildName, right.guildName);
      }
    })
    .map((item, index) => ({ ...item, rank: index + 1 }));
}

function renderDetailMetrics(metrics) {
  const grid = document.createElement("div");
  grid.className = "detail-metrics";

  metrics.forEach(([labelText, valueText]) => {
    const metric = document.createElement("div");
    metric.className = "detail-metric";

    const label = document.createElement("span");
    label.textContent = labelText;

    const value = document.createElement("strong");
    value.textContent = valueText;
    value.title = valueText;

    metric.append(label, value);
    grid.appendChild(metric);
  });

  return grid;
}

function renderDetailHero(title, meta, score) {
  const hero = document.createElement("div");
  hero.className = "detail-hero";

  const main = document.createElement("div");
  main.className = "rank-main";

  const name = document.createElement("div");
  name.className = "detail-name";
  name.textContent = title;

  const metaText = document.createElement("div");
  metaText.className = "detail-meta";
  metaText.textContent = meta;

  const scoreText = document.createElement("div");
  scoreText.className = "detail-score";
  scoreText.textContent = score;

  main.append(name, metaText);
  hero.append(main, scoreText);
  return hero;
}

function setHeraldDetailLoading(kind, name) {
  setText("heraldDetailTitle", kind === "guild" ? "길드 상세" : "캐릭터 상세");
  setText("heraldDetailSubtitle", name || "불러오는 중");
  setEmptyState("heraldDetail", "상세 정보를 불러오는 중입니다");
}

function renderCharacterDetail(detail) {
  const body = document.getElementById("heraldDetail");

  if (!body) {
    return;
  }

  const realmInfo = getRealmInfo(detail.realmId, detail.realmName);
  body.innerHTML = "";
  body.style.setProperty("--realm-color", realmInfo.color);

  const card = document.createElement("div");
  card.className = "detail-card";
  card.appendChild(renderDetailHero(
    detail.name || "-",
    `${realmInfo.label} · Lv ${formatNumber(detail.level)} ${detail.className || ""} · ${detail.realmRank || formatRealmRank(detail.realmLevel)}${detail.guildName ? ` · ${detail.guildName}` : ""}`,
    `${formatNumber(detail.realmPoints)} RP`));
  card.appendChild(renderDetailMetrics([
    ["BP", formatNumber(detail.bountyPoints)],
    ["최근 접속", formatDate(detail.lastPlayed)],
    ["플레이어 킬", formatNumber(detail.totalPlayerKills)],
    ["데스블로우", formatNumber(detail.totalDeathBlows)],
    ["솔로킬", formatNumber(detail.totalSoloKills)],
    ["PvP 사망", formatNumber(detail.pvpDeaths)]
  ]));

  body.appendChild(card);
  setText("heraldDetailTitle", "캐릭터 상세");
  setText("heraldDetailSubtitle", `${detail.name || "-"} · ${realmInfo.label}`);
}

function renderGuildDetail(detail) {
  const body = document.getElementById("heraldDetail");

  if (!body) {
    return;
  }

  const realmInfo = getRealmInfo(detail.realmId, detail.realmName);
  body.innerHTML = "";
  body.style.setProperty("--realm-color", realmInfo.color);

  const card = document.createElement("div");
  card.className = "detail-card";
  card.appendChild(renderDetailHero(
    detail.guildName || "-",
    `${realmInfo.label} · Lv ${formatNumber(detail.guildLevel)}`,
    `${formatNumber(detail.realmPoints)} RP`));
  card.appendChild(renderDetailMetrics([
    ["BP", formatNumber(detail.bountyPoints)],
    ["멤버", `${formatNumber(detail.memberCount)}명`],
    ["50레벨", `${formatNumber(detail.level50Members)}명`]
  ]));

  const members = document.createElement("div");
  members.className = "detail-member-list";
  const topMembers = detail.topMembers || [];

  if (topMembers.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "공개 멤버 데이터 없음";
    members.appendChild(empty);
  } else {
    topMembers.forEach((member, index) => {
      const row = document.createElement("button");
      row.type = "button";
      row.className = "rank-row";
      row.dataset.detailKind = "character";
      row.dataset.detailName = member.name || "";
      row.addEventListener("click", () => loadHeraldDetail("character", member.name));

      const position = document.createElement("span");
      position.className = "rank-pos";
      position.textContent = `#${index + 1}`;

      const main = document.createElement("div");
      main.className = "rank-main";

      const name = document.createElement("span");
      name.className = "rank-name";
      name.textContent = member.name || "-";

      const meta = document.createElement("span");
      meta.className = "rank-meta";
      meta.textContent = `${realmInfo.label} · Lv ${formatNumber(member.level)} ${member.className || ""} · ${member.realmRank || formatRealmRank(member.realmLevel)}`;

      const value = document.createElement("span");
      value.className = "rank-value";
      value.textContent = `${formatNumber(member.realmPoints)} RP`;

      main.append(name, meta);
      row.append(position, main, value);
      members.appendChild(row);
    });
  }

  card.appendChild(members);
  body.appendChild(card);
  setText("heraldDetailTitle", "길드 상세");
  setText("heraldDetailSubtitle", `${detail.guildName || "-"} · ${realmInfo.label}`);
}

async function loadHeraldDetail(kind, name) {
  if (!kind || !name) {
    return;
  }

  const cacheKey = `${kind}:${name}`;
  setHeraldDetailLoading(kind, name);

  try {
    let detail = heraldDetailCache.get(cacheKey);

    if (!detail) {
      detail = await getJson(`/api/dashboard/herald/${kind}/${encodeURIComponent(name)}`);
      heraldDetailCache.set(cacheKey, detail);
    }

    if (kind === "guild") {
      renderGuildDetail(detail);
    } else {
      renderCharacterDetail(detail);
    }
  } catch {
    setText("heraldDetailTitle", kind === "guild" ? "길드 상세" : "캐릭터 상세");
    setText("heraldDetailSubtitle", name);
    setEmptyState("heraldDetail", "상세 정보를 불러올 수 없습니다");
  }
}

function renderActivityList(items) {
  const list = document.getElementById("heraldActivity");

  if (!list) {
    return;
  }

  list.innerHTML = "";

  if (!items || items.length === 0) {
    setEmptyState("heraldActivity", "최근 활동 데이터 없음");
    return;
  }

  items.forEach((item) => {
    const realmInfo = getRealmInfo(item.realmId, item.realmName);
    const row = document.createElement("div");
    row.className = "activity-row";
    row.style.setProperty("--realm-color", realmInfo.color);

    const realm = document.createElement("span");
    realm.className = "rank-pos realm-label";
    realm.textContent = realmInfo.label.slice(0, 2);

    const main = document.createElement("div");
    main.className = "activity-main";

    const name = document.createElement("span");
    name.className = "activity-name";
    name.textContent = item.label || "활동";

    const meta = document.createElement("span");
    meta.className = "activity-meta";
    meta.textContent = `${realmInfo.label} · ${formatDate(item.bucket)}`;

    const value = document.createElement("span");
    value.className = "activity-value";
    value.textContent = item.metric === "gold"
      ? `${formatNumber(item.value)} 골드`
      : `${formatNumber(item.value)} RP`;

    main.append(name, meta);
    row.append(realm, main, value);
    list.appendChild(row);
  });
}

function renderRvrActivityList(items) {
  const list = document.getElementById("heraldRvrActivity");

  if (!list) {
    return;
  }

  list.innerHTML = "";

  if (!items || items.length === 0) {
    setEmptyState("heraldRvrActivity", "최근 RvR 기록 없음");
    return;
  }

  items.forEach((item) => {
    const killerRealm = getRealmInfo(item.killerRealmId, item.killerRealmName);
    const victimRealm = getRealmInfo(item.victimRealmId, item.victimRealmName);
    const row = document.createElement("div");
    row.className = "activity-row rvr-activity-row";
    row.style.setProperty("--realm-color", killerRealm.color);

    const realm = document.createElement("span");
    realm.className = "rank-pos realm-label";
    realm.textContent = killerRealm.label.slice(0, 2);

    const main = document.createElement("div");
    main.className = "activity-main";

    const name = document.createElement("span");
    name.className = "activity-name rvr-kill-line";
    const killer = item.killerName || "-";
    const victim = item.victimName || "-";
    name.textContent = `${killer} → ${victim}`;

    const meta = document.createElement("span");
    meta.className = "activity-meta";
    const killerClass = item.killerClassName || "Unknown";
    const victimClass = item.victimClassName || "Unknown";
    const region = item.regionName ? ` · ${item.regionName}` : "";
    meta.textContent = `${killerRealm.label} ${killerClass} vs ${victimRealm.label} ${victimClass}${region} · ${formatDate(item.killedAt)}`;

    const value = document.createElement("span");
    value.className = "activity-value";
    value.textContent = item.realmPoints > 0
      ? `${formatNumber(item.realmPoints)} RP`
      : (item.soloKill ? "Solo" : "Kill");

    main.append(name, meta);
    row.append(realm, main, value);
    list.appendChild(row);
  });
}

function applyHerald(herald) {
  latestHerald = herald;
  setText("heraldCharacterRankTitle", getCharacterRankMetric().title);
  renderHeraldSummary(herald);
  renderHeraldWar(herald?.war);
  renderRankList(
    "heraldCharacterRanks",
    getFilteredCharacterRanks(herald),
    {
      detailKind: "character",
      name: item => item.name || "-",
      meta: item => {
        const realmInfo = getRealmInfo(item.realmId, item.realmName);
        const guild = item.guildName ? ` · ${item.guildName}` : "";
        return `${realmInfo.label} · Lv ${item.level} ${item.className || ""} · ${formatRealmRank(item.realmLevel)}${guild} · ${formatDate(item.lastPlayed)}`;
      },
      value: getCharacterRankValue
    },
    "캐릭터 랭킹 데이터 없음");
  renderRankList(
    "heraldGuildRanks",
    getFilteredGuildRanks(herald),
    {
      detailKind: "guild",
      name: item => item.guildName || "-",
      meta: item => {
        const realmInfo = getRealmInfo(item.realmId, item.realmName);
        return `${realmInfo.label} · Lv ${formatNumber(item.guildLevel)} · BP ${formatNumber(item.bountyPoints)}`;
      },
      value: item => `${formatNumber(item.realmPoints)} RP`
    },
    "길드 랭킹 데이터 없음");
  renderRvrActivityList(herald?.recentRvr || []);
  renderActivityList(herald?.recentActivity || []);
}

function applyLive(live) {
  latestLive = live;
  setText("onlinePlayers", live.totalPlayers);
  updatePeakPlayers24h();
  setText("updatedAt", new Date(live.updatedAt).toLocaleTimeString("ko-KR"));
  setText("uptime", live.uptime);

  const realms = live.realms || [];
  setText("albionPlayers", realms.find(realm => realm.realmName === "Albion")?.players ?? 0);
  setText("midgardPlayers", realms.find(realm => realm.realmName === "Midgard")?.players ?? 0);
  setText("hiberniaPlayers", realms.find(realm => realm.realmName === "Hibernia")?.players ?? 0);
  drawBarChart("realmChart", realms.map(realm => displayRealmName(realm.realmName)), realms.map(realm => realm.players), realmColors);
  renderClassRealmGrid(live);
  applyHeraldClassView();
}

function applyHistory(history) {
  latestHistory = history;
  updatePeakPlayers24h();
  const points = history.points || [];
  const cpuValues = points.map(point => Math.max(0, Number(point.cpuPercent || 0)));
  const memoryValues = points.map(point => Math.max(0, Number(point.memoryKb || 0) / 1024));
  const connectionValues = points.map(point => Math.max(0, Number(point.totalPlayers || 0)));
  const receivedValues = points.map(point => Math.max(0, Number(point.networkReceivedKbps || 0)));
  const sentValues = points.map(point => Math.max(0, Number(point.networkSentKbps || 0)));
  const latest = points[points.length - 1] || {};

  drawLineChart("populationChart", [
    { label: "전체", values: points.map(point => point.totalPlayers), color: "#d7af54" },
    { label: "알비온", values: points.map(point => point.albionPlayers), color: realmColors[0] },
    { label: "미드가드", values: points.map(point => point.midgardPlayers), color: realmColors[1] },
    { label: "하이버니아", values: points.map(point => point.hiberniaPlayers), color: realmColors[2] }
  ]);

  drawLineChart("cpuChart", [
    { label: `CPU ${formatDecimal(latest.cpuPercent)}%`, values: cpuValues, color: "#c97cc7" }
  ]);
  drawLineChart("memoryChart", [
    { label: `RAM ${formatMemoryMb(latest.memoryKb)} MB`, values: memoryValues, color: "#50ad6f" }
  ]);
  drawLineChart("connectionChart", [
    { label: `커넥션 ${formatNumber(latest.totalPlayers)}`, values: connectionValues, color: "#5f8ee8" }
  ]);
  drawLineChart("networkChart", [
    { label: `수신 ${formatBandwidthKbps(latest.networkReceivedKbps)}`, values: receivedValues, color: "#5f8ee8" },
    { label: `송신 ${formatBandwidthKbps(latest.networkSentKbps)}`, values: sentValues, color: "#d7af54" }
  ]);
}

function applyActivity(activity) {
  latestActivity = activity;
  const points = activity.points || [];
  const total = (selector) => points.reduce((sum, point) => sum + Number(selector(point) || 0), 0);

  drawLineChart("goldChart", [
    { label: `알비온 ${formatNumber(total(point => point.albionGold))}`, values: points.map(point => point.albionGold), color: realmColors[0] },
    { label: `미드가드 ${formatNumber(total(point => point.midgardGold))}`, values: points.map(point => point.midgardGold), color: realmColors[1] },
    { label: `하이버니아 ${formatNumber(total(point => point.hiberniaGold))}`, values: points.map(point => point.hiberniaGold), color: realmColors[2] }
  ]);

  drawLineChart("rpChart", [
    { label: `알비온 ${formatNumber(total(point => point.albionRealmPoints))}`, values: points.map(point => point.albionRealmPoints), color: realmColors[0] },
    { label: `미드가드 ${formatNumber(total(point => point.midgardRealmPoints))}`, values: points.map(point => point.midgardRealmPoints), color: realmColors[1] },
    { label: `하이버니아 ${formatNumber(total(point => point.hiberniaRealmPoints))}`, values: points.map(point => point.hiberniaRealmPoints), color: realmColors[2] }
  ]);
}

function applyOperatorStatus(operator, latencyMs) {
  latestOperator = operator;
  latestOperatorLatency = latencyMs;
  setText("operatorUpdatedAt", `갱신 ${formatTime(operator.updatedAt)}`);
  setText("operatorApiLatency", latencyMs == null ? "API -" : `API ${formatNumber(latencyMs)}ms`);

  const banner = document.getElementById("operatorStatusBanner");
  if (banner) {
    banner.innerHTML = "";
    banner.className = `operator-banner status-${operator.overallStatus || "ok"}`;

    const status = document.createElement("strong");
    status.textContent = statusLabel(operator.overallStatus);

    const message = document.createElement("span");
    message.textContent = operator.message || "상태 확인 중";

    banner.append(status, message);
  }

  const live = operator.live || {};
  const performanceStats = live.performance || {};
  const resourceMetrics = document.getElementById("operatorResourceMetrics");
  if (resourceMetrics) {
    resourceMetrics.innerHTML = "";
    resourceMetrics.append(
      createMetric("접속자", `${formatNumber(live.totalPlayers)}명`),
      createMetric("CPU", `${formatDecimal(performanceStats.cpuPercent)}%`),
      createMetric("RAM", `${formatMemoryMb(performanceStats.memoryKb)} MB`),
      createMetric("수신 대역폭", formatBandwidthKbps(performanceStats.networkReceivedKbps)),
      createMetric("송신 대역폭", formatBandwidthKbps(performanceStats.networkSentKbps)),
      createMetric("가동 시간", live.uptime || "-"));
  }

  const historyMetrics = document.getElementById("operatorHistoryMetrics");
  if (historyMetrics) {
    historyMetrics.innerHTML = "";
    historyMetrics.append(
      createMetric("24시간 샘플", `${formatNumber(operator.historyPoints24h)}개`),
      createMetric("최근 샘플", formatTime(operator.latestHistoryBucket)),
      createMetric("라이브 갱신", formatTime(live.updatedAt)),
      createMetric("서버 시작", formatDate(live.startedAt)));
  }

  const checks = document.getElementById("operatorChecks");
  if (checks) {
    checks.innerHTML = "";
    (operator.checks || []).forEach((check) => {
      const row = document.createElement("div");
      row.className = `operator-check status-${check.status || "ok"}`;

      const status = document.createElement("span");
      status.className = "operator-check-status";
      status.textContent = statusLabel(check.status);

      const main = document.createElement("div");
      main.className = "operator-check-main";

      const name = document.createElement("strong");
      name.textContent = check.name || "-";

      const detail = document.createElement("span");
      detail.textContent = check.detail || "-";

      main.append(name, detail);
      row.append(status, main);
      checks.appendChild(row);
    });
  }
}

function applyClassHistory(history) {
  latestClassHistory.set(history.range, history);
  applyHeraldClassView();
}

function applyHeraldClassView() {
  const subtitle = document.getElementById("heraldClassSubtitle");

  if (currentHeraldClassRange === "now") {
    if (subtitle) {
      subtitle.textContent = "Classes Online - Now";
    }

    renderClassRealmGrid(latestLive, latestLive ? null : "실시간 데이터를 불러오는 중입니다", "heraldClassRealmGrid");
    return;
  }

  const history = latestClassHistory.get(currentHeraldClassRange);
  const label = currentHeraldClassRange === "7d" ? "7일 평균" : "24시간 평균";

  if (subtitle) {
    subtitle.textContent = `Classes Online - ${label}`;
  }

  if (!history) {
    renderClassRealmGrid(null, "히스토리 데이터를 불러오는 중입니다", "heraldClassRealmGrid");
    return;
  }

  renderClassRealmGrid(
    { classes: history.classes || [] },
    null,
    "heraldClassRealmGrid",
    {
      valueKey: "averagePlayers",
      emptyText: "히스토리 데이터 없음",
      valueText: item => `${formatDecimal(item.players)}명 평균 · 최고 ${formatNumber(item.peakPlayers)}명`,
      totalText: realmClasses => `${formatDecimal(realmClasses.reduce((sum, item) => sum + item.players, 0))}명 평균`
    });
}

function setupViewTabs() {
  const buttons = [...document.querySelectorAll("[data-view-tab]")];
  const panels = [...document.querySelectorAll("[data-view-panel]")];

  const activate = (target, updateHash) => {
    const normalizedTarget = target === "dashboard" ? "live" : target;
    const knownTarget = buttons.some(item => item.dataset.viewTab === normalizedTarget) ? normalizedTarget : "live";

    buttons.forEach(item => {
      const active = item.dataset.viewTab === knownTarget;
      item.classList.toggle("active", active);
      item.setAttribute("aria-selected", String(active));
    });

    panels.forEach(panel => {
      const active = panel.dataset.viewPanel === knownTarget;
      panel.classList.toggle("active", active);
      panel.hidden = !active;
    });

    if (updateHash) {
      const hash = `#${knownTarget}`;
      history.replaceState(null, "", `${location.pathname}${location.search}${hash}`);
    }

    redraw();
  };

  buttons.forEach(button => {
    button.addEventListener("click", () => {
      activate(button.dataset.viewTab, true);
    });
  });

  window.addEventListener("hashchange", () => {
    activate(location.hash.replace("#", ""), false);
  });

  activate(location.hash.replace("#", ""), false);
}

function setupClassRangeTabs() {
  const buttons = [...document.querySelectorAll("[data-class-range]")];

  buttons.forEach(button => {
    button.addEventListener("click", () => {
      currentHeraldClassRange = button.dataset.classRange || "now";

      buttons.forEach(item => {
        const active = item.dataset.classRange === currentHeraldClassRange;
        item.classList.toggle("active", active);
        item.setAttribute("aria-selected", String(active));
      });

      applyHeraldClassView();
    });
  });
}

function setupHeraldControls() {
  const bindInput = (id, kind, field) => {
    const element = document.getElementById(id);

    if (!element) {
      return;
    }

    element.addEventListener("input", () => {
      heraldFilters[kind][field] = element.value;
      applyHerald(latestHerald);
    });
  };

  const bindSelect = (id, kind, field) => {
    const element = document.getElementById(id);

    if (!element) {
      return;
    }

    element.addEventListener("change", () => {
      heraldFilters[kind][field] = element.value;
      applyHerald(latestHerald);
    });
  };

  const bindLookup = (buttonId, inputId, kind) => {
    const button = document.getElementById(buttonId);
    const input = document.getElementById(inputId);

    if (!button || !input) {
      return;
    }

    const lookup = () => {
      const name = input.value.trim();

      if (name) {
        loadHeraldDetail(kind, name);
      }
    };

    button.addEventListener("click", lookup);
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        lookup();
      }
    });
  };

  bindInput("heraldCharacterSearch", "character", "search");
  bindSelect("heraldCharacterRealm", "character", "realm");
  bindSelect("heraldCharacterSort", "character", "sort");
  bindLookup("heraldCharacterLookup", "heraldCharacterSearch", "character");

  bindInput("heraldGuildSearch", "guild", "search");
  bindSelect("heraldGuildRealm", "guild", "realm");
  bindSelect("heraldGuildSort", "guild", "sort");
  bindLookup("heraldGuildLookup", "heraldGuildSearch", "guild");
}

function redraw() {
  if (latestLive) {
    applyLive(latestLive);
  }

  if (latestHistory) {
    applyHistory(latestHistory);
  }

  if (latestActivity) {
    applyActivity(latestActivity);
  }

  if (latestHerald) {
    applyHerald(latestHerald);
  }

  if (latestOperator) {
    applyOperatorStatus(latestOperator, latestOperatorLatency);
  }

  applyDynamicQuestOps();
  applyHeraldClassView();
}

async function refresh() {
  const [
    live,
    history,
    activity,
    classHistory24h,
    classHistory7d,
    herald,
    operator,
    dynamicQuests,
    dynamicQuestSeed,
    dynamicQuestStoryCache,
    dynamicQuestStoryConfig,
    dynamicQuestDifficulty
  ] = await Promise.allSettled([
    getJson("/api/dashboard/live"),
    getJson("/api/dashboard/history?range=24h"),
    getJson("/api/dashboard/realm-activity?range=7d"),
    getJson("/api/dashboard/class-history?range=24h"),
    getJson("/api/dashboard/class-history?range=7d"),
    getJson("/api/dashboard/herald"),
    getJsonWithLatency("/api/dashboard/operator"),
    getJson("/api/world/dynamic-quests"),
    getJson("/api/world/dynamic-quests/seed/status"),
    getJson("/api/world/dynamic-quests/story-cache?limit=24"),
    getJson("/api/world/dynamic-quests/story-config"),
    getJson("/api/dashboard/dynamic-quests/difficulty")
  ]);

  if (live.status === "fulfilled") {
    applyLive(live.value);
  } else {
    latestLive = null;
    chartError("realmChart", "실시간 데이터를 불러올 수 없습니다");
    renderClassRealmGrid(null, "실시간 데이터를 불러올 수 없습니다");
    applyHeraldClassView();
  }

  if (history.status === "fulfilled") {
    applyHistory(history.value);
  } else {
    latestHistory = null;
    chartError("populationChart", "이전 기록을 불러올 수 없습니다");
    chartError("cpuChart", "CPU 기록을 불러올 수 없습니다");
    chartError("memoryChart", "RAM 기록을 불러올 수 없습니다");
    chartError("connectionChart", "커넥션 기록을 불러올 수 없습니다");
    chartError("networkChart", "네트워크 기록을 불러올 수 없습니다");
  }

  if (activity.status === "fulfilled") {
    applyActivity(activity.value);
  } else {
    latestActivity = null;
    chartError("goldChart", "활동 기록을 불러올 수 없습니다");
    chartError("rpChart", "활동 기록을 불러올 수 없습니다");
  }

  if (classHistory24h.status === "fulfilled") {
    applyClassHistory(classHistory24h.value);
  }

  if (classHistory7d.status === "fulfilled") {
    applyClassHistory(classHistory7d.value);
  }

  if (herald.status === "fulfilled") {
    applyHerald(herald.value);
  } else {
    latestHerald = null;
    setEmptyState("heraldRealmSummary", "해럴드 데이터를 불러올 수 없습니다");
    setText("heraldDfOwner", "DF -");
    setEmptyState("heraldWarSummary", "전황 데이터를 불러올 수 없습니다");
    setEmptyState("heraldRelics", "유물 데이터를 불러올 수 없습니다");
    setEmptyState("heraldCharacterRanks", "캐릭터 랭킹을 불러올 수 없습니다");
    setEmptyState("heraldGuildRanks", "길드 랭킹을 불러올 수 없습니다");
    setEmptyState("heraldActivity", "최근 활동을 불러올 수 없습니다");
  }

  if (operator.status === "fulfilled") {
    applyOperatorStatus(operator.value.value, operator.value.latencyMs);
  } else {
    latestOperator = null;
    setText("operatorUpdatedAt", "-");
    setText("operatorApiLatency", "API 실패");
    setEmptyState("operatorStatusBanner", "운영 상태를 불러올 수 없습니다");
    setEmptyState("operatorResourceMetrics", "라이브 자원을 불러올 수 없습니다");
    setEmptyState("operatorHistoryMetrics", "수집 상태를 불러올 수 없습니다");
    setEmptyState("operatorChecks", "서비스 체크를 불러올 수 없습니다");
  }

  latestDynamicQuests = dynamicQuests.status === "fulfilled" ? dynamicQuests.value : null;
  latestDynamicQuestSeed = dynamicQuestSeed.status === "fulfilled" ? dynamicQuestSeed.value : null;
  latestDynamicQuestStoryCache = dynamicQuestStoryCache.status === "fulfilled" ? dynamicQuestStoryCache.value : null;
  latestDynamicQuestStoryConfig = dynamicQuestStoryConfig.status === "fulfilled" ? dynamicQuestStoryConfig.value : null;
  latestDynamicQuestDifficulty = dynamicQuestDifficulty.status === "fulfilled" ? dynamicQuestDifficulty.value : null;

  if (latestDynamicQuests || latestDynamicQuestSeed || latestDynamicQuestStoryCache || latestDynamicQuestStoryConfig || latestDynamicQuestDifficulty) {
    applyDynamicQuestOps();
  } else {
    setText("dynamicQuestSeedUpdatedAt", "-");
    setText("dynamicQuestStoryProvider", "-");
    setText("dynamicQuestDifficultyUpdatedAt", "-");
    setEmptyState("dynamicQuestSeedMetrics", "동적 퀘스트 상태를 불러올 수 없습니다");
    setEmptyState("dynamicQuestOfferList", "활성 퀘스트를 불러올 수 없습니다");
    setEmptyState("dynamicQuestStoryMetrics", "스토리 캐시를 불러올 수 없습니다");
    setEmptyState("dynamicQuestStoryList", "스토리 캐시 목록을 불러올 수 없습니다");
    setEmptyState("dynamicQuestDifficultyMetrics", "난이도 리포트를 불러올 수 없습니다");
    setEmptyState("dynamicQuestDifficultyRuns", "난이도 런 목록을 불러올 수 없습니다");
  }
}

setupViewTabs();
setupClassRangeTabs();
setupHeraldControls();
window.addEventListener("resize", redraw);
refresh();
setInterval(refresh, 30000);
