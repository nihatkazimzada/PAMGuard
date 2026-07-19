# Frontend Deep-Dive: PAM Console (Embedded SPA + React Source)

> Generated from codebase snapshot at `/home/administrator/pam-server/`  
> Total frontend LOC: ~1342 lines embedded SPA (`frontend_html.py`) + ~1680 lines React source (`frontend/src/`) + config files

---

## 1. Architecture Overview

The PAM Console has **two frontends** — only one is actually served:

| Aspect | Embedded SPA | React Frontend |
|--------|-------------|----------------|
| **File** | `backend-python/frontend_html.py` (1342 lines) | `frontend/` (~40 source files) |
| **Delivery** | Raw HTML string returned by FastAPI at `GET /` | Vite build expected at `frontend/dist/` |
| **Status** | **Served live** — this is what users see | **Unbuildable** — `npm install` hangs (filesystem timeout) |
| **Framework** | None — vanilla JS SPA | React 18 + TypeScript + Vite 5 + Tailwind CSS 3 |
| **Terminal** | Custom scrollable `<div>` with `white-space: pre-wrap` | xterm.js with FitAddon, Dracula theme, ResizeObserver |
| **Router** | Manual `navigateTo()` switch/case on `window.location` | React Router v6 with `<Routes>` |
| **State** | Global JS variables | React Context (`AuthContext`), `useState`/`useEffect` |
| **Styling** | Inline CSS with CSS variables | Tailwind utility classes + custom CSS |

**Why the embedded SPA won:** The project was initially developed with a React frontend (Vite + TypeScript + Tailwind), but `npm install` consistently timed out after 20+ minutes on this filesystem. The Vite dev server was also unresponsive. As a workaround, the entire UI was inlined as a raw HTML string in `frontend_html.py` — a single-file vanilla JS SPA that requires no build step, no dependencies, and zero cold-start time.

---

## 2. Embedded SPA Deep-Dive

### 2.1 File Structure

The entire frontend lives in one Python triple-quoted string:

```
frontend_html.py (1342 lines)
├── HTML shell (<html>, <head>, <body>)       lines 1-189
├── Inline CSS (all styles in <style> tag)     lines 8-187
├── Sidebar + Topbar HTML                      lines 190-213
├── Terminal container (hidden by default)     lines 214-220
├── Login page HTML                            lines 221-236
└── <script> (all JS logic)                    lines 237-1340
    ├── Global state variables                 lines 238-247
    ├── Login handler                          lines 249-293
    ├── App init / auth restore                lines 295-403
    ├── navigateTo() routing                   lines 404-421
    ├── API helper                             lines 423-437
    ├── Toast system                           lines 439-445
    ├── Dashboard (user + admin)               lines 447-603
    ├── Companies page                         lines 605-671
    ├── Users page                             lines 673-735
    ├── Servers page                           lines 737-869
    ├── My Requests page                       lines 871-917
    ├── Approvals page                         lines 919-956
    ├── Session Recordings page                lines 958-1011
    ├── Audit Logs page                        lines 1013-1058
    ├── Settings page                          lines 1060-1118
    ├── Notifications                          lines 1120-1161
    ├── Terminal / WebSocket                   lines 1163-1275
    ├── Modal system                           lines 1277-1290
    ├── Helpers (timeAgo, $)                   lines 1292-1306
    └── Init sequence                          lines 1308-1339
```

### 2.2 CSS Theme System

The theming engine uses **pure CSS variables with `[data-theme]` attribute switching** — no Tailwind, no Sass:

```css
:root {
  --bg: #0f172a;          --card-bg: #1e293b;
  --border: #334155;      --text: #e2e8f0;
  --primary: #3b82f6;     --danger: #dc2626;
  --success: #16a34a;
  /* ... 30+ variables for dark mode */
}
[data-theme="light"] {
  --bg: #f1f5f9;          --card-bg: #ffffff;
  --border: #e2e8f0;      --text: #1e293b;
  /* ... 30+ variables for light mode */
}
```

The **toggle switch** is a custom `<button>` with a track and thumb:

```html
<button id="theme-toggle" data-state="dark">
  <div class="toggle-track">
    <span class="toggle-label">DARK</span>
    <span class="toggle-label">LIGHT</span>
    <div class="toggle-thumb"></div>
  </div>
</button>
```

CSS controls the thumb position via `[data-state="light"] .toggle-thumb { left: 28px; }` and a `left: 0.25s ease` transition. The JS handler flips the attribute on `<html>` and persists to `localStorage`:

```javascript
document.getElementById('theme-toggle').addEventListener('click', function() {
  const isLight = document.documentElement.getAttribute('data-theme') === 'light';
  document.documentElement.setAttribute('data-theme', isLight ? 'dark' : 'light');
  localStorage.setItem('pam_theme', isLight ? 'dark' : 'light');
  setThemeToggle(isLight ? 'dark' : 'light');
});
```

On page load, the init sequence at line 1310 reads `localStorage.getItem('pam_theme')` and applies it before any content renders, preventing flash-of-wrong-theme.

