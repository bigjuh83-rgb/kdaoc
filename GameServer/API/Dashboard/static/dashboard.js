const realmColors = ["#d64a4a", "#5f8ee8", "#50ad6f"];
const realmNames = new Map([
  ["Albion", "알비온"],
  ["Midgard", "미드가드"],
  ["Hibernia", "하이버니아"]
]);
let latestLive = null;
let latestHistory = null;
let latestActivity = null;

async function getJson(url) {
  const response = await fetch(url, { cache: "no-store" });

  if (!response.ok) {
    throw new Error(`${url} returned ${response.status}`);
  }

  return response.json();
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

function drawLegend(ctx, series, x, y) {
  ctx.font = "13px system-ui";

  series.forEach((item, index) => {
    const label = item.label || `Series ${index + 1}`;
    const offset = index * 130;

    ctx.fillStyle = item.color || realmColors[index % realmColors.length];
    ctx.fillRect(x + offset, y - 10, 18, 4);
    ctx.fillStyle = "#f1efe8";
    ctx.fillText(label, x + offset + 26, y);
  });
}

function drawLineChart(canvasId, series) {
  const canvas = document.getElementById(canvasId);
  const points = series[0]?.values.length || 0;

  if (points < 2) {
    clearChart(canvas, "데이터가 더 필요합니다");
    return;
  }

  const { ctx, width, height } = clearChart(canvas);
  const padding = 34;
  const values = series.flatMap(item => item.values);
  const max = Math.max(1, ...values);
  const allZero = values.every(value => value <= 0);

  ctx.strokeStyle = "#34302a";
  ctx.lineWidth = 1;
  drawLegend(ctx, series, padding, 20);

  for (let i = 0; i < 4; i++) {
    const y = padding + 16 + ((height - padding * 2 - 16) * i / 3);
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
      const x = padding + ((width - padding * 2) * pointIndex / (points - 1));
      const overlapOffset = series.length > 1 ? (index - ((series.length - 1) / 2)) * 4 : 0;
      const zeroOffset = allZero ? index * 9 : overlapOffset;
      const y = height - padding - zeroOffset - ((height - padding * 2 - 16) * value / max);

      if (pointIndex === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });

    ctx.stroke();
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

function applyLive(live) {
  latestLive = live;
  setText("onlinePlayers", live.totalPlayers);
  setText("updatedAt", new Date(live.updatedAt).toLocaleTimeString("ko-KR"));
  setText("uptime", live.uptime);

  const realms = live.realms || [];
  setText("albionPlayers", realms.find(realm => realm.realmName === "Albion")?.players ?? 0);
  setText("midgardPlayers", realms.find(realm => realm.realmName === "Midgard")?.players ?? 0);
  setText("hiberniaPlayers", realms.find(realm => realm.realmName === "Hibernia")?.players ?? 0);
  drawBarChart("realmChart", realms.map(realm => displayRealmName(realm.realmName)), realms.map(realm => realm.players), realmColors);
  drawBarChart("classChart", (live.classes || []).map(item => item.className), (live.classes || []).map(item => item.players), ["#d7af54", "#75c2cb", "#c97cc7"]);
}

function applyHistory(history) {
  latestHistory = history;
  const points = history.points || [];

  drawLineChart("populationChart", [
    { label: "전체", values: points.map(point => point.totalPlayers), color: "#d7af54" },
    { label: "알비온", values: points.map(point => point.albionPlayers), color: realmColors[0] },
    { label: "미드가드", values: points.map(point => point.midgardPlayers), color: realmColors[1] },
    { label: "하이버니아", values: points.map(point => point.hiberniaPlayers), color: realmColors[2] }
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
}

async function refresh() {
  const [live, history, activity] = await Promise.allSettled([
    getJson("/api/dashboard/live"),
    getJson("/api/dashboard/history?range=24h"),
    getJson("/api/dashboard/realm-activity?range=7d")
  ]);

  if (live.status === "fulfilled") {
    applyLive(live.value);
  } else {
    latestLive = null;
    chartError("realmChart", "실시간 데이터를 불러올 수 없습니다");
    chartError("classChart", "실시간 데이터를 불러올 수 없습니다");
  }

  if (history.status === "fulfilled") {
    applyHistory(history.value);
  } else {
    latestHistory = null;
    chartError("populationChart", "이전 기록을 불러올 수 없습니다");
  }

  if (activity.status === "fulfilled") {
    applyActivity(activity.value);
  } else {
    latestActivity = null;
    chartError("goldChart", "활동 기록을 불러올 수 없습니다");
    chartError("rpChart", "활동 기록을 불러올 수 없습니다");
  }
}

window.addEventListener("resize", redraw);
refresh();
setInterval(refresh, 30000);
