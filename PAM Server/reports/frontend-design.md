# Frontend Design — PAM Console

> Source: `frontend_html.py` (1342 lines) at `/home/administrator/pam-server/backend-python/`  
> Single-page application embedded as a Python string, served at `GET /`

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Page-by-Page Breakdown](#2-page-by-page-breakdown)
3. [Theming System](#3-theming-system)
4. [Navigation and State Management](#4-navigation-and-state-management)
5. [WebSocket-Based Terminal UI](#5-websocket-based-terminal-ui)
6. [Design Rationale](#6-design-rationale)

---

## 1. Architecture Overview

The frontend is a **single-file SPA** (Single Page Application) built with vanilla JavaScript and CSS, embedded directly inside the Python backend at `frontend_html.py:2` as the constant `FRONTEND_HTML`. It is served by a single FastAPI route:

```python
@app.get("/")
async def root():
    return HTMLResponse(FRONTEND_HTML)
```

**Key characteristics:**

| Property | Value |
|----------|-------|
| Framework | None (vanilla JS) |
| CSS methodology | CSS custom properties (variables) |
| Routing | Client-side hash-less, flat switch in `navigateTo()` |
| State | Global JavaScript variables held in memory |
| Auth | JWT access token stored in `localStorage` |
| Backend communication | `fetch()` API wrapper + WebSocket for terminal |
| Bundle size | ~45 KB (CSS + HTML + JS, all one file) |
| External dependencies | None |

**File structure inside the single document:**

```
FRONTEND_HTML
├── <style>          (lines 8-187)   — All CSS (~180 lines)
├── <body>           (lines 189-274) — Static HTML shell (~85 lines)
└── <script>         (lines 276-1340) — All JavaScript (~1060 lines)
    ├── State            (lines 278-291)
    ├── Auth             (lines 295-394)
    ├── Navigation       (lines 397-421)
    ├── API Helper       (lines 425-445)
    ├── Dashboard        (lines 449-603)
    ├── Companies        (lines 607-671)
    ├── Users            (lines 675-735)
    ├── Servers          (lines 739-869)
    ├── My Requests      (lines 873-917)
    ├── Pending Approvals (lines 921-956)
    ├── Recordings       (lines 960-1011)
    ├── Audit Logs       (lines 1015-1058)
    ├── Settings         (lines 1062-1118)
    ├── Notifications    (lines 1122-1161)
    ├── Terminal/Session (lines 1165-1275)
    ├── Modal            (lines 1279-1290)
    └── Helpers + Init   (lines 1294-1340)
```

---

## 2. Page-by-Page Breakdown

### 2.1 Dashboard (`renderDashboard`, lines 449-603)

Two variants based on role:

**User role dashboard** (`/dashboard/user-stats`):
- Welcome message with formatted date badge
- Three stat cards: Pending Requests, Approved, Servers Available — each with distinct gradient backgrounds (blue, green)
- Recent Requests list — each row shows server name, access level, duration, relative timestamp, and status badge
- Recent Activity feed — each event has a severity dot (red/yellow/blue) and event type badge

**Admin/Superuser dashboard** (`/dashboard/stats`):
- Six stat cards in a 3×2 grid: Admins, Companies, Users, Servers, Requests, Active Sessions
- Two alert cards for Critical and High alerts (red/orange gradient backgrounds with border accents)
- Companies sublist under the Companies stat card
- Recent Activities feed (last 8 events) with severity dot, event type badge, detail text, and performer name

### 2.2 Servers (`renderServers`, lines 739-770)

- Collapsible card list — each server is a card with status badge, name, IP, and an expand arrow
- Superusers see an **"Add Target Server"** button at top
- Server detail modal (`showServerDetail`, lines 773-803) renders a 2-column grid:
  - All users see: IP Address, Company
  - Admins/superusers also see: Port, OS, Connection Types, Server ID (hidden from `user` role)
  - "Request Access" button (active servers) or "Unavailable" (inactive)
  - "Delete Server" for superusers
- Request flow: clicking "Request Access" first checks for an active request (`/requests/check-active/:id`). If found, opens terminal directly. Otherwise, shows a request form modal with duration, access level (`user`/`root`), and description fields.

### 2.3 My Requests (`renderMyRequests`, lines 873-917)

- Tabbed filter bar: All / Pending / Approved / Rejected (passes `?status=` query param)
- Table with columns: ID (truncated), Server, Level (badge), Duration, Status (badge), Requested (relative time), Actions
- Context-sensitive actions:
  - Pending: "Cancel" button
  - Approved + not expired: "Connect" button → opens terminal
  - Any status: "Delete" button
- Empty state: "No requests found" message

### 2.4 Pending Approvals (`renderApprovals`, lines 921-956)

- Accessible only to `admin` and `superuser` roles; renders "Access denied" for `user`
- Table with columns: Requester, Server, Company, Level, Duration, Requested (relative time), Actions
- Action buttons: "Approve" (green) / "Reject" (red), each with confirmation dialog
- Empty state: "No pending approvals" message

### 2.5 Users (`renderUsers`, lines 675-735)

- Superusers fetch all users from `/users/all`; admins fetch scoped from `/users`
- Table with columns: Name, Username, Role (purple/blue/green badge), Company, Status (green/red badge), Last Login, Actions
- **Add User** modal: Full Name, Username, Password (min 6 chars), Role selector (admin users can only create `user` role), Company selector (admin users are locked to their company)
- **Toggle status** button: Deactivate/Activate (yellow/green, calls `PATCH /users/:id/status`)
- Role badges: superuser = purple, admin = blue, user = green

### 2.6 Audit Logs (`renderAuditLogs`, lines 1015-1058)

- Server-side pagination: 50 rows per page, with Previous/Next buttons and page counter
- "Export CSV" button opens `/api/audit-logs/export` in a new tab
- "Clear Filters" resets page to 0
- Table: Timestamp, Event (blue badge), By (actor), Target (truncated ID), Details, Security Status (red/yellow/blue badge), Action
- Context action: Suspicious events (`suspicious_command`, `suspicious_output`) get a red "Terminate" button that ends the associated session

### 2.7 Recordings (`renderRecordings`, lines 960-1011)

- Accessible to `admin` and `superuser` only
- Table: User, Server, Company, Duration (calculated from start/end timestamps), Date, Actions
- "Play" button fetches the session recording data (`/sessions/:id/recording`) and opens a replay modal
- Replay modal:
  - Black background, monospace font, green text (`#00ff00`)
  - "Play" button resets the replay and starts stepping through the recording array
  - Uses timed delays based on original entry timestamps (capped at 100ms, min 15ms)
  - Output events append to the replay div; input events are skipped in visual replay

### 2.8 Settings (`renderSettings`, lines 1062-1118)

Two-column card layout:
- **Change Username**: current username (disabled), new username input, save button with feedback message
- **Change Password**: current password, new password, confirm password fields, save button with validation (match check + min length)
- **Billing Account** (hidden for `user` role): displays balance (green) and price-per-user, loaded from `/billing/my`

---

## 3. Theming System

### 3.1 CSS Custom Properties (lines 9-31)

The theme is defined entirely through CSS custom properties on `:root` (dark) and `[data-theme="light"]` (light). Every visual element references these variables rather than hardcoded colors.

**Dark theme (`:root`, default):**

| Variable | Value | Purpose |
|----------|-------|---------|
| `--bg` | `#0f172a` | Page background (slate-900) |
| `--card-bg` | `#1e293b` | Card/surface background (slate-800) |
| `--card-alt` | `#1a2235` | Card gradient variant |
| `--border` | `#334155` | Borders and dividers (slate-700) |
| `--text` | `#e2e8f0` | Primary text (slate-200) |
| `--muted` | `#94a3b8` | Secondary text (slate-400) |
| `--text-muted` | `#64748b` | Subtle text (slate-500) |
| `--primary` | `#3b82f6` | Primary accent (blue-500) |
| `--primary-dark` | `#2563eb` | Primary hover/shadow (blue-600) |
| `--primary-light` | `#60a5fa` | Primary text/light (blue-400) |
| `--danger` | `#dc2626` | Error/destructive (red-600) |
| `--success` | `#16a34a` | Success (green-600) |
| `--warning` | `#d97706` | Warning (amber-600) |
| `--sidebar-bg` | `#0f172a` | Sidebar background (same as page) |
| `--accent-bg` | `#1e3a5f` | Subtle accent highlight |
| `--input-bg` | `#1e293b` | Input field background |
| `--hover-bg` | `#1e293b` | Hover/active state |
| `--badge-green-*` | various | Green badge variants |
| `--badge-red-*` | various | Red badge variants |
| `--badge-yellow-*` | various | Yellow badge variants |
| `--badge-blue-*` | various | Blue badge variants |
| `--badge-purple-*` | various | Purple badge variants (superuser role) |

**Light theme (`[data-theme="light"]`):**

Inverts the palette using the same variable names:

| Variable | Dark Value | Light Value | Difference |
|----------|-----------|-------------|------------|
| `--bg` | `#0f172a` | `#f1f5f9` | Nearly inverted |
| `--card-bg` | `#1e293b` | `#ffffff` | Dark surfaces → white |
| `--text` | `#e2e8f0` | `#1e293b` | Light text → dark |
| `--border` | `#334155` | `#e2e8f0` | Dark borders → light |
| `--input-bg` | `#1e293b` | `#ffffff` | Dark inputs → white |
| Badge backgrounds | Dark tints | Light tints | Inverted opacity |

### 3.2 Theme Toggle Implementation (lines 335-352, 1310-1317)

The toggle is a custom switch widget in the top bar (lines 105-109):

```html
<div id="theme-toggle" onclick="toggleTheme()" data-state="dark">
  <div class="toggle-track">
    <div class="toggle-thumb"></div>
    <span class="toggle-label">D</span>
    <span class="toggle-label">L</span>
  </div>
</div>
```

The thumb position is controlled by CSS:

```css
#theme-toggle[data-state="light"] .toggle-thumb { left: 28px; }
```

**Toggle logic** (`toggleTheme`, line 340):
1. Reads the current `data-theme` attribute on `<html>`
2. If `light` → removes attribute (reverts to `:root` dark), sets toggle state to `dark`
3. If `dark` → sets `data-theme="light"`, sets toggle state to `light`
4. Persists preference to `localStorage` key `pam_theme`

**Initialization** (lines 1310-1317):
```javascript
const savedTheme = localStorage.getItem('pam_theme');
if (savedTheme === 'light') {
  document.documentElement.setAttribute('data-theme', 'light');
  setThemeToggle('light');
}
```

### 3.3 Theme Usage Patterns

All CSS selectors reference variables:

```css
body {
  background: var(--bg);
  color: var(--text);
}
.card {
  background: linear-gradient(135deg, var(--card-bg), var(--card-alt));
  border: 1px solid var(--border);
}
```

Gradients are layered on top of themed backgrounds for visual depth. Button gradients use hardcoded colors (e.g., `linear-gradient(135deg, var(--primary-dark), var(--primary))`) so they remain vibrant regardless of theme. Badge colors use dedicated `--badge-*` variable pairs for both themes.

---

## 4. Navigation and State Management

### 4.1 Global State (lines 278-291)

The entire application state lives in module-level variables:

```javascript
let user = null;         // Decoded user object from login response
let token = null;        // JWT access token string
let companies = [];      // Cached companies list
let servers = [];        // Cached servers list
let users = [];          // Cached users list
let requests = [];       // Cached requests list
let notifications = [];  // Cached notifications list
let currentPage = 'dashboard';  // Active page identifier
let ws = null;           // General-purpose WebSocket (unused)
let terminalSession = null;     // Active terminal session ID
let terminalTimer = null;       // setInterval handle for countdown
let termWs = null;       // Terminal WebSocket connection
let terminalData = [];   // Terminal recording buffer (unused)
let replayIndex = 0;     // Recording replay cursor
let replayTimeout = null;       // setTimeout handle for replay
let auditPage = 0;       // Audit log pagination offset
```

There is no state management library. Pages fetch fresh data from the API each time they render (no stale cache problem), but the cached arrays enable modal detail lookups without additional network requests.

### 4.2 Routing (lines 397-421)

Routing is hash-less. Clicking a sidebar link calls `navigateTo(page)` directly:

```javascript
document.querySelectorAll('#nav a').forEach(a => {
  a.addEventListener('click', e => {
    e.preventDefault();
    navigateTo(a.dataset.page);
  });
});
```

The `navigateTo()` function (line 404) is a flat switch statement:

```javascript
function navigateTo(page) {
  if (!user) return;
  currentPage = page;
  updateSidebar();
  switch(page) {
    case 'dashboard': renderDashboard(); break;
    case 'companies': user.role === 'superuser' ? renderCompanies() : content.innerHTML = '<p>Access denied</p>'; break;
    case 'users': renderUsers(); break;
    case 'servers': renderServers(); break;
    case 'my-requests': renderMyRequests(); break;
    case 'approvals': user.role !== 'user' ? renderApprovals() : ...;
    case 'recordings': user.role !== 'user' ? renderRecordings() : ...;
    case 'audit': user.role !== 'user' ? renderAuditLogs() : ...;
    case 'settings': renderSettings(); break;
  }
}
```

Each page render function replaces `#content` inner HTML entirely. There is no virtual DOM or diffing — every navigation is a full content swap. The advantage is simplicity: zero framework overhead, and the browser's garbage collector cleans up detached DOM nodes immediately.

### 4.3 Sidebar Role Visibility (lines 373-393)

The `updateSidebar()` function controls which nav items appear based on the user's role:

```html
<a href="#" data-page="companies" class="role-su">       <!-- superuser only -->
<a href="#" data-page="users" class="role-su role-ad">  <!-- superuser + admin -->
<a href="#" data-page="approvals" class="role-su role-ad">
<a href="#" data-page="recordings" class="role-su role-ad">
<a href="#" data-page="audit" class="role-su role-ad">
```

Logic:
- `dashboard`, `servers`, `my-requests`, `settings` — always visible
- `superuser` — sees everything
- `admin` — sees items with both `role-su` and `role-ad` classes, plus the universal items
- `user` — sees only the universal items

The same guard is duplicated in `navigateTo()` for pages that role-based CSS hiding could be bypassed via direct URL manipulation.

### 4.4 API Helper (lines 425-437)

```javascript
async function api(url, opts = {}) {
  const headers = {'Content-Type': 'application/json', ...opts.headers};
  if (token) {
    headers['Authorization'] = 'Bearer ' + token;
    const sep = url.includes('?') ? '&' : '?';
    url += sep + 'token=' + encodeURIComponent(token);
  }
  const res = await fetch(API + url, {...opts, headers});
  if (res.status === 401) { /* clear session and reload */ }
  const text = await res.text();
  try { return {ok: res.ok, data: JSON.parse(text)}; }
  catch { return {ok: res.ok, data: text}; }
}
```

The token is sent in **two ways** simultaneously: as an `Authorization: Bearer` header and as a query parameter (`?token=`). This ensures the WebSocket handshake (which cannot set custom headers via the browser `WebSocket` API) still receives the token. The `401` check auto-logs out if the token expires.

### 4.5 Auth Flow (lines 300-365)

1. **Login**: `POST /api/auth/login` → stores `access_token` and `user` object in `localStorage`, hides login page, shows app shell
2. **Auto-login** (init, lines 1319-1331): on page load, checks `localStorage` for `pam_token` and `pam_user`. If both exist, skips login page and calls `showApp()`
3. **Logout**: clears `localStorage`, nullifies state, shows login page

### 4.6 Modal System (lines 1279-1290)

A generic modal creates an overlay with a centered card:

```javascript
function showModal(html) {
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = '<div class="modal">' + html + '</div>';
  overlay.addEventListener('click', e => { if (e.target === overlay) closeModal(); });
  document.body.appendChild(overlay);
}
```

Closing is handled by clicking the overlay backdrop or calling `closeModal()` which removes the overlay and clears any active replay timeout.

### 4.7 Notification System (lines 1122-1161)

- **Unread count badge**: polled on app load via `/notifications/unread-count`, displayed as a red circle on the bell icon
- **Notification list**: fetched from `/notifications?limit=20`
- **Mark read**: clicking a notification calls `PATCH /notifications/:id/read` and navigates to the linked page
- **Mark all read**: `POST /notifications/read-all`

---

## 5. WebSocket-Based Terminal UI

### 5.1 Terminal Shell (lines 1165-1236)

The terminal is a full-screen overlay (`#terminal-wrap`) positioned with `position: fixed; z-index: 3000`. It has three structural zones:

**Header bar** (`#terminal-header`, lines 181-184):
- Badge: "SSH ACCESS" in blue
- Info: `username@server:<id_prefix>` (e.g., `john@server:a1b2c3d4`)
- Timer: live countdown of remaining session time (green)
- Actions: Terminate (red) and Close (secondary) buttons

**Output area** (`#term-output`):
- Flex-grows to fill available space
- `overflow-y: auto` for scrollable history
- Monospace font, 14px, green text (`#4ade80`) on dark background (`#0f172a`)
- `white-space: pre-wrap; word-break: break-all` to handle long terminal lines

**Input line** (`#term-inputline`):
- Fixed at bottom, separated by a subtle border
- Prompt prefix (dynamically updated to `username@server_prefix:~$` after SSH connects)
- Text input with monospace styling, auto-focused on connect

### 5.2 WebSocket Connection (lines 1176-1177)

```javascript
const wsUrl = (location.protocol === 'https:' ? 'wss://' : 'ws://')
  + location.host + '/ws/terminal?token=' + token;
termWs = new WebSocket(wsUrl);
```

The WebSocket URL uses `location.host` to match the current origin, with protocol auto-detection (`ws://` or `wss://`). The JWT token is passed as a query parameter (workaround for the browser WebSocket API's inability to set custom headers).

### 5.3 Message Protocol

All messages are JSON. The client sends two message types:

| Sent Message | `action` / `type` | Payload |
|-------------|-------------------|---------|
| Join session | `action: "join_session"` | `requestId`, `serverId` |
| Terminal input | `type: "terminal_input"` | `data: "<command>\n"` |

The server sends five message types:

| Received Message | When | Display |
|-----------------|------|---------|
| `terminal_output` | SSH stdout/stderr | Appends `data` to output div |
| `session_created` | Backend session record created | Stores `sessionId`, starts timer |
| `ssh_ready` | SSH connection established | Shows message, updates prompt, focuses input |
| `session_ended` | Session terminated or expired | Shows reason, stops timer |
| `session_error` | Error during connection | Shows error text in red |

### 5.4 Input Handling (lines 1222-1235)

```javascript
document.getElementById('term-input').addEventListener('keydown', function handleTermKey(e) {
  if (e.key === 'Enter') {
    const cmd = inp.value;
    const text = cmd + '\n';
    termOut.textContent += '\n' + document.getElementById('term-prompt').textContent + ' ' + cmd + '\n';
    termWs.send(JSON.stringify({type: 'terminal_input', data: text}));
    inp.value = '';
    e.preventDefault();
  }
});
```

On Enter:
1. Reads the current input value
2. Writes a local echo line (`prompt + command`) to the output
3. Sends the command (with newline) to the server over WebSocket
4. Clears the input field

The server sends back the actual terminal output (including any echo from the SSH server), which is appended as raw text. The local echo ensures immediate visual feedback; the server echo may duplicate or differ.

### 5.5 Session Timer (lines 1238-1260)

```javascript
function showTimer(requestId) {
  terminalTimer = setInterval(async () => {
    const {ok, data} = await api('/requests?status=approved');
    const req = data.find(r => r.id === requestId);
    const remaining = Math.floor((new Date(req.expires_at) - new Date()) / 1000);
    if (remaining <= 0) {
      document.getElementById('term-timer').textContent = 'EXPIRED';
      terminateSession();
    } else {
      document.getElementById('term-timer').textContent = 'm:ss';
    }
  }, 1000);
}
```

The timer polls the request's `expires_at` every second. When remaining time hits zero, it displays "EXPIRED" and calls `terminateSession()`. The timer is formatted as `M:SS` and styled in green (`#4ade80`).

### 5.6 Session Termination (lines 1262-1275)

```javascript
function terminateSession() {
  if (terminalSession) {
    api('/sessions/' + terminalSession + '/terminate', {method:'POST'});
  }
  if (termWs) {
    termWs.send(JSON.stringify({type: 'terminate_session'}));
    termWs.close();
  }
  closeTerminal();
}

function closeTerminal() {
  document.getElementById('terminal-wrap').classList.remove('active');
  if (termWs) { termWs.close(); termWs = null; }
  if (terminalTimer) { clearInterval(terminalTimer); terminalTimer = null; }
  terminalSession = null;
}
```

`terminateSession()` hits the backend API, sends a terminate message over WebSocket, then cleans up. `closeTerminal()` is gentler (just hides the overlay and closes the socket). Both reset WebSocket, timer, and session references.

### 5.7 Reconnect Behavior

There is no explicit reconnect logic in the current implementation. If the WebSocket closes unexpectedly (network issue, server restart), the `onclose` handler appends "Connection closed" to the output and the user must manually reconnect by requesting access again. The session on the backend may still be active — the user can check active requests and click "Connect" again.

---

## 6. Design Rationale

### 6.1 Why a Single-File Embedded SPA?

The frontend is delivered as a Python string constant inside the backend rather than as a separate build pipeline with a modern framework (React, Vue, Svelte). This was an intentional engineering decision driven by operational constraints:

| Concern | Single-File SPA | Build-Tool-Based SPA |
|---------|----------------|---------------------|
| **Deployment** | One file to deploy — the backend binary | Requires separate build step, static file serving, or CDN |
| **Dependencies** | Zero — no npm install, no node_modules | Requires Node.js ≥18, npm/yarn, install step |
| **Build time** | None — edit and reload | 30-120s per production build |
| **Cold start** | Instant — no bundler overhead | Requires build toolchain availability |
| **Surface area** | Single file, single route | Multiple files, multiple entry points |
| **Cache behavior** | Loaded once per backend start | Cache-busting hashes for each deploy |
| **State management** | Global variables — no framework overhead | React hooks / Vue reactive system |
| **Terminal rendering** | Direct DOM manipulation — no virtual DOM | Requires integration with xterm.js or custom component |

**The deciding factor:** The target deployment environment is a lightweight VM (potentially containerized) where running `npm install` would add 200+ MB of dependencies, several minutes of build time, and a second service to manage (or a multi-stage Docker build). By embedding the frontend directly in the Python backend, the entire application ships as a single Python file that can be copied to any Linux VM and run with `python main.py`.

### 6.2 Trade-Offs Accepted

| Trade-Off | Impact | Mitigation |
|-----------|--------|------------|
| No component reusability | Similar UI patterns are duplicated (e.g., table rendering) | Template literals with mapping patterns keep it readable |
| No hot module replacement | Every CSS/JS change requires a full page reload | Backend auto-reloads on file change (FastAPI `--reload`) |
| Manual DOM management | Risk of memory leaks from orphaned event listeners | All event handlers use `onclick` attributes or scoped listeners |
| No build-time validation | JS errors surface at runtime, not at compile time | Consistent patterns and manual testing |
| Larger backend response | ~45 KB HTML string per request | Gzip compression in Nginx/proxy layer |
| No code splitting | Entire UI loads on every page visit | Single-file is <50 KB — negligible compared to typical page weight |

### 6.3 When This Approach Excels

- **Prototyping**: changes take seconds (edit text, reload browser)
- **Air-gapped deployments**: no package registry access needed
- **Embedded/config-tool UIs**: admin panels that ship with the backend binary
- **Single-developer projects**: one person maintains both backend and frontend in one file
- **Minimal infrastructure**: no static file server, no CDN, no build server

### 6.4 Alternative Frontend Implementation

An alternative frontend implementation exists in the `frontend/` folder for future reference. It uses React with component-based architecture and was developed alongside this embedded SPA. The embedded SPA was chosen as the primary delivery mechanism for the deployment considerations detailed above, while the React implementation remains available for teams that prefer a framework-based approach or need to extend the UI with complex interactive components.