**Badge color tokens** use semantic `--badge-*-bg` / `--badge-*-text` CSS variables that swap between dark and light mode — green badges go from dark green bg to light green bg, etc.

### 2.3 Page Routing

The SPA has no hash-based or history-based router. Instead, `navigateTo(page)` is a simple switch statement:

```javascript
function navigateTo(page) {
  if (!user) return;
  currentPage = page;
  updateSidebar();
  const content = document.getElementById('content');
  switch(page) {
    case 'dashboard': renderDashboard(); break;
    case 'companies': user.role === 'superuser' ? renderCompanies()
      : (content.innerHTML = '<p>Access denied</p>'); break;
    case 'users': renderUsers(); break;
    case 'servers': renderServers(); break;
    case 'my-requests': renderMyRequests(); break;
    case 'approvals': user.role !== 'user' ? renderApprovals()
      : (content.innerHTML = '<p>Access denied</p>'); break;
    case 'recordings': user.role !== 'user' ? renderRecordings()
      : (content.innerHTML = '<p>Access denied</p>'); break;
    case 'audit': user.role !== 'user' ? renderAuditLogs()
      : (content.innerHTML = '<p>Access denied</p>'); break;
    case 'settings': renderSettings(); break;
    default: renderDashboard();
  }
}
```

The sidebar nav links use `data-page` attributes:

```html
<a href="#" data-page="dashboard">Dashboard</a>
<a href="#" data-page="companies" class="role-su">Company Tenants</a>
<a href="#" data-page="users" class="role-su role-ad">User Registry</a>
<a href="#" data-page="servers">Servers</a>
<!-- ... -->
```

And the `updateSidebar()` function shows/hides nav items based on user role by checking CSS classes (`role-su`, `role-ad`). This is purely cosmetic — the `navigateTo()` switch also enforces access at the function-call level.

**Active page highlighting** is done by iterating all nav links and adding/removing the `active` CSS class.

### 2.4 State Management

No React, no Redux, no reactive system. State is managed in **6 global JS variables**:

```javascript
let token = null;
let user = null;
let companies = [];
let users = [];
let servers = [];
let requests = [];
// Terminal state
let termWs = null;
let terminalSession = null;
let terminalTimer = null;
// Replay state
let replayIndex = 0;
let replayTimeout = null;
// Audit pagination
let auditPage = 0;
```

Every page render function is impure — it re-reads the global state (or fetches fresh data from the API) and replaces `#content` innerHTML. This means:
- **No diffing** — every navigation is a full DOM replacement
- **No component isolation** — event listeners are inline `onclick` attributes requiring globally-scoped functions
- **Accidental global mutation** — any function can overwrite state

However, this simplicity was a deliberate trade-off to avoid the build-tool dependency chain.

### 2.5 API Communication

All HTTP calls go through a single `api()` wrapper:

```javascript
async function api(url, opts = {}) {
  const headers = {'Content-Type': 'application/json', ...opts.headers};
  if (token) {
    headers['Authorization'] = 'Bearer ' + token;
    const sep = url.includes('?') ? '&' : '?';
    url += sep + 'token=' + encodeURIComponent(token);
  }
  const res = await fetch(API + url, {...opts, headers});
  if (res.status === 401) {
    localStorage.removeItem('pam_token');
    localStorage.removeItem('pam_user');
    location.reload();
  }
  const text = await res.text();
  try { return {ok: res.ok, data: text ? JSON.parse(text) : null, status: res.status}; }
  catch { return {ok: res.ok, data: text, status: res.status}; }
}
```

Key design decisions:
- **Token in URL AND header** — the query param `?token=` is a fallback for WebSocket connections (which can't set custom headers in the browser's old `WebSocket` API). The backend checks the query param first.
- **401 auto-logout** — any 401 response clears storage and reloads the page to show the login screen.
- **No typed responses** — unlike the React frontend's generic `request<T>()` with TypeScript generics, the SPA returns `{ok, data, status}` and each render function manually juggles the shape.

### 2.6 Dashboard (`renderDashboard`, lines 447-603)

The dashboard has **two completely different views** depending on role:

**User view** — 3 stat cards (Pending Requests, Approved, Servers Available) with gradient backgrounds and SVG icons, then a Recent Requests list and Recent Activity timeline. Example card:

```javascript
`<div style="background:linear-gradient(135deg,#1e3a5f,#1e40af);border-radius:14px;
    padding:18px 20px;display:flex;align-items:center;gap:14px;box-shadow:0 4px 15px rgba(30,58,95,.3)">
  <div style="background:rgba(255,255,255,.12);width:44px;height:44px;border-radius:12px;
    display:flex;align-items:center;justify-content:center;flex-shrink:0">
    <svg><!-- clock icon --></svg>
  </div>
  <div>
    <div style="font-size:28px;font-weight:700;color:#fff">${s.pendingCount}</div>
    <div style="font-size:12px;color:#fbbf24;font-weight:500">Pending Requests</div>
  </div>
</div>`
```

