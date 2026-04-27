from __future__ import annotations

"""Embedded dashboard asset for the stdlib PowerClaw HTTP service."""

DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PowerClaw Operator Console</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #09111f;
      --bg2: #111b2e;
      --panel: rgba(18, 29, 48, 0.92);
      --panel2: rgba(27, 42, 68, 0.88);
      --ink: #edf4ff;
      --muted: #9fb0c7;
      --line: rgba(156, 180, 215, 0.20);
      --blue: #6ea8ff;
      --blue2: #2458d3;
      --green: #37d399;
      --gold: #f4bf50;
      --red: #ff6b6b;
      --shadow: 0 18px 60px rgba(0, 0, 0, 0.28);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(72, 111, 255, 0.24), transparent 34rem),
        radial-gradient(circle at top right, rgba(55, 211, 153, 0.14), transparent 30rem),
        linear-gradient(180deg, var(--bg), #050914);
      color: var(--ink);
    }
    button, input, textarea, select { font: inherit; }
    button {
      min-height: 36px;
      border: 1px solid var(--line);
      background: var(--panel2);
      color: var(--ink);
      border-radius: 10px;
      padding: 0 12px;
      cursor: pointer;
    }
    button:hover { border-color: rgba(110, 168, 255, 0.65); }
    button.primary {
      background: linear-gradient(135deg, var(--blue2), #6c45ff);
      border-color: transparent;
      color: #fff;
      font-weight: 700;
    }
    button.danger { color: var(--red); }
    button.ghost { background: transparent; }
    button:disabled { opacity: 0.55; cursor: not-allowed; }
    input, textarea {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 10px 12px;
      background: rgba(6, 12, 24, 0.75);
      color: var(--ink);
      outline: none;
    }
    textarea { min-height: 150px; resize: vertical; }
    input:focus, textarea:focus { border-color: var(--blue); }
    .shell { min-height: 100vh; display: grid; grid-template-rows: auto 1fr; }
    header {
      display: grid;
      grid-template-columns: 1fr minmax(260px, 460px);
      gap: 16px;
      align-items: center;
      padding: 20px 24px;
      border-bottom: 1px solid var(--line);
      backdrop-filter: blur(18px);
      background: rgba(5, 9, 20, 0.72);
      position: sticky;
      top: 0;
      z-index: 3;
    }
    h1 { margin: 0; font-size: 25px; line-height: 1.1; letter-spacing: -0.03em; }
    h2 { margin: 0; font-size: 14px; letter-spacing: 0.02em; text-transform: uppercase; color: var(--muted); }
    .subhead { margin-top: 6px; color: var(--muted); font-size: 13px; overflow-wrap: anywhere; }
    .auth-row { display: grid; grid-template-columns: 1fr auto; gap: 8px; }
    main {
      display: grid;
      grid-template-columns: minmax(340px, 470px) minmax(0, 1fr);
      gap: 18px;
      padding: 18px 24px 32px;
    }
    .stack { display: grid; gap: 16px; align-content: start; }
    .panel {
      min-width: 0;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 16px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }
    .panel-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
      padding: 14px 16px;
      border-bottom: 1px solid var(--line);
    }
    .body { padding: 14px 16px; }
    .composer { display: grid; gap: 10px; }
    .grid2 { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
    .row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); }
    .metric { padding: 15px 16px; border-right: 1px solid var(--line); border-bottom: 1px solid var(--line); }
    .metric:last-child { border-right: 0; }
    .metric strong { display: block; font-size: 26px; line-height: 1; margin-bottom: 6px; }
    .metric span { color: var(--muted); font-size: 12px; }
    .cards { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; padding: 14px 16px; }
    .card { padding: 13px; border: 1px solid var(--line); border-radius: 14px; background: rgba(6, 12, 24, 0.44); }
    .card strong { display: block; margin-bottom: 4px; }
    .feed { max-height: 430px; overflow: auto; }
    .feed.tall { max-height: calc(100vh - 330px); }
    .item { display: grid; gap: 6px; padding: 12px 16px; border-bottom: 1px solid var(--line); }
    .item:last-child { border-bottom: 0; }
    .item-title { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; min-width: 0; }
    .pill {
      display: inline-flex;
      align-items: center;
      min-height: 22px;
      border-radius: 999px;
      border: 1px solid var(--line);
      padding: 0 8px;
      font-size: 12px;
      color: var(--muted);
      background: rgba(255, 255, 255, 0.04);
      white-space: nowrap;
    }
    .ok { color: var(--green); }
    .warn { color: var(--gold); }
    .bad { color: var(--red); }
    .muted { color: var(--muted); font-size: 13px; overflow-wrap: anywhere; }
    code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; overflow-wrap: anywhere; }
    pre {
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      margin: 0;
      font-size: 12px;
      color: var(--muted);
    }
    .response {
      min-height: 100px;
      padding: 13px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: rgba(6, 12, 24, 0.54);
      color: var(--ink);
    }
    .quick button { flex: 1 1 150px; }
    @media (max-width: 1050px) {
      header, main { grid-template-columns: 1fr; }
      .cards { grid-template-columns: 1fr; }
      .feed.tall { max-height: none; }
    }
    @media (max-width: 620px) {
      .metrics, .grid2 { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <header>
      <div>
        <h1>PowerClaw Operator Console</h1>
        <div id="health" class="subhead">Connecting</div>
      </div>
      <div class="auth-row">
        <input id="token" type="password" autocomplete="off" placeholder="Bearer token">
        <button id="save-token">Save Token</button>
      </div>
    </header>
    <main>
      <section class="stack">
        <div class="panel">
          <div class="panel-head">
            <h2>Run A Turn</h2>
            <span id="active-session-pill" class="pill">new session</span>
          </div>
          <form id="turn-form" class="body composer">
            <input id="session-id" placeholder="Session id, optional">
            <textarea id="message" placeholder="Ask PowerClaw to inspect, plan, summarize, or operate with approved tools."></textarea>
            <div class="row">
              <button class="primary" type="submit">Send Turn</button>
              <button type="button" id="repo-workflow">Repo Operator</button>
              <button type="button" class="ghost" id="clear-session">New Session</button>
            </div>
            <div class="row quick">
              <button type="button" data-prompt="Summarize this workspace and identify the next best improvement.">Workspace Summary</button>
              <button type="button" data-prompt="Review the latest session events and explain what needs attention.">Review Events</button>
              <button type="button" data-prompt="List visible skills and recommend which one fits repo maintenance.">Skill Match</button>
            </div>
            <pre id="response" class="response">Responses will appear here.</pre>
          </form>
        </div>
        <div class="panel">
          <div class="panel-head">
            <h2>Search Memory</h2>
            <button id="search-memory">Search</button>
          </div>
          <div class="body composer">
            <input id="memory-query" placeholder="Search transcripts and facts">
            <div id="memory-results" class="feed"></div>
          </div>
        </div>
        <div class="panel">
          <div class="panel-head"><h2>Approvals</h2><span id="approval-count" class="pill">0 pending</span></div>
          <div id="approvals" class="feed"></div>
        </div>
      </section>
      <section class="stack">
        <div class="panel">
          <div class="metrics">
            <div class="metric"><strong id="turns">0</strong><span>completed turns</span></div>
            <div class="metric"><strong id="tools">0</strong><span>tool calls</span></div>
            <div class="metric"><strong id="models">0</strong><span>model calls</span></div>
            <div class="metric"><strong id="failures">0</strong><span>failures</span></div>
          </div>
          <div id="health-cards" class="cards"></div>
        </div>
        <div class="grid2">
          <div class="panel">
            <div class="panel-head"><h2>Sessions</h2><button id="refresh-sessions">Refresh</button></div>
            <div id="sessions" class="feed"></div>
          </div>
          <div class="panel">
            <div class="panel-head"><h2>Transcript</h2><span id="transcript-session" class="pill">select session</span></div>
            <div id="transcript" class="feed"></div>
          </div>
        </div>
        <div class="panel">
          <div class="panel-head"><h2>Runtime Events</h2><button id="refresh-events">Refresh</button></div>
          <div id="events" class="feed tall"></div>
        </div>
      </section>
    </main>
  </div>
  <script>
    const state = {
      token: localStorage.getItem("powerclaw-token") || "",
      sessionId: "",
      health: null,
    };
    const tokenInput = document.getElementById("token");
    tokenInput.value = state.token;

    document.getElementById("save-token").onclick = () => {
      state.token = tokenInput.value.trim();
      localStorage.setItem("powerclaw-token", state.token);
      refresh();
    };
    document.getElementById("refresh-events").onclick = () => loadEvents();
    document.getElementById("refresh-sessions").onclick = () => loadSessions();
    document.getElementById("clear-session").onclick = () => selectSession("");
    document.getElementById("search-memory").onclick = () => loadMemorySearch();
    document.querySelectorAll("[data-prompt]").forEach(button => {
      button.onclick = () => { document.getElementById("message").value = button.dataset.prompt; };
    });

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
    function dt(value) {
      return value ? new Date(value).toLocaleString() : "";
    }
    function renderEmpty(target, label) {
      target.innerHTML = `<div class="item"><div class="muted">${esc(label)}</div></div>`;
    }
    function statusClass(ok) { return ok ? "ok" : "bad"; }

    async function refresh() {
      await loadHealth();
      await Promise.allSettled([loadMetrics(), loadEvents(), loadApprovals(), loadSessions()]);
    }
    async function loadHealth() {
      try {
        const health = await api("/health");
        state.health = health;
        const providerState = health.model_providers_available ? "model ready" : "model missing";
        document.getElementById("health").innerHTML =
          `${esc(health.service)} on <code>${esc(health.workspace)}</code> · <span class="${statusClass(health.model_providers_available)}">${providerState}</span>`;
        renderHealthCards(health);
      } catch (err) {
        document.getElementById("health").textContent = `Auth required or offline: ${err.message}`;
      }
    }
    function renderHealthCards(health) {
      const diag = (health.model_diagnostics || []).map(item => `${item.name}: ${item.reason || "available"}`).join("; ") || "No diagnostics recorded";
      document.getElementById("health-cards").innerHTML = `
        <div class="card">
          <strong class="${statusClass(health.model_providers_available)}">Model ${health.model_providers_available ? "ready" : "not configured"}</strong>
          <div class="muted">${esc(health.model_provider)} / ${esc(health.model)}</div>
          <pre>${esc(diag)}</pre>
        </div>
        <div class="card">
          <strong>Tools</strong>
          <div class="muted">${(health.tools || []).length} available</div>
          <pre>${esc((health.tools || []).join(", ") || "No tools registered")}</pre>
        </div>
        <div class="card">
          <strong>Runtime Policy</strong>
          <div class="muted">Reflection: ${health.reflection_enabled ? "on" : "off"}</div>
          <div class="muted">Terminal: ${health.terminal_enabled ? "enabled" : "disabled"}</div>
        </div>
      `;
    }
    async function loadMetrics() {
      const metrics = await api("/v1/metrics");
      document.getElementById("turns").textContent = metrics.turns_completed || 0;
      document.getElementById("tools").textContent = metrics.tool_calls || 0;
      document.getElementById("models").textContent = metrics.model_calls || 0;
      document.getElementById("failures").textContent = metrics.failures || 0;
    }
    async function loadEvents() {
      const payload = await api("/v1/events?limit=100");
      const target = document.getElementById("events");
      if (!payload.events.length) return renderEmpty(target, "No events yet");
      target.innerHTML = payload.events.reverse().map(event => `
        <div class="item">
          <div class="item-title">
            <strong>${esc(event.event_type)}</strong>
            <span class="pill ${event.level === "error" ? "bad" : ""}">${esc(event.level)}</span>
          </div>
          <div class="muted">${dt(event.created_at)} ${event.session_id ? "· " + esc(event.session_id) : ""}</div>
          <pre>${esc(event.message || JSON.stringify(event.payload, null, 2))}</pre>
        </div>
      `).join("");
    }
    async function loadApprovals() {
      const payload = await api("/v1/approvals?status=pending");
      const target = document.getElementById("approvals");
      document.getElementById("approval-count").textContent = `${payload.requests.length} pending`;
      if (!payload.requests.length) return renderEmpty(target, "No pending approvals");
      target.innerHTML = payload.requests.map(item => `
        <div class="item">
          <div class="item-title"><strong>${esc(item.kind)}</strong><code>${esc(item.id)}</code></div>
          <div><code>${esc(item.subject)}</code></div>
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
      const target = document.getElementById("sessions");
      if (!payload.sessions.length) return renderEmpty(target, "No sessions yet");
      target.innerHTML = payload.sessions.map(session => `
        <button class="item" onclick="selectSession('${esc(session.session_id)}', true)">
          <span class="item-title"><strong>${esc(session.platform)}</strong><code>${esc(session.session_id)}</code></span>
          <span class="muted">${dt(session.updated_at)} · ${session.turn_count} turns · ${session.history_count} messages</span>
        </button>
      `).join("");
    }
    async function loadSessionTranscript() {
      const target = document.getElementById("transcript");
      if (!state.sessionId) return renderEmpty(target, "Select a session to inspect its transcript.");
      const payload = await api(`/v1/sessions/${encodeURIComponent(state.sessionId)}`);
      document.getElementById("transcript-session").textContent = payload.platform;
      if (!payload.history.length) return renderEmpty(target, "No transcript messages yet");
      target.innerHTML = payload.history.map(message => `
        <div class="item">
          <div class="item-title"><strong>${esc(message.role)}</strong><span class="pill">${dt(message.created_at)}</span></div>
          <pre>${esc(message.content)}</pre>
        </div>
      `).join("");
    }
    async function loadMemorySearch() {
      const query = document.getElementById("memory-query").value.trim();
      const target = document.getElementById("memory-results");
      if (!query) return renderEmpty(target, "Enter a memory query.");
      const payload = await api(`/v1/memory/search?q=${encodeURIComponent(query)}&limit=8`);
      if (!payload.results.length) return renderEmpty(target, "No memory matches.");
      target.innerHTML = payload.results.map(item => `
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
      document.getElementById("session-id").value = id;
      document.getElementById("active-session-pill").textContent = id ? "continuing session" : "new session";
      if (load) loadSessionTranscript();
    }
    async function submitTurn(endpoint, payload) {
      const responseBox = document.getElementById("response");
      responseBox.textContent = "PowerClaw is working...";
      const turn = await api(endpoint, {method: "POST", body: JSON.stringify(payload)});
      selectSession(turn.session_id, true);
      responseBox.textContent = turn.response;
      refresh();
    }
    document.getElementById("turn-form").onsubmit = async (event) => {
      event.preventDefault();
      const message = document.getElementById("message").value.trim();
      const sessionId = document.getElementById("session-id").value.trim();
      if (!message) return;
      const payload = {message};
      if (sessionId) payload.session_id = sessionId;
      await submitTurn("/v1/turn", payload);
    };
    document.getElementById("repo-workflow").onclick = async () => {
      const objective = document.getElementById("message").value.trim() || "Inspect this workspace and prepare the next EC2-ready step.";
      const sessionId = document.getElementById("session-id").value.trim();
      const payload = {objective};
      if (sessionId) payload.session_id = sessionId;
      await submitTurn("/v1/workflows/repo-operator", payload);
    };
    refresh();
    setInterval(refresh, 5000);
  </script>
</body>
</html>
"""
