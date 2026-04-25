from __future__ import annotations

"""Embedded dashboard asset for the stdlib PowerClaw HTTP service."""

DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PowerClaw Dashboard</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #1b1f24;
      --muted: #637083;
      --line: #d7dde5;
      --paper: #f8fafc;
      --panel: #ffffff;
      --blue: #2458d3;
      --green: #127a5a;
      --red: #b42318;
      --gold: #986500;
      --shadow: 0 16px 42px rgba(20, 32, 50, 0.12);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--paper);
      color: var(--ink);
    }
    button, input, textarea, select {
      font: inherit;
    }
    button {
      min-height: 36px;
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--ink);
      border-radius: 6px;
      padding: 0 12px;
      cursor: pointer;
    }
    button.primary {
      background: var(--blue);
      border-color: var(--blue);
      color: #fff;
    }
    button.danger {
      color: var(--red);
    }
    button:disabled {
      opacity: 0.55;
      cursor: not-allowed;
    }
    input, textarea {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px 12px;
      background: #fff;
      color: var(--ink);
    }
    textarea {
      min-height: 110px;
      resize: vertical;
    }
    .shell {
      min-height: 100vh;
      display: grid;
      grid-template-rows: auto 1fr;
    }
    header {
      display: grid;
      grid-template-columns: 1fr minmax(240px, 420px);
      gap: 16px;
      align-items: center;
      padding: 16px 22px;
      border-bottom: 1px solid var(--line);
      background: #fff;
      position: sticky;
      top: 0;
      z-index: 2;
    }
    h1 {
      margin: 0;
      font-size: 22px;
      line-height: 1.2;
      font-weight: 700;
      letter-spacing: 0;
    }
    .status-line {
      margin-top: 4px;
      color: var(--muted);
      font-size: 13px;
    }
    .auth-row {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 8px;
    }
    main {
      display: grid;
      grid-template-columns: minmax(320px, 440px) minmax(0, 1fr);
      gap: 18px;
      padding: 18px 22px 28px;
    }
    section {
      min-width: 0;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }
    .panel h2 {
      margin: 0;
      padding: 14px 16px;
      font-size: 15px;
      border-bottom: 1px solid var(--line);
    }
    .stack {
      display: grid;
      gap: 14px;
    }
    .composer {
      display: grid;
      gap: 10px;
      padding: 14px;
    }
    .row {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .metrics {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      border-bottom: 1px solid var(--line);
    }
    .metric {
      padding: 14px 16px;
      border-right: 1px solid var(--line);
      min-width: 0;
    }
    .metric:last-child { border-right: 0; }
    .metric strong {
      display: block;
      font-size: 24px;
      line-height: 1;
      margin-bottom: 5px;
    }
    .metric span {
      color: var(--muted);
      font-size: 12px;
    }
    .feed {
      max-height: calc(100vh - 255px);
      overflow: auto;
    }
    .event, .approval, .session {
      display: grid;
      gap: 4px;
      padding: 12px 16px;
      border-bottom: 1px solid var(--line);
    }
    .event:last-child, .approval:last-child, .session:last-child {
      border-bottom: 0;
    }
    .event-title, .approval-title, .session-title {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 10px;
      min-width: 0;
    }
    code {
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 12px;
      overflow-wrap: anywhere;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      min-height: 22px;
      border-radius: 999px;
      border: 1px solid var(--line);
      padding: 0 8px;
      font-size: 12px;
      color: var(--muted);
      background: #fff;
    }
    .ok { color: var(--green); }
    .warn { color: var(--gold); }
    .bad { color: var(--red); }
    .muted {
      color: var(--muted);
      font-size: 13px;
      overflow-wrap: anywhere;
    }
    pre {
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      margin: 0;
      font-size: 12px;
      color: var(--muted);
    }
    @media (max-width: 900px) {
      header, main {
        grid-template-columns: 1fr;
      }
      .metrics {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      .feed {
        max-height: none;
      }
    }
  </style>
</head>
<body>
  <div class="shell">
    <header>
      <div>
        <h1>PowerClaw</h1>
        <div id="health" class="status-line">Connecting</div>
      </div>
      <div class="auth-row">
        <input id="token" type="password" autocomplete="off" placeholder="Bearer token">
        <button id="save-token">Save</button>
      </div>
    </header>
    <main>
      <section class="stack">
        <div class="panel">
          <h2>Turn</h2>
          <form id="turn-form" class="composer">
            <input id="session-id" placeholder="Session id">
            <textarea id="message" placeholder="Message"></textarea>
            <div class="row">
              <button class="primary" type="submit">Send</button>
              <button type="button" id="repo-workflow">Repo Operator</button>
            </div>
            <pre id="response"></pre>
          </form>
        </div>
        <div class="panel">
          <h2>Approvals</h2>
          <div id="approvals"></div>
        </div>
        <div class="panel">
          <h2>Sessions</h2>
          <div id="sessions"></div>
        </div>
      </section>
      <section class="panel">
        <div class="metrics">
          <div class="metric"><strong id="turns">0</strong><span>turns</span></div>
          <div class="metric"><strong id="tools">0</strong><span>tool calls</span></div>
          <div class="metric"><strong id="models">0</strong><span>model calls</span></div>
          <div class="metric"><strong id="failures">0</strong><span>failures</span></div>
        </div>
        <h2>Events</h2>
        <div id="events" class="feed"></div>
      </section>
    </main>
  </div>
  <script>
    const state = {
      token: localStorage.getItem("powerclaw-token") || "",
      sessionId: "",
    };
    const tokenInput = document.getElementById("token");
    tokenInput.value = state.token;
    document.getElementById("save-token").onclick = () => {
      state.token = tokenInput.value.trim();
      localStorage.setItem("powerclaw-token", state.token);
      refresh();
    };
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
    function text(value) {
      return String(value ?? "");
    }
    function renderEmpty(target, label) {
      target.innerHTML = `<div class="event"><div class="muted">${label}</div></div>`;
    }
    async function refresh() {
      try {
        const health = await api("/health");
        document.getElementById("health").textContent = `${health.service} on ${health.workspace}`;
      } catch (err) {
        document.getElementById("health").textContent = `Auth required or offline: ${err.message}`;
      }
      await Promise.allSettled([loadMetrics(), loadEvents(), loadApprovals(), loadSessions()]);
    }
    async function loadMetrics() {
      const metrics = await api("/v1/metrics");
      document.getElementById("turns").textContent = metrics.turns_completed || 0;
      document.getElementById("tools").textContent = metrics.tool_calls || 0;
      document.getElementById("models").textContent = metrics.model_calls || 0;
      document.getElementById("failures").textContent = metrics.failures || 0;
    }
    async function loadEvents() {
      const payload = await api("/v1/events?limit=80");
      const target = document.getElementById("events");
      if (!payload.events.length) return renderEmpty(target, "No events yet");
      target.innerHTML = payload.events.reverse().map(event => `
        <div class="event">
          <div class="event-title">
            <strong>${text(event.event_type)}</strong>
            <span class="pill">${text(event.level)}</span>
          </div>
          <div class="muted">${new Date(event.created_at).toLocaleString()}</div>
          <pre>${text(event.message || JSON.stringify(event.payload, null, 2))}</pre>
        </div>
      `).join("");
    }
    async function loadApprovals() {
      const payload = await api("/v1/approvals?status=pending");
      const target = document.getElementById("approvals");
      if (!payload.requests.length) return renderEmpty(target, "No pending approvals");
      target.innerHTML = payload.requests.map(item => `
        <div class="approval">
          <div class="approval-title">
            <strong>${text(item.kind)}</strong>
            <code>${text(item.id)}</code>
          </div>
          <div><code>${text(item.subject)}</code></div>
          <div class="row">
            <button onclick="resolveApproval('${item.id}', 'approve')">Approve</button>
            <button class="danger" onclick="resolveApproval('${item.id}', 'deny')">Deny</button>
          </div>
        </div>
      `).join("");
    }
    async function loadSessions() {
      const payload = await api("/v1/sessions?limit=12");
      const target = document.getElementById("sessions");
      if (!payload.sessions.length) return renderEmpty(target, "No sessions yet");
      target.innerHTML = payload.sessions.map(session => `
        <button class="session" onclick="selectSession('${session.session_id}')">
          <span class="session-title"><strong>${text(session.platform)}</strong><code>${text(session.session_id)}</code></span>
          <span class="muted">${new Date(session.updated_at).toLocaleString()}</span>
        </button>
      `).join("");
    }
    async function resolveApproval(id, action) {
      await api(`/v1/approvals/${id}/${action}`, {method: "POST", body: "{}"});
      refresh();
    }
    function selectSession(id) {
      state.sessionId = id;
      document.getElementById("session-id").value = id;
    }
    document.getElementById("turn-form").onsubmit = async (event) => {
      event.preventDefault();
      const message = document.getElementById("message").value.trim();
      const sessionId = document.getElementById("session-id").value.trim();
      if (!message) return;
      const payload = {message};
      if (sessionId) payload.session_id = sessionId;
      const turn = await api("/v1/turn", {method: "POST", body: JSON.stringify(payload)});
      selectSession(turn.session_id);
      document.getElementById("response").textContent = turn.response;
      refresh();
    };
    document.getElementById("repo-workflow").onclick = async () => {
      const objective = document.getElementById("message").value.trim() || "Inspect this workspace and prepare the next EC2-ready step.";
      const sessionId = document.getElementById("session-id").value.trim();
      const payload = {objective};
      if (sessionId) payload.session_id = sessionId;
      const turn = await api("/v1/workflows/repo-operator", {method: "POST", body: JSON.stringify(payload)});
      selectSession(turn.session_id);
      document.getElementById("response").textContent = turn.response;
      refresh();
    };
    refresh();
    setInterval(refresh, 5000);
  </script>
</body>
</html>
"""