**Admin/Superuser view** — 6 stat cards (Admins, Companies with names, Users, Servers, Requests, Active Sessions) plus 2 alert cards (Critical Alerts in red gradient, High Alerts in amber gradient). Then a Recent Activities table with colored dot indicators for severity.

Data is fetched from either `/dashboard/user-stats` or `/dashboard/stats` depending on role.

### 2.7 Companies Page (`renderCompanies`, lines 605-671)

Superuser-only CRUD:
- **List** — table with name, tenant ID, domain, server count, user count, delete button
- **Add** — modal with name * (required), auto-generated tenant ID (readonly), industry dropdown, domain, contact email/phone, billing email
- **Delete** — confirm dialog, then `DELETE /companies/:id`
- **`generateTenantId()`** — `'tnt-' + Math.random().toString(36).substring(2,10) + '-' + Date.now().toString(36)`

### 2.8 Users Page (`renderUsers`, lines 673-735)

- **Superuser** fetches from `/users/all`, sees all users across all companies
- **Admin** fetches from `/users`, sees only their own company's users
- **Add User** modal — admin cannot set role (always `user`), cannot change company (disabled dropdown auto-set to their company)
- **Toggle Status** — activate/deactivate button, never available for superuser accounts

### 2.9 Servers Page (`renderServers`, lines 737-869)

**Server cards** — expandable cards (not a table) with on-demand detail:

```javascript
`<div class="server-card" onclick="showServerDetail('${s.id}')">
  <div class="header">
    <span class="badge ${s.status === 'active' ? 'badge-green' : 'badge-red'}">${s.status}</span>
    <strong style="font-size:15px;flex:1">${s.name}</strong>
    <span class="font-mono text-sm" style="color:#94a3b8">${s.ip}</span>
    <span class="arrow">▼</span>
  </div>
</div>`
```

**Server detail modal** — shows IP + (for admin/superuser) Port, OS, Connection Types, Company, Server ID. The **Port is hidden from regular users** — both in backend response (the endpoint excludes `port`/`os`/`allowed_connection_types` for `user` role) and in the frontend (wrapped in `isAdminOrSuper` conditional).

**Request Access flow:**
1. Click "Request Access" → checks `/requests/check-active/:serverId`
2. If active request exists → opens terminal directly
3. Otherwise → shows request form modal with duration, access level (user/root), description
4. Submit → `POST /requests` → toast notification

### 2.10 My Requests Page (`renderMyRequests`, lines 871-917)

Filter tabs (All / Pending / Approved / Rejected) send `?status=` query parameter. Each row shows truncated ID, server name, access level badge, duration, status badge, time-ago. Actions vary by status:
- Pending → **Cancel** button (`POST /requests/:id/cancel`)
- Approved + not expired → **Connect** button (calls `openTerminal()`)
- Any status → **Delete** button (permanent deletion)

### 2.11 Approvals Page (`renderApprovals`, lines 919-956)

Admin/superuser-only table showing pending requests with:
- Requester name, server, company, level, duration, time-ago
- Approve/Reject buttons calling `POST /requests/:id/approve` and `POST /requests/:id/reject`

### 2.12 Session Recordings Page (`renderRecordings`, lines 958-1011)

Lists completed sessions only (filtered client-side with `.filter(s => s.status !== 'active')`) with duration computed client-side from `started_at`/`ended_at`. "Play" button calls `playRecording()` which:
1. Fetches `/sessions/:id/recording` to get the full JSON recording array
2. Opens a modal with a `<pre>` replay container and a Play button
3. `replayRecording()` iterates through the recording entries with timed delays (min 15ms, max 100ms between entries), appending output data to the container

The recording JSON is an array of `{timestamp, event, data}` objects — the same format used by the backend's session recording system.

### 2.13 Audit Logs Page (`renderAuditLogs`, lines 1013-1058)

Paginated (50 per page) with prev/next buttons and a "Clear Filters" reset. Each log entry shows:
- Timestamp (locale-formatted)
- Event type as blue badge
- Performed by
- Target ID (first 12 chars)
- Action detail text
- Security status badge (red=critical, yellow=warning, blue=info)
- **Terminate button** — appears only for `suspicious_command` or `suspicious_output` events, calls `POST /sessions/:id/terminate`

Optional CSV export via `window.open('/api/audit-logs/export?token=' + token)`.

### 2.14 Settings Page (`renderSettings`, lines 1060-1118)

Two-column layout:
- **Change Username** — input for new username + save button + inline status message
- **Change Password** — current password, new password, confirm + save + inline status
- **Billing Account** — hidden for `user` role, shows balance and price-per-user from `/billing/my`

### 2.15 Notifications (lines 1120-1161)

Bell icon in the topbar shows unread count (fetched from `/notifications/unread-count`). Clicking opens a modal with the notification list:
- Unread items have a blue left border
- Clicking marks as read and optionally navigates to a link
- "Mark All Read" button calls `POST /notifications/read-all`

### 2.16 Terminal / WebSocket Client (lines 1163-1275)

This is the most complex part of the SPA. The `openTerminal(serverId, requestId)` function:

