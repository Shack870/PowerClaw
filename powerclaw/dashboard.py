from __future__ import annotations

"""Embedded dashboard asset for the stdlib PowerClaw HTTP service."""

DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PowerClaw OS</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #070014;
      --bg-soft: #120726;
      --panel: rgba(17, 9, 39, 0.94);
      --panel-2: rgba(32, 14, 64, 0.92);
      --ink: #fff8d6;
      --muted: #8ff7ff;
      --line: #4b2dff;
      --blue: #28e8ff;
      --violet: #c13cff;
      --green: #39ff88;
      --gold: #ffe66d;
      --red: #ff3b8d;
      --shadow: 10px 10px 0 rgba(0, 0, 0, 0.55);
      --pixel-font: "Press Start 2P", "Silkscreen", "VT323", "Cascadia Mono", "Consolas", monospace;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: var(--pixel-font);
      color: var(--ink);
      background:
        linear-gradient(rgba(255, 255, 255, 0.035) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255, 255, 255, 0.035) 1px, transparent 1px),
        radial-gradient(circle at 18% 0%, rgba(40, 232, 255, 0.30), transparent 28rem),
        radial-gradient(circle at 85% 18%, rgba(255, 59, 141, 0.23), transparent 25rem),
        linear-gradient(180deg, #15042d, var(--bg));
      background-size: 18px 18px, 18px 18px, auto, auto, auto;
      image-rendering: pixelated;
    }
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      z-index: 20;
      background: repeating-linear-gradient(
        180deg,
        rgba(255, 255, 255, 0.045),
        rgba(255, 255, 255, 0.045) 1px,
        transparent 1px,
        transparent 4px
      );
      mix-blend-mode: screen;
      opacity: 0.32;
    }
    button, input, textarea, select { font: inherit; }
    button {
      min-height: 40px;
      border: 3px solid var(--line);
      border-radius: 0;
      padding: 0 14px;
      color: var(--ink);
      background: #160839;
      cursor: pointer;
      box-shadow: 4px 4px 0 #000;
      text-transform: uppercase;
      font-size: 10px;
    }
    button:hover {
      color: #050014;
      border-color: var(--gold);
      background: var(--gold);
      transform: translate(-1px, -1px);
    }
    button.primary {
      border-color: var(--gold);
      background: linear-gradient(135deg, #ff3b8d, #7c4dff 52%, #28e8ff);
      font-weight: 800;
      color: #fff8d6;
      text-shadow: 2px 2px 0 #000;
    }
    button.mode-active { border-color: var(--green); background: #0d3a38; color: var(--green); }
    button.danger { color: var(--red); }
    input, textarea {
      width: 100%;
      border: 3px solid var(--line);
      border-radius: 0;
      padding: 11px 13px;
      color: var(--ink);
      background: #070014;
      outline: none;
      font-size: 12px;
    }
    textarea { min-height: 132px; resize: vertical; }
    input:focus, textarea:focus { border-color: var(--gold); box-shadow: 0 0 0 3px rgba(255, 230, 109, 0.25); }
    header {
      display: grid;
      grid-template-columns: 1fr minmax(300px, 500px);
      gap: 18px;
      align-items: center;
      padding: 20px 24px;
      border-bottom: 4px solid var(--line);
      background: rgba(10, 3, 29, 0.94);
      position: sticky;
      top: 0;
      z-index: 5;
    }
    h1 {
      margin: 0;
      font-size: 25px;
      line-height: 1.15;
      color: var(--gold);
      text-shadow: 3px 0 0 var(--red), 6px 0 0 var(--blue), 3px 3px 0 #000;
      letter-spacing: 0.02em;
      text-transform: uppercase;
    }
    h2 {
      margin: 0;
      color: var(--green);
      font-size: 10px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      text-shadow: 2px 2px 0 #000;
    }
    .subtitle { margin-top: 7px; color: var(--muted); font-size: 13px; overflow-wrap: anywhere; }
    .auth-box { display: grid; gap: 6px; }
    .auth-row { display: grid; grid-template-columns: 1fr auto; gap: 8px; }
    .hint { color: var(--muted); font-size: 12px; }
    .saved { color: var(--green); font-size: 12px; min-height: 16px; }
    main {
      display: grid;
      grid-template-columns: minmax(420px, 1.14fr) minmax(340px, 0.86fr);
      gap: 18px;
      padding: 18px 24px 30px;
    }
    .stack { display: grid; gap: 16px; align-content: start; }
    .panel {
      min-width: 0;
      overflow: hidden;
      border: 4px solid var(--line);
      border-radius: 0;
      background: var(--panel);
      box-shadow: var(--shadow);
    }
    .panel-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      padding: 14px 16px;
      border-bottom: 4px solid var(--line);
      background: linear-gradient(90deg, rgba(255, 59, 141, 0.18), rgba(40, 232, 255, 0.10));
    }
    .panel-body { padding: 15px 16px; }
    .grid2 { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
    .row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .mode-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
    .mode-card {
      display: grid;
      gap: 5px;
      min-height: 76px;
      padding: 12px;
      text-align: left;
      align-content: start;
    }
    .composer { display: grid; gap: 11px; }
    .reply-box {
      min-height: 180px;
      padding: 16px;
      border: 4px solid var(--blue);
      border-radius: 0;
      background:
        repeating-linear-gradient(0deg, rgba(40, 232, 255, 0.08), rgba(40, 232, 255, 0.08) 2px, transparent 2px, transparent 8px),
        #050014;
      box-shadow: inset 0 0 0 4px rgba(255, 255, 255, 0.04), 6px 6px 0 #000;
    }
    .reply-title { display: flex; justify-content: space-between; gap: 10px; margin-bottom: 10px; }
    .reply-content {
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      line-height: 1.7;
      font-size: 12px;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      min-height: 23px;
      border-radius: 0;
      border: 2px solid var(--line);
      padding: 0 8px;
      color: var(--muted);
      background: #070014;
      font-size: 10px;
      white-space: nowrap;
    }
    .ok { color: var(--green); }
    .warn { color: var(--gold); }
    .bad { color: var(--red); }
    .muted { color: var(--muted); font-size: 13px; overflow-wrap: anywhere; }
    .cards { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 11px; }
    .card {
      min-width: 0;
      padding: 13px;
      border: 3px solid var(--line);
      border-radius: 0;
      background: #0b0524;
      box-shadow: 4px 4px 0 #000;
    }
    .card strong { display: block; margin-bottom: 5px; }
    .metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); }
    .metric { padding: 14px 16px; border-right: 3px solid var(--line); border-bottom: 3px solid var(--line); }
    .metric:last-child { border-right: 0; }
    .metric strong { display: block; font-size: 22px; line-height: 1; margin-bottom: 8px; color: var(--gold); text-shadow: 2px 2px 0 #000; }
    .metric span { color: var(--muted); font-size: 10px; text-transform: uppercase; }
    .feed { max-height: 360px; overflow: auto; }
    .feed.tall { max-height: calc(100vh - 430px); }
    .item { display: grid; gap: 6px; padding: 12px 16px; border-bottom: 2px solid rgba(75, 45, 255, 0.65); }
    .item:last-child { border-bottom: 0; }
    .item-title { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; }
    code { font-family: var(--pixel-font); font-size: 10px; overflow-wrap: anywhere; color: var(--gold); }
    pre {
      margin: 0;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      color: var(--muted);
      font-size: 11px;
    }
    .quick button { flex: 1 1 155px; }
    .banner {
      display: none;
      margin-bottom: 12px;
      padding: 11px 13px;
      border: 3px solid var(--gold);
      border-radius: 0;
      background: rgba(255, 230, 109, 0.10);
      color: #ffe3a1;
      font-size: 11px;
      box-shadow: 4px 4px 0 #000;
    }
    .banner.show { display: block; }
    @media (max-width: 1120px) {
      header, main { grid-template-columns: 1fr; }
      .feed.tall { max-height: none; }
    }
    @media (max-width: 720px) {
      .grid2, .mode-grid, .cards, .metrics { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>PowerClaw OS</h1>
      <div id="health" class="subtitle">Insert token. Boot local operator console.</div>
    </div>
    <div class="auth-box">
      <div class="auth-row">
        <input id="token" type="password" autocomplete="off" placeholder="Dashboard access token, not OpenAI key">
        <button id="save-token">Save</button>
      </div>
      <div class="hint">This only unlocks the dashboard API. Set OpenAI with <code>OPENAI_API_KEY</code> before starting PowerClaw.</div>
      <div id="token-saved" class="saved"></div>
    </div>
  </header>
  <main>
    <section class="stack">
      <div class="panel">
        <div class="panel-head">
          <h2>Agent Console</h2>
          <span id="session-pill" class="pill">new session</span>
        </div>
        <div class="panel-body composer">
          <div id="model-banner" class="banner"></div>
          <div class="mode-grid">
            <button type="button" id="mode-chat" class="mode-card mode-active">
              <strong>Chat Mode</strong>
              <span class="muted">Ask, inspect, summarize, and use available tools.</span>
            </button>
            <button type="button" id="mode-repo" class="mode-card">
              <strong>Repo Operator</strong>
              <span class="muted">Runs the flagship workflow for repo review, EC2 readiness, approvals, and reusable runbooks.</span>
            </button>
          </div>
          <input id="session-id" placeholder="Session id, optional">
          <textarea id="message" placeholder="Tell PowerClaw what to do on this Windows machine or in this workspace."></textarea>
          <div class="row">
            <button id="send" class="primary" type="button">Send To PowerClaw</button>
            <button id="new-session" type="button">New Session</button>
            <button id="reload" type="button">Refresh State</button>
          </div>
          <div class="row quick">
            <button type="button" data-prompt="Summarize this PowerClaw workspace and explain what is ready to use.">Summarize Workspace</button>
            <button type="button" data-prompt="Review the latest runtime events and tell me what needs attention.">Review Events</button>
            <button type="button" data-prompt="List available skills and recommend the best one for repo maintenance.">Skill Match</button>
          </div>
          <div class="reply-box">
            <div class="reply-title">
              <strong>PowerClaw Reply Screen</strong>
              <span id="reply-state" class="pill">idle</span>
            </div>
            <div id="reply" class="reply-content">READY PLAYER OPERATOR. Agent replies appear here after every turn.</div>
          </div>
        </div>
      </div>
      <div class="grid2">
        <div class="panel">
          <div class="panel-head"><h2>Memory Search</h2><button id="search-memory">Search</button></div>
          <div class="panel-body composer">
            <input id="memory-query" placeholder="Search remembered messages and facts">
            <div id="memory-results" class="feed"></div>
          </div>
        </div>
        <div class="panel">
          <div class="panel-head"><h2>Approvals</h2><span id="approval-count" class="pill">0 pending</span></div>
          <div id="approvals" class="feed"></div>
        </div>
      </div>
    </section>
    <section class="stack">
      <div class="panel">
        <div class="metrics">
          <div class="metric"><strong id="turns">0</strong><span>turns</span></div>
          <div class="metric"><strong id="tools">0</strong><span>tool calls</span></div>
          <div class="metric"><strong id="models">0</strong><span>model calls</span></div>
          <div class="metric"><strong id="failures">0</strong><span>failures</span></div>
        </div>
        <div id="system-cards" class="panel-body cards"></div>
      </div>
      <div class="grid2">
        <div class="panel">
          <div class="panel-head"><h2>Sessions</h2><button id="refresh-sessions">Refresh</button></div>
          <div id="sessions" class="feed"></div>
        </div>
        <div class="panel">
          <div class="panel-head"><h2>Transcript</h2><span id="transcript-label" class="pill">select session</span></div>
          <div id="transcript" class="feed"></div>
        </div>
      </div>
      <div class="panel">
        <div class="panel-head"><h2>Runtime Events</h2><button id="refresh-events">Refresh</button></div>
        <div id="events" class="feed tall"></div>
      </div>
    </section>
  </main>
  <script>
    const state = {
      token: localStorage.getItem("powerclaw-token") || "",
      sessionId: "",
      mode: "chat",
      health: null,
    };
    const $ = (id) => document.getElementById(id);
    $("token").value = state.token;

    $("save-token").onclick = () => {
      state.token = $("token").value.trim();
      localStorage.setItem("powerclaw-token", state.token);
      $("token-saved").textContent = state.token ? "Dashboard token saved locally in this browser." : "Dashboard token cleared.";
      refresh();
      setTimeout(() => $("token-saved").textContent = "", 3000);
    };
    $("mode-chat").onclick = () => setMode("chat");
    $("mode-repo").onclick = () => setMode("repo");
    $("send").onclick = () => submit();
    $("new-session").onclick = () => selectSession("");
    $("reload").onclick = () => refresh();
    $("refresh-events").onclick = () => loadEvents();
    $("refresh-sessions").onclick = () => loadSessions();
    $("search-memory").onclick = () => loadMemorySearch();
    document.querySelectorAll("[data-prompt]").forEach(button => {
      button.onclick = () => $("message").value = button.dataset.prompt;
    });

    function setMode(mode) {
      state.mode = mode;
      $("mode-chat").classList.toggle("mode-active", mode === "chat");
      $("mode-repo").classList.toggle("mode-active", mode === "repo");
      if (mode === "repo" && !$("message").value.trim()) {
        $("message").value = "Inspect this workspace, summarize risks, and prepare the next EC2-ready release step.";
      }
    }
    function headers() {
      const base = {"Content-Type": "application/json"};
      if (state.token) base.Authorization = `Bearer ${state.token}`;
      return base;
    }
    async function api(path, options = {}) {
      const res = await fetch(path, {...options, headers: {...headers(), ...(options.headers || {})}});
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      return await res.json();
    }
    function esc(value) {
      return String(value ?? "").replace(/[&<>"']/g, char => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      })[char]);
    }
    function dt(value) { return value ? new Date(value).toLocaleString() : ""; }
    function renderEmpty(target, label) {
      target.innerHTML = `<div class="item"><div class="muted">${esc(label)}</div></div>`;
    }
    function setReply(status, content) {
      $("reply-state").textContent = status;
      $("reply").textContent = content;
    }
    async function refresh() {
      await loadHealth();
      await Promise.allSettled([loadMetrics(), loadApprovals(), loadSessions(), loadEvents()]);
      if (state.sessionId) await loadSessionTranscript();
    }
    async function loadHealth() {
      try {
        const health = await api("/health");
        state.health = health;
        const modelState = health.model_providers_available ? "model ready" : "model not configured";
        $("health").innerHTML = `${esc(health.service)} on <code>${esc(health.workspace)}</code> · <span class="${health.model_providers_available ? "ok" : "warn"}">${modelState}</span>`;
        renderSystemCards(health);
        renderModelBanner(health);
      } catch (err) {
        $("health").textContent = `Dashboard locked or offline: ${err.message}`;
      }
    }
    function renderModelBanner(health) {
      const banner = $("model-banner");
      if (health.model_providers_available) {
        banner.classList.remove("show");
        banner.textContent = "";
        return;
      }
      const diag = (health.model_diagnostics || []).map(item => item.reason).filter(Boolean).join(" ");
      banner.textContent = `Model is not connected. The dashboard access token is not your OpenAI key. Set OPENAI_API_KEY or POWERCLAW_OPENAI_API_KEY in the shell before starting PowerClaw. ${diag}`;
      banner.classList.add("show");
    }
    function renderSystemCards(health) {
      const diag = (health.model_diagnostics || []).map(item => `${item.name}: ${item.reason || "available"}`).join("; ") || "No diagnostics recorded";
      $("system-cards").innerHTML = `
        <div class="card">
          <strong class="${health.model_providers_available ? "ok" : "warn"}">Model ${health.model_providers_available ? "connected" : "missing"}</strong>
          <div class="muted">${esc(health.model_provider)} / ${esc(health.model)}</div>
          <pre>${esc(diag)}</pre>
        </div>
        <div class="card">
          <strong>Native Tools</strong>
          <div class="muted">${(health.tools || []).length} available</div>
          <pre>${esc((health.tools || []).join(", ") || "No active tools")}</pre>
        </div>
        <div class="card">
          <strong>Machine Policy</strong>
          <div class="muted">Reflection: ${health.reflection_enabled ? "on" : "off"}</div>
          <div class="muted">Terminal: ${health.terminal_enabled ? "enabled" : "disabled"}</div>
          <div class="muted">Sessions: ${health.sessions}</div>
        </div>
      `;
    }
    async function loadMetrics() {
      const metrics = await api("/v1/metrics");
      $("turns").textContent = metrics.turns_completed || 0;
      $("tools").textContent = metrics.tool_calls || 0;
      $("models").textContent = metrics.model_calls || 0;
      $("failures").textContent = metrics.failures || 0;
    }
    async function loadApprovals() {
      const payload = await api("/v1/approvals?status=pending");
      $("approval-count").textContent = `${payload.requests.length} pending`;
      if (!payload.requests.length) return renderEmpty($("approvals"), "No pending approvals.");
      $("approvals").innerHTML = payload.requests.map(item => `
        <div class="item">
          <div class="item-title"><strong>${esc(item.kind)}</strong><code>${esc(item.id)}</code></div>
          <code>${esc(item.subject)}</code>
          <div class="muted">${esc(item.reason || "")}</div>
          <div class="row">
            <button onclick="resolveApproval('${esc(item.id)}', 'approve')">Approve</button>
            <button class="danger" onclick="resolveApproval('${esc(item.id)}', 'deny')">Deny</button>
          </div>
        </div>
      `).join("");
    }
    async function loadSessions() {
      const payload = await api("/v1/sessions?limit=20");
      if (!payload.sessions.length) return renderEmpty($("sessions"), "No sessions yet.");
      $("sessions").innerHTML = payload.sessions.map(session => `
        <button class="item" onclick="selectSession('${esc(session.session_id)}', true)">
          <span class="item-title"><strong>${esc(session.platform)}</strong><code>${esc(session.session_id)}</code></span>
          <span class="muted">${dt(session.updated_at)} · ${session.turn_count} turns · ${session.history_count} messages</span>
        </button>
      `).join("");
    }
    async function loadSessionTranscript() {
      if (!state.sessionId) return renderEmpty($("transcript"), "Select a session to inspect the transcript.");
      const payload = await api(`/v1/sessions/${encodeURIComponent(state.sessionId)}`);
      $("transcript-label").textContent = payload.platform;
      if (!payload.history.length) return renderEmpty($("transcript"), "No transcript messages yet.");
      $("transcript").innerHTML = payload.history.map(message => `
        <div class="item">
          <div class="item-title"><strong>${esc(message.role)}</strong><span class="pill">${dt(message.created_at)}</span></div>
          <pre>${esc(message.content)}</pre>
        </div>
      `).join("");
    }
    async function loadEvents() {
      const payload = await api("/v1/events?limit=100");
      if (!payload.events.length) return renderEmpty($("events"), "No runtime events yet.");
      $("events").innerHTML = payload.events.reverse().map(event => `
        <div class="item">
          <div class="item-title"><strong>${esc(event.event_type)}</strong><span class="pill ${event.level === "error" ? "bad" : ""}">${esc(event.level)}</span></div>
          <div class="muted">${dt(event.created_at)} ${event.session_id ? "· " + esc(event.session_id) : ""}</div>
          <pre>${esc(event.message || JSON.stringify(event.payload, null, 2))}</pre>
        </div>
      `).join("");
    }
    async function loadMemorySearch() {
      const query = $("memory-query").value.trim();
      if (!query) return renderEmpty($("memory-results"), "Enter a memory query.");
      const payload = await api(`/v1/memory/search?q=${encodeURIComponent(query)}&limit=8`);
      if (!payload.results.length) return renderEmpty($("memory-results"), "No memory matches.");
      $("memory-results").innerHTML = payload.results.map(item => `
        <div class="item">
          <div class="item-title"><strong>${esc(item.kind)}</strong><span class="pill">${dt(item.created_at)}</span></div>
          <pre>${esc(item.content)}</pre>
        </div>
      `).join("");
    }
    async function resolveApproval(id, action) {
      await api(`/v1/approvals/${id}/${action}`, {method: "POST", body: "{}"});
      refresh();
    }
    function selectSession(id, load = false) {
      state.sessionId = id;
      $("session-id").value = id;
      $("session-pill").textContent = id ? "continuing session" : "new session";
      $("transcript-label").textContent = id ? "loading" : "select session";
      if (load) loadSessionTranscript();
    }
    async function submit() {
      const message = $("message").value.trim();
      const sessionId = $("session-id").value.trim();
      if (!message) return;
      const payload = {};
      const endpoint = state.mode === "repo" ? "/v1/workflows/repo-operator" : "/v1/turn";
      if (state.mode === "repo") payload.objective = message;
      else payload.message = message;
      if (sessionId) payload.session_id = sessionId;
      setReply("working", "PowerClaw is thinking...");
      try {
        const turn = await api(endpoint, {method: "POST", body: JSON.stringify(payload)});
        selectSession(turn.session_id, true);
        setReply("complete", turn.response || "No response returned.");
        refresh();
      } catch (err) {
        setReply("error", `Request failed: ${err.message}`);
      }
    }
    refresh();
    setInterval(refresh, 5000);
  </script>
</body>
</html>
"""
