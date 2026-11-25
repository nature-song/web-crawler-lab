/* 页面逻辑：表单 → API → SSE 事件 → 更新卡片/日志/表格。没有框架，够用就好。 */

const $ = (id) => document.getElementById(id);

const STATE_TEXT = {
  idle: "空闲",
  running: "运行中",
  paused: "已暂停",
  stopping: "停止中",
  finished: "已结束",
};

let startedAt = 0;
let timer = null;
let pageLimit = 50;

function setState(state) {
  const pill = $("state-pill");
  pill.textContent = STATE_TEXT[state] || state;
  pill.className = "pill " + state;

  const busy = state === "running" || state === "paused" || state === "stopping";
  $("btn-start").disabled = busy;
  $("btn-pause").disabled = !(state === "running" || state === "paused");
  $("btn-stop").disabled = !(state === "running" || state === "paused");
  $("btn-pause").textContent = state === "paused" ? "继续" : "暂停";

  if (!busy && timer) {
    clearInterval(timer);
    timer = null;
  }
}

function readForm() {
  return {
    seeds: $("seeds").value,
    strategy: $("strategy").value,
    max_depth: Number($("max_depth").value),
    max_pages: Number($("max_pages").value),
    workers: Number($("workers").value),
    interval: Number($("interval").value),
    same_domain: $("same_domain").checked,
    respect_robots: $("respect_robots").checked,
  };
}

async function post(url) {
  const resp = await fetch(url, { method: "POST" });
  return resp.json();
}

async function startCrawl() {
  $("log").innerHTML = "";
  $("rows").innerHTML = "";
  $("row-count").textContent = "0 条";

  const body = readForm();
  pageLimit = body.max_pages || 1;

  const resp = await fetch("/api/crawl/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await resp.json();
  if (!resp.ok) {
    alert(data.error || "启动失败");
    return;
  }
  startedAt = Date.now();
  setState("running");
  timer = setInterval(tick, 500);
  tick();
}

function tick() {
  if (!startedAt) return;
  const seconds = Math.floor((Date.now() - startedAt) / 1000);
  const mm = String(Math.floor(seconds / 60)).padStart(2, "0");
  const ss = String(seconds % 60).padStart(2, "0");
  $("clock").textContent = `${mm}:${ss}`;
}

function appendLog(level, message, time) {
  const box = $("log");
  const line = document.createElement("div");
  line.className = "line " + (level === "WARN" ? "warn" : level === "ERROR" ? "error" : "");

  const stamp = document.createElement("span");
  stamp.className = "t";
  stamp.textContent = time || "";

  const badge = document.createElement("span");
  badge.className = "lv";
  badge.textContent = level;

  const text = document.createElement("span");
  text.className = "m";
  text.textContent = message;

  line.append(stamp, badge, text);
  box.appendChild(line);
  while (box.childElementCount > 500) box.removeChild(box.firstChild);
  box.scrollTop = box.scrollHeight;
}

function addRow(row, prepend = true) {
  const tbody = $("rows");
  const tr = document.createElement("tr");
  [row.title, row.authors, row.publish_date, row.site, row.url].forEach((value, index) => {
    const td = document.createElement("td");
    td.textContent = value || "—";
    if (index === 4) td.className = "url";
    tr.appendChild(td);
  });
  if (prepend) tbody.prepend(tr);
  else tbody.appendChild(tr);
  $("row-count").textContent = `${tbody.childElementCount} 条`;
}

function updateStats(stats) {
  for (const key of ["fetched", "queued", "failed", "dup", "blocked", "pdf"]) {
    const el = $(`s-${key}`);
    if (el) el.textContent = stats[key] ?? 0;
  }
  const fetched = Number(stats.fetched || 0);
  const percent = Math.min(100, (fetched / Math.max(pageLimit, 1)) * 100);
  $("progress-bar").style.width = `${percent}%`;
  $("progress-text").textContent = `${fetched} / ${pageLimit}`;
}

async function loadResults() {
  const resp = await fetch("/api/results?limit=100");
  const rows = await resp.json();
  $("rows").innerHTML = "";
  rows.slice().reverse().forEach((row) => addRow(row, false));
  $("row-count").textContent = `${rows.length} 条`;
}

function connectEvents() {
  const source = new EventSource("/api/events");
  source.onmessage = (event) => {
    let payload;
    try {
      payload = JSON.parse(event.data);
    } catch {
      return;
    }
    const data = payload.data;
    switch (payload.type) {
      case "log":
        appendLog(data.level, data.msg, data.time);
        break;
      case "page":
        addRow(data);
        break;
      case "stats":
        updateStats(data);
        break;
      case "state":
        setState(data);
        break;
      case "done":
        appendLog("INFO", "本轮采集结束", "");
        break;
      default:
        break;
    }
  };
}

$("btn-start").addEventListener("click", startCrawl);

$("btn-pause").addEventListener("click", async () => {
  const paused = $("state-pill").classList.contains("paused");
  await post(paused ? "/api/crawl/resume" : "/api/crawl/pause");
  setState(paused ? "running" : "paused");
});

$("btn-stop").addEventListener("click", async () => {
  await post("/api/crawl/stop");
  setState("stopping");
});

$("btn-clear").addEventListener("click", async () => {
  if (!confirm("确定清空数据库里的全部结果吗？此操作不可撤销。")) return;
  await post("/api/clear");
  $("rows").innerHTML = "";
  $("row-count").textContent = "0 条";
  appendLog("INFO", "已清空结果", "");
});

loadResults();
setState("idle");
connectEvents();