1. **Shows the terminal container** — reveals `#terminal-wrap` (a fixed fullscreen overlay)
2. **Resets the terminal UI** — closes any existing WebSocket, sets the prompt to `user@server:id`
3. **Creates the terminal layout**:
   ```
   #terminal-wrap
     #terminal-header (48px) — badge, info text, timer, close/terminate buttons
     #terminal
       #term-output (flex:1, scrollable, pre-wrap, green-on-black)
       #term-inputline (input row with prompt $ + text input)
   ```
4. **Opens WebSocket** to `ws://host/ws/terminal?token=token`
5. **Sends `join_session`** message with requestId and serverId
6. **Handles incoming messages**:
   - `terminal_output` — appends data to `#term-output`
   - `session_created` — stores sessionId, starts timer
   - `ssh_ready` — updates prompt to `user@server-id:~$`, focuses input
   - `session_ended` — appends reason, stops timer
   - `session_error` / `error` — appends error text in red
7. **Input handling** — Enter key sends command with local echo:
   ```javascript
   document.getElementById('term-input').addEventListener('keydown', function handleTermKey(e) {
     if (e.key === 'Enter') {
       const cmd = inp.value;
       const text = cmd + '\n';
       // Local echo: show prompt + command on output
       termOut.textContent += '\n' + document.getElementById('term-prompt').textContent + ' ' + cmd + '\n';
       // Send to WebSocket
       termWs.send(JSON.stringify({type: 'terminal_input', data: text}));
       inp.value = '';
     }
   });
   ```
8. **Timer** — polls `/requests?status=approved` every second, finds the request by ID, computes remaining time from `expires_at`, auto-terminates when expired
9. **Terminate** — sends `terminate_session` message + calls `POST /sessions/:id/terminate` + closes WebSocket + hides terminal

**Key difference from the React terminal:** The SPA uses a plain `<div>` with `white-space: pre-wrap` and appends text content, while the React version uses `xterm.js` with a canvas-based renderer, cursor blink, color themes, and terminal resize events.

### 2.17 Modal System (lines 1277-1290)

A simple create/remove pattern:

```javascript
function showModal(html) {
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = '<div class="modal">' + html + '</div>';
  overlay.addEventListener('click', e => { if (e.target === overlay) closeModal(); });
  document.body.appendChild(overlay);
}
function closeModal() {
  document.querySelector('.modal-overlay')?.remove();
  if (replayTimeout) { clearTimeout(replayTimeout); replayTimeout = null; }
}
```

- Close on backdrop click (not on modal content click due to `e.target` check)
- Closes replay timeout when modal is dismissed
- Max height 85vh with overflow-y-auto

### 2.18 Toast System (lines 439-445)

```javascript
function toast(msg, type = 'info') {
  const t = document.createElement('div');
  t.className = 'toast toast-' + type;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3000);
}
```

Three types: `toast-success` (green), `toast-error` (red), `toast-info` (blue). Slide-up animation via `@keyframes slideUp`. Positioned fixed bottom-right.

### 2.19 Init Sequence (lines 1308-1339)

On every page load:
1. Read `localStorage.getItem('pam_theme')` → apply data-theme attribute
2. Read `localStorage.getItem('pam_token')` + `pam_user` → if both exist, skip login page, show app
3. Attach Enter-key handlers on login form fields
4. API base URL is set via inline template `${API_BASE}` from Flask/Jinja context (actually from the Python string template — the SPA uses a hardcoded `/api` prefix or a dynamic window.location)

---

## 3. React Frontend (`frontend/src/`)

### 3.1 Tech Stack

| Dependency | Version | Purpose |
|-----------|---------|---------|
| React | ^18.2.0 | UI framework |
| react-dom | ^18.2.0 | DOM renderer |
| react-router-dom | ^6.21.0 | Client-side routing |
| TypeScript | ^5.3.3 | Type safety |
| Vite | ^5.0.8 | Build tool + dev server |
| Tailwind CSS | ^3.4.0 | Utility-first CSS |
| xterm | ^5.3.0 | Canvas-based terminal emulator |
| xterm-addon-fit | ^0.8.0 | Auto-resize for xterm |
| recharts | ^2.10.0 | Charting library |
| lucide-react | ^0.303.0 | SVG icon library |
| clsx | ^2.1.0 | Conditional class names |

### 3.2 Source Files

```
frontend/src/
├── App.tsx              (52 lines)  — Route definitions, 13 routes
├── main.tsx             (16 lines)  — Entry point, BrowserRouter wrapper
├── AuthContext.tsx      (89 lines)  — Auth state, login/logout/refresh
├── api.ts              (345 lines)  — Typed API client, 38 exported functions
├── types.ts            (140 lines)  — TypeScript interfaces (12 types)
├── index.css           (1+ line)    — Tailwind directives
├── components/
│   └── Layout.tsx      (141 lines)  — Sidebar, header, nav filter, user info
└── pages/
    ├── LoginPage.tsx          (130 lines)  — Login form, show/hide password, loading state
    ├── DashboardPage.tsx      (varies)     — Stats + charts
    ├── CompanyTenantsPage.tsx (varies)     — Company CRUD
    ├── UserRegistryPage.tsx   (varies)     — User management
    ├── ServerManagementPage.tsx (varies)   — Server list + detail
    ├── MyRequestsPage.tsx     (varies)     — Request tabs + actions
    ├── PendingApprovalsPage.tsx (varies)   — Approve/reject
    ├── SessionRecordingsPage.tsx (varies)  — Replay list
    ├── AuditLogsPage.tsx      (varies)     — Audit with pagination
    ├── SettingsPage.tsx       (varies)     — Change password/username
    ├── NotificationsPage.tsx  (varies)     — Notification list
    └── SessionWindowPage.tsx  (334 lines)  — xterm.js terminal
```

