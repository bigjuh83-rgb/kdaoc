const realmColors = ["#d64a4a", "#5f8ee8", "#50ad6f"];
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
  ctx.fillStyle = "#aaa399";
  ctx.font = "14px system-ui";
  ctx.fillText(title, 12, 26);

  return { ctx, width, height };
}

function chartError(canvasId, message) {
  const canvas = document.getElementById(canvasId);
  const { ctx } = clearChart(canvas, message);
  ctx.fillStyle = "#c97cc7";
  ctx.fillRect(12, 38, 36, 3);
}

function drawLineChart(canvasId, series) {
  const canvas = document.getElementById(canvasId);
  const { ctx, width, height } = clearChart(canvas, "Not enough data yet");
  const padding = 28;
  const values = series.flatMap(item => item.values);
  const max = Math.max(1, ...values);
  const points = series[0]?.values.length || 0;

  if (points < 2) {
    return;
  }

  ctx.strokeStyle = "#34302a";
  ctx.lineWidth = 1;

  for (let i = 0; i < 4; i++) {
    const y = padding + ((height - padding * 2) * i / 3);
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
      const y = height - padding - ((height - padding * 2) * value / max);

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
  const { ctx, width, height } = clearChart(canvas, "No data");
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

function applyLive(live) {
  latestLive = live;
  setText("onlinePlayers", live.totalPlayers);
  setText("updatedAt", new Date(live.updatedAt).toLocaleTimeString());
  setText("uptime", live.uptime);

  const realms = live.realms || [];
  setText("albionPlayers", realms.find(realm => realm.realmName === "Albion")?.players ?? 0);
  setText("midgardPlayers", realms.find(realm => realm.realmName === "Midgard")?.players ?? 0);
  setText("hiberniaPlayers", realms.find(realm => realm.realmName === "Hibernia")?.players ?? 0);
  drawBarChart("realmChart", realms.map(realm => realm.realmName), realms.map(realm => realm.players), realmColors);
  drawBarChart("classChart", (live.classes || []).map(item => item.className), (live.classes || []).map(item => item.players), ["#d7af54", "#75c2cb", "#c97cc7"]);
}

function applyHistory(history) {
  latestHistory = history;
  const points = history.points || [];

  drawLineChart("populationChart", [
    { values: points.map(point => point.totalPlayers), color: "#d7af54" },
    { values: points.map(point => point.albionPlayers), color: realmColors[0] },
    { values: points.map(point => point.midgardPlayers), color: realmColors[1] },
    { values: points.map(point => point.hiberniaPlayers), color: realmColors[2] }
  ]);

  drawLineChart("performanceChart", [
    { values: points.map(point => point.cpuPercent), color: "#d7af54" },
    { values: points.map(point => Math.round((point.memoryKb || 0) / 1024)), color: "#75c2cb" }
  ]);
}

function applyActivity(activity) {
  latestActivity = activity;
  const points = activity.points || [];

  drawLineChart("goldChart", [
    { values: points.map(point => point.albionGold), color: realmColors[0] },
    { values: points.map(point => point.midgardGold), color: realmColors[1] },
    { values: points.map(point => point.hiberniaGold), color: realmColors[2] }
  ]);

  drawLineChart("rpChart", [
    { values: points.map(point => point.albionRealmPoints), color: realmColors[0] },
    { values: points.map(point => point.midgardRealmPoints), color: realmColors[1] },
    { values: points.map(point => point.hiberniaRealmPoints), color: realmColors[2] }
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
    chartError("realmChart", "Live data unavailable");
    chartError("classChart", "Live data unavailable");
  }

  if (history.status === "fulfilled") {
    applyHistory(history.value);
  } else {
    latestHistory = null;
    chartError("populationChart", "History unavailable");
    chartError("performanceChart", "History unavailable");
  }

  if (activity.status === "fulfilled") {
    applyActivity(activity.value);
  } else {
    latestActivity = null;
    chartError("goldChart", "Activity unavailable");
    chartError("rpChart", "Activity unavailable");
  }
}

window.addEventListener("resize", redraw);
refresh();
setInterval(refresh, 30000);