### 3.3 AuthContext (`AuthContext.tsx`, lines 1-89)

```typescript
interface AuthContextValue {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
}
```

**Flow:**
1. **Mount** — reads `localStorage.getItem('token')` and `localStorage.getItem('user')`
2. If found → calls `api.getMe()` to verify token is still valid → if fails, calls `refresh()` → if refresh also fails, calls `logout()`
3. **Route guard** — watches `location.pathname`; if no token and not on `/login`, redirects to `/login`
4. **Login** — calls `api.login()`, stores token+user in both state and localStorage
5. **Logout** — clears state + localStorage + navigates to `/login`

### 3.4 Layout (`Layout.tsx`, lines 1-141)

Sidebar layout with:
- **Logo** — Shield icon + "PAM Console" branding
- **Nav** — `NavLink` items with role-based filtering via `navItems.filter(item => item.roles.includes(user.role))`:
  - Dashboard (admin/manager only)
  - Company Tenants (admin only)
  - User Registry (admin/manager)
  - Server Management (all roles)
  - My Requests (all roles)
  - Pending Approvals (admin/manager)
  - Session Recordings (admin/manager)
  - Audit Logs (admin/manager)
  - Settings (all roles)
- **User info** — avatar circle (first letter), username, role badge
- **Header** — page title, notification bell (hardcoded `unreadCount = 3`), logout button
- **`<Outlet />`** — renders the matched page from React Router

### 3.5 API Client (`api.ts`, lines 1-345)

Typed generic wrapper:

```typescript
async function request<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });
  if (res.status === 401) { clearToken(); window.location.href = '/login'; throw new Error('Unauthorized'); }
  if (!res.ok) { /* parse error body */ }
  return res.json();
}
```

Exports 38 typed functions organized by domain: `login`, `getMe`, `getCompanies`, `createServer`, `getRequests`, `approveRequest`, `getSessionRecording`, `exportAuditLogsCsv`, `getBillingAccount`, `getNotifications`, etc.

**Design differences from embedded SPA API:**
- No `?token=` query param (uses `Authorization` header only)
- Throws typed errors instead of returning `{ok, data, status}`
- Token stored under key `token` (SPA uses `pam_token`)
- Uses `PUT` for approve/reject (SPA uses `POST`)

### 3.6 Terminal (TypeScript + xterm.js, `SessionWindowPage.tsx`, lines 1-334)

The React terminal is significantly more sophisticated than the embedded SPA version:

```typescript
const term = new Terminal({
  cursorStyle: 'bar',
  cursorBlink: true,
  fontSize: 14,
  fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'Consolas', monospace",
  theme: {
    background: '#1a1b2e',
    foreground: '#e0e0e0',
    cursor: '#00ff66',
    // Dracula-inspired color palette (16 colors)
    black: '#2e2e3e', red: '#ff5555', green: '#50fa7b', yellow: '#f1fa8c',
    blue: '#6272a4', magenta: '#ff79c6', cyan: '#8be9fd', white: '#f8f8f2',
    brightBlack: '#5a5a7a', brightRed: '#ff6e6e', brightGreen: '#69ff94',
    brightYellow: '#ffffa5', brightBlue: '#7b8abf', brightMagenta: '#ff92d0',
    brightCyan: '#a4f0ff', brightWhite: '#ffffff',
  },
});

const fitAddon = new FitAddon();
term.loadAddon(fitAddon);

// ResizeObserver for responsive terminal
const ro = new ResizeObserver(() => {
  requestAnimationFrame(() => { try { fitAddon.fit(); } catch {} });
});
ro.observe(terminalContainerRef.current);
```

**WebSocket message handling** handles 9 message types (vs. 5 in SPA):
- `terminal_output` — uses `term.write()` (canvas rendering, supports ANSI escape codes)
- `session_created` — extracts hostname, IP, port, username, expiry
- `ssh_ready` — green "Connected" badge
- `session_error` — red error text with ANSI
- `session_ended` — yellow "reason" text, sets `terminated` state
- `session_timer` — updates remaining time from server push (no polling)
- `session_reconnect` — green "Reconnected" text, re-enables input

**Input handling** uses `term.onData()` which fires on **every keystroke** (unlike SPA which sends only on Enter):

```typescript
term.onData((data) => {
  sendMessage({ action: 'terminal_input', data });
});
```

This means the React terminal sends individual characters as they are typed, while the SPA terminal sends only completed lines on Enter. The backend processes both fine since it has an internal line buffer.

**Terminal resize** sends `cols` and `rows` on every resize via `term.onResize()` — the embedded SPA has no equivalent; the pty stays at default size.

**Cleanup** on unmount disconnects the ResizeObserver, closes WebSocket, and disposes the terminal instance.

### 3.7 Build Failure Details

The React frontend cannot be built or served for two reasons:

1. **`npm install` timeout** — the `node_modules/` directory needs 5000+ packages (from xterm, xterm-addon-fit, recharts, lucide-react, and their transitive dependencies). `npm install` runs for 25+ minutes before timing out with `ERR_CONNECTION_TIMED_OUT` on various registry requests. Even when packages are partially cached, the sheer number of files causes filesystem-level slowdowns.

2. **Vite unresponsive** — the Vite dev server starts but hangs on the first HMR request. The filesystem I/O for TypeScript compilation + Tailwind JIT + React refresh is too slow to serve pages within a reasonable time.

The partial `node_modules/` that exists contains only `clsx`, `csstype`, `xterm`, `xterm-addon-fit`, `postcss-value-parser`, `lucide-react`, and `@babel/plugin-transform-react-jsx-source` — missing critical dependencies like `react`, `react-dom`, `react-router-dom`, `recharts`, `tailwindcss`, and their 400+ transitive deps.

**As a result**, the project ships the embedded SPA (frontend_html.py) as the live frontend, and the React source exists purely as code reference.

---

## 4. Comparison: Embedded SPA vs. React Frontend

| Feature | Embedded SPA | React Frontend |
|---------|-------------|----------------|
| **Terminal rendering** | Plain `<div>` with `white-space: pre-wrap`, monospace font, green text on black | xterm.js canvas with Dracula theme, cursor blink, ANSI colors, resizing, 16-color palette |
| **Input mode** | Line mode — sends on Enter only, local echo in JS | Raw mode — sends every keystroke via `term.onData()`, terminal handles echo |
| **Terminal resize** | None — fixed size output div | `FitAddon` + `ResizeObserver` + `term.onResize()` sends `{cols, rows}` to server |
| **Session timer** | Polls `/requests?status=approved` every 1s | Server-pushed `session_timer` WebSocket messages |
| **Routing** | Manual `navigateTo()` switch | React Router v6 `<Routes>` |
| **State** | Global mutable variables | React Context + `useState` |
| **API client** | Generic `api()` returning `{ok, data, status}` | Typed `request<T>()` with generics and error throwing |
| **Styling** | Inline CSS + CSS variables | Tailwind utility classes |
| **Icons** | Inline SVG strings | lucide-react components |
| **Notifications** | Polling every interval, modal display | React Router page |
| **Auth storage** | `pam_token` / `pam_user` keys | `token` / `user` keys |
| **API method conventions** | `POST` for approve/reject/terminate | `PUT` for approve/reject/terminate |
| **Build required** | None — raw triple-quoted Python string | Vite + TypeScript compilation |
| **Bundle size** | ~1342 lines (minified ~60KB gzipped) | Would be ~200KB+ with xterm.js, recharts, React runtime |
| **Lines of code (page-specific)** | 930 lines of JS | 1680+ lines of TSX across 13 files |

---

## 5. UX/UI Decisions

### 5.1 Dark Theme Default
All users see dark mode first (navy background, `#0f172a`). Light mode exists and is toggled via the custom button, persisted in localStorage. The choice aligns with SSH terminal aesthetics — most system administrators prefer dark terminals.

### 5.2 Gradient Stat Cards
Dashboard cards use 135-degree linear gradients with matching icon backgrounds (semi-transparent white). Each card type has its own color identity:
- Blue gradient → admins, servers, requests (informational)
- Green gradient → approved, users, active sessions (positive)
- Red/amber gradient → critical/high alerts (warning)

### 5.3 Server Cards vs. Table
Servers use expandable cards instead of a table row. This was chosen because:
- Server data is sparse (IP, status, name) — a table would waste horizontal space
- Cards with status badges look more modern
- The expandable body reveals detail while keeping the list compact
- The card pattern signals "click for action" more intuitively than a table row

### 5.4 Toast Placement
Toasts appear bottom-right (not top-center or top-right). This avoids obscuring the topbar content and keeps them out of the way of modal dialogs. The 3-second auto-dismiss is short enough to not require manual closing but long enough to read.

### 5.5 Badge Color Semantics
Consistent across all entities:
- Green → approved, active, success
- Red → rejected, critical, inactive, error
- Yellow → pending, warning, elevated
- Blue → informational, event types
- Purple → superuser accounts

### 5.6 Terminal UX
- Local echo with `\n` suffix so SSH output appears on the line below the command (mirrors real terminal behavior)
- Prompt format: `username@server-id:~$ ` (username stripped to first segment before `@`, server ID truncated to 8 chars)
- Timer shows `M:SS` format with automatic termination at 0
- Fullscreen overlay (z-index 3000) with header bar for info and controls

### 5.7 Notification Bell
- Unread count badge in red circle
- Polls `/notifications/unread-count` on page load (no WebSocket push)
- Modal overlay for list rather than a dedicated page

---

## 6. Code Examples

### 6.1 Theme Toggle (CSS + JS)

```css
/* CSS custom properties for theming */
:root {
  --bg: #0f172a; --card-bg: #1e293b; --border: #334155;
  --text: #e2e8f0; --muted: #94a3b8; --primary: #3b82f6;
}
[data-theme="light"] {
  --bg: #f1f5f9; --card-bg: #ffffff; --border: #e2e8f0;
  --text: #1e293b; --muted: #64748b; --primary: #2563eb;
}

/* Sliding toggle switch */
.toggle-track { position: relative; display: flex; align-items: center;
  padding: 0 7px; justify-content: space-between;
  background: var(--border); border-radius: 12px; height: 24px; }
.toggle-thumb { width: 16px; height: 16px; border-radius: 50%;
  background: var(--primary); position: absolute; left: 3px; top: 3px;
  transition: left 0.25s ease; }
#theme-toggle[data-state="light"] .toggle-thumb { left: 28px; }
```

```javascript
// Theme toggle handler
document.getElementById('theme-toggle').addEventListener('click', function() {
  const isLight = document.documentElement.getAttribute('data-theme') === 'light';
  document.documentElement.setAttribute('data-theme', isLight ? 'dark' : 'light');
  localStorage.setItem('pam_theme', isLight ? 'dark' : 'light');
  setThemeToggle(isLight ? 'dark' : 'light');
});

// Restore on page load
const savedTheme = localStorage.getItem('pam_theme');
if (savedTheme === 'light') {
  document.documentElement.setAttribute('data-theme', 'light');
  setThemeToggle('light');
}
```

### 6.2 API Wrapper with JWT Auth

```javascript
async function api(url, opts = {}) {
  const headers = {'Content-Type': 'application/json', ...opts.headers};
  if (token) {
    headers['Authorization'] = 'Bearer ' + token;
    // Append token as query param for WebSocket compatibility
    url += (url.includes('?') ? '&' : '?') + 'token=' + encodeURIComponent(token);
  }
  const res = await fetch('/api' + url, {...opts, headers});
  if (res.status === 401) {
    localStorage.removeItem('pam_token');
    localStorage.removeItem('pam_user');
    location.reload();
  }
  const text = await res.text();
  try { return {ok: res.ok, data: text ? JSON.parse(text) : null, status: res.status}; }
  catch { return {ok: res.ok, data: text, status: res.status}; }
}
```

### 6.3 WebSocket Terminal Client

```javascript
function openTerminal(serverId, requestId) {
  // Show terminal overlay
  document.getElementById('terminal-wrap').classList.add('active');
  document.getElementById('term-info').textContent =
    user.username.split('@')[0] + '@server:' + serverId.slice(0,8);

  // Reset terminal UI
  const termDiv = document.getElementById('terminal');
  if (termWs) termWs.close();
  termDiv.innerHTML = `
    <div id="term-output" style="flex:1;overflow-y:auto;padding:16px;
      white-space:pre-wrap;font-family:Menlo,Monaco,'Courier New',monospace;
      font-size:14px;line-height:1.5;color:#4ade80;background:#0f172a"></div>
    <div id="term-inputline" style="display:flex;align-items:center;gap:8px;
      padding:8px 16px;border-top:1px solid #1e293b;background:#0a0f1a">
      <span id="term-prompt" style="color:#4ade80;font-weight:700">$</span>
      <input id="term-input" style="flex:1;background:#0f172a;border:1px solid #334155;
        border-radius:4px;color:#e2e8f0;font-family:Menlo,Monaco,'Courier New',monospace;
        font-size:14px;padding:8px 10px" autofocus>
    </div>`;

  // Open WebSocket
  const wsUrl = 'ws://' + location.host + '/ws/terminal?token=' + token;
  termWs = new WebSocket(wsUrl);

  termWs.onopen = () => {
    termOut.textContent += '\nConnected. Joining session...';
    termWs.send(JSON.stringify({action: 'join_session', requestId, serverId}));
  };

  termWs.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === 'terminal_output') {
      termOut.textContent += msg.data;
    } else if (msg.type === 'session_created') {
      terminalSession = msg.data.sessionId;
      showTimer(requestId);
    } else if (msg.type === 'ssh_ready') {
      document.getElementById('term-prompt').textContent =
        user.username.split('@')[0] + '@' + serverId.slice(0,8) + ':~$';
    }
  };

  // Enter-only input with local echo
  document.getElementById('term-input').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') {
      const cmd = e.target.value;
      termOut.textContent += '\n$ ' + cmd + '\n';
      termWs.send(JSON.stringify({type: 'terminal_input', data: cmd + '\n'}));
      e.target.value = '';
    }
  });
}
```

### 6.4 Modal System

```javascript
function showModal(html) {
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = '<div class="modal">' + html + '</div>';
  overlay.addEventListener('click', e => {
    if (e.target === overlay) closeModal();
  });
  document.body.appendChild(overlay);
}

function closeModal() {
  document.querySelector('.modal-overlay')?.remove();
  if (replayTimeout) { clearTimeout(replayTimeout); replayTimeout = null; }
}
```

### 6.5 Session Recording Replay

```javascript
let replayIndex = 0;
let replayTimeout = null;

function replayRecording(rec) {
  const wrap = document.getElementById('replay-wrap');
  if (!wrap) return;
  if (replayIndex >= rec.length) { toast('Replay complete'); return; }

  const entry = rec[replayIndex];
  if (entry.event === 'output') {
    wrap.textContent += entry.data;
    wrap.scrollTop = wrap.scrollHeight;
  }

  replayIndex++;
  const delay = replayIndex < rec.length
    ? Math.min((rec[replayIndex].timestamp - entry.timestamp), 100)
    : 100;
  replayTimeout = setTimeout(() => replayRecording(rec), Math.max(delay, 15));
}
```

### 6.6 React xterm.js Terminal Setup

```tsx
import { Terminal } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import 'xterm/css/xterm.css';

// In component:
const term = new Terminal({
  cursorStyle: 'bar',
  cursorBlink: true,
  fontSize: 14,
  theme: {
    background: '#1a1b2e',
    foreground: '#e0e0e0',
    cursor: '#00ff66',
    green: '#50fa7b',
    red: '#ff5555',
  },
});

const fitAddon = new FitAddon();
term.loadAddon(fitAddon);
term.open(terminalContainerRef.current);

// Responsive resizing
const ro = new ResizeObserver(() => {
  requestAnimationFrame(() => { try { fitAddon.fit(); } catch {} });
});
ro.observe(terminalContainerRef.current);

// Keystroke input
term.onData((data) => {
  sendMessage({ action: 'terminal_input', data });
});

// Terminal resize
term.onResize(({ cols, rows }) => {
  sendMessage({ action: 'terminal_resize', cols, rows });
});
```

---

## 7. Security Considerations

### 7.1 JWT in URL Query String
The embedded SPA appends `?token=` to every API request URL. This exposes the JWT in:
- Server access logs
- Browser history (if using GET for non-fetch requests)
- Referer headers (if navigating to external links)
- WebSocket handshake (required because browser `WebSocket` API doesn't support custom headers)

**Mitigation:** The JWT has a 15-minute access token window. The refresh token is stored in the request body, not the URL.

### 7.2 LocalStorage XSS Risk
Both frontends store auth tokens in `localStorage` (`pam_token` / `token`). Any XSS vulnerability would leak tokens directly. The React frontend is slightly more vulnerable because it also stores the parsed user object for instant UI rendering.

**Comparison:** The SPA re-reads `localStorage` on every page load; the React frontend initializes state from `localStorage` and keeps it in memory thereafter.

### 7.3 Client-Side Role Checks
Both frontends perform role-based access control on the client side. In the SPA, `navigateTo()` checks `user.role` before calling `render*()`. In the React frontend, `navigateTo()` checks the same via filter and conditional rendering. However, all sensitive data is also gated server-side — the backend returns 403 for unauthorized access regardless of what the client renders.

### 7.4 Port/OS Hiding
The server detail modal hides Port, OS, and Connection Types from regular `user` role users using both:
- **Frontend:** JSX wraps sensitive fields in `isAdminOrSuper ? ... : ...` conditional
- **Backend:** The `/servers` endpoint for user role excludes `port`, `os`, and `allowed_connection_types` from the response

This is a correct defense-in-depth pattern — the frontend could be bypassed, but the backend enforces the same restriction.

### 7.5 No CSRF Protection
Neither frontend implements CSRF tokens. The SPA uses only `fetch()` with `Authorization: Bearer` headers, which are not automatically attached by browsers on cross-origin form submissions. The CORS middleware is set to `allow_origins=["*"]` with credentials, but browsers ignore `Access-Control-Allow-Credentials` when `*` is used, so cross-origin reads are effectively blocked.

---

## 8. Summary

| Metric | Value |
|--------|-------|
| Total frontend source | ~3020 lines across both codebases |
| Embedded SPA (served) | 1342 lines — HTML + CSS + JS in one file |
| React frontend (source) | ~1680 lines across 15 TSX/TS files |
| CSS variables | 36 dark mode + 36 light mode = 72 total |
| Theme colors | 2 modes, 6 shared colors, 6 badge color pairs |
| JS pages/views | 11 (Dashboard, Companies, Users, Servers, MyRequests, Approvals, Recordings, Audit, Settings, Notifications, Terminal) |
| WebSocket message types | 6 handled (terminal_output, session_created, ssh_ready, session_ended, session_error, error) |
| React routes | 13 (including `/session/:serverId/:requestId`) |
| API functions (React) | 38 typed endpoints |
| React page components | 12 page components |
| Major libraries | React 18, xterm.js 5.3, Vite 5, Tailwind 3, React Router 6, recharts, lucide-react |

The embedded SPA is a pragmatic fallback: it sacrifices component isolation, type safety, and terminal polish in exchange for zero build dependencies and instant delivery. The React source documents the intended architecture if a build pipeline becomes available.
