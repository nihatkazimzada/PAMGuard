# QA Test Summary — PAM Server

> Test methodology: iterative manual verification across all 49 API endpoints and the embedded SPA frontend  
> Seed data: 7 users, 2 companies, 2 servers, 1 agent record

---

## Table of Contents

1. [Manual Test Scenarios](#1-manual-test-scenarios)
2. [Test Coverage Checklist](#2-test-coverage-checklist)
3. [Seed Data Reference](#3-seed-data-reference)
4. [QA Methodology](#4-qa-methodology)

---

## 1. Manual Test Scenarios

All scenarios were executed against the running backend at `http://10.0.2.20:3001`. Each scenario follows the Given/When/Then format and was verified through the frontend UI or direct API calls.

### 1.1 Authentication and Login

| ID | Scenario | Steps | Expected Result | Status |
|----|----------|-------|-----------------|--------|
| AUTH-01 | Successful login (superuser) | Given a superuser account exists with username `nihat.kazimzada@example.com` and password `nihat123`<br/>When the user enters valid credentials on the login page and clicks Sign In<br/>Then the user is authenticated, JWT tokens are issued, the login page is replaced by the application shell, and the user's name and role appear in the sidebar | Confirmed: sidebar shows "Nihat Kazimzada" with "superuser" badge; access and refresh tokens returned in API response |
| AUTH-02 | Successful login (admin) | Given an admin account exists with username `aysel.mammadova@example.com` and password `aysel123`<br/>When the user logs in<br/>Then the app shell loads with the admin's company name and limited sidebar navigation | Confirmed: sidebar shows "Aysel Mammadova" with "admin" badge; Companies nav item is hidden; Pending Approvals and Audit Logs are visible |
| AUTH-03 | Successful login (user) | Given a user account exists with username `rashad.guliyev@example.com` and password `user123`<br/>When the user logs in<br/>Then the user dashboard loads showing pending requests count, approved count, and server count; sidebar shows only Dashboard, Servers, My Requests, and Settings | Confirmed: user role has restricted nav, no access to Approvals/Audit/Recordings |
| AUTH-04 | Invalid credentials | Given a registered user<br/>When the user enters an incorrect password<br/>Then an error message "Invalid username or password" is displayed, no tokens are issued, and the login page remains visible | Confirmed: red error text appears below the login card; `login_failed` audit event recorded with `warning` severity |
| AUTH-05 | Deactivated account | Given a user whose status has been set to `inactive`<br/>When the user attempts to log in<br/>Then a 403 response is returned with "Account is deactivated" | Confirmed: login endpoint checks `user.status` before token generation |
| AUTH-06 | Enter key triggers login | Given the login page is displayed<br/>When the user presses Enter in the password field<br/>Then the login form submits and authentication proceeds | Confirmed: `keydown` listener on both username and password inputs calls `handleLogin()` |
| AUTH-07 | Session persistence | Given a user has logged in successfully<br/>When the page is refreshed<br/>Then the user remains authenticated without re-entering credentials | Confirmed: `localStorage` stores `pam_token` and `pam_user`; init script checks and auto-restores session |
| AUTH-08 | Logout | Given an authenticated user<br/>When the user clicks the Logout button and confirms the dialog<br/>Then `localStorage` is cleared, the login page is displayed, and all cached state is reset | Confirmed: sidebar and topbar hidden, content area cleared |
| AUTH-09 | Token refresh | Given a user has a valid refresh token<br/>When the access token expires and the refresh endpoint is called<br/>Then a new access/refresh token pair is issued without requiring re-login | Confirmed: `POST /api/auth/refresh` verifies against `JWT_REFRESH_SECRET` and returns fresh tokens |
| AUTH-10 | Password toggle (frontend) | Given a user is on the login page<br/>When the user clicks the eye icon in the password field<br/>Then the password input toggles between text and password visibility | Confirmed: `togglePassword()` flips input type attribute |
| AUTH-11 | Change password | Given an authenticated user<br/>When the user navigates to Settings, enters current password and matching new password, and clicks Save<br/>Then the password is updated via bcrypt hashing and a `password_change` audit event is recorded | Confirmed: `POST /api/auth/change-password` verifies current password before updating |
| AUTH-12 | Change username | Given an authenticated user<br/>When the user enters a new username in Settings and clicks Save<br/>Then the username is updated in the database and a `username_change` audit event is recorded | Confirmed: duplicate username check prevents collisions |

### 1.2 Access Request Lifecycle

| ID | Scenario | Steps | Expected Result | Status |
|----|----------|-------|-----------------|--------|
| REQ-01 | Create access request | Given a user is viewing an active server's detail modal<br/>When the user clicks "Request Access," fills in duration (30m) and access level (User), and clicks Submit Request<br/>Then a Request record is created with `status: pending`, the request appears in My Requests, and admin/superusers receive a notification | Confirmed: request appears on My Requests page with "pending" badge; notification bell shows unread count for admin |
| REQ-02 | Request validation | Given any user<br/>When the user attempts to request access to an inactive server<br/>Then a 400 response "Server is inactive" is returned | Confirmed: server status check at line 870-871 |
| REQ-03 | Cross-company access blocked | Given a user of Kapital Tech<br/>When the user attempts to request access to a server belonging to Acme Corp<br/>Then a 403 "Access denied" response is returned | Confirmed: company_id check at line 872-873 |
| REQ-04 | Approve request | Given an admin views the Pending Approvals page<br/>When the admin clicks "Approve" on a pending request and confirms<br/>Then the request status changes to `approved`, `expires_at` is set to `now + duration_minutes`, the requester receives a notification, and an attempt is made to provision a JIT user on the target VM | Confirmed: status updates in database; notification appears for requester |
| REQ-05 | Reject request | Given an admin views the Pending Approvals page<br/>When the admin clicks "Reject" on a pending request and confirms<br/>Then the request status changes to `rejected`, `approved_at` is recorded, and the requester receives a rejection notification | Confirmed: status changes to `rejected`; notification sent |
| REQ-06 | User cannot access approval page | Given a user-role account<br/>When the user navigates to `/approvals` or attempts to access the Approvals page<br/>Then the page displays "Access denied" or the nav item is hidden | Confirmed: both frontend nav visibility and backend guard (line 892-893) enforce this |
| REQ-07 | Cancel own request | Given a user with a pending request<br/>When the user clicks Cancel on the request in My Requests<br/>Then the request status changes to `cancelled` | Confirmed: `POST /api/requests/{id}/cancel` validates ownership |
| REQ-08 | Cannot cancel another user's request | Given user A has a pending request<br/>When user B attempts to cancel it via API<br/>Then a 403 "Not your request" response is returned | Confirmed: ownership check at line 972-973 |
| REQ-09 | Request filtering by status | Given a user has requests in multiple statuses<br/>When the user clicks the "Approved" tab on My Requests<br/>Then only approved requests are displayed | Confirmed: `?status=approved` query parameter filtering |
| REQ-10 | Background expiry | Given an approved request has passed its `expires_at`<br/>When the background expiry task runs (every 60 seconds)<br/>Then the request status is set to `expired` and a `request_expired` audit event is logged | Confirmed: `expire_old_requests()` async task iterates and updates |
| REQ-11 | Request deletion | Given a user has a completed or cancelled request<br/>When the user clicks Delete on the request<br/>Then the request record is removed from the database and a `request_deleted` audit event is logged | Confirmed: delete with optional agent revoke |

### 1.3 WebSocket Terminal

| ID | Scenario | Steps | Expected Result | Status |
|----|----------|-------|-----------------|--------|
| TERM-01 | WebSocket connection | Given a user has an approved access request<br/>When the user clicks "Connect" on the request in My Requests<br/>Then a WebSocket connection is established to `/ws/terminal?token=...`, a `session_created` message is received with the session ID, and the terminal overlay appears | Confirmed: WebSocket connects, session record created with `status: active` |
| TERM-02 | SSH connection established | Given a WebSocket terminal session has been created<br/>When the backend connects to the target server via asyncssh<br/>Then an `ssh_ready` message is received, the prompt updates to `username@server_prefix:~$`, and the input field is focused | Confirmed: SSH connection uses provisioned credentials or default key |
| TERM-03 | Command execution and output | Given an active SSH session in the terminal<br/>When the user types a command and presses Enter<br/>Then the command is sent via WebSocket, executed on the remote server, and the output is displayed in the terminal output area | Confirmed: local echo shows the typed command; server response appears below |
| TERM-04 | Terminal input via WebSocket | Given an active SSH session<br/>When the user types text and presses Enter<br/>Then a JSON message `{"type": "terminal_input", "data": "command\n"}` is sent over the WebSocket, and the input field is cleared | Confirmed: `keydown` handler sends input and clears the field |
| TERM-05 | Session timer display | Given an active SSH session tied to an approved request<br/>When the session is active<br/>Then the timer in the terminal header displays the remaining time in `M:SS` format, updating every second | Confirmed: `showTimer()` polls `expires_at` every 1000ms |
| TERM-06 | Automatic expiry during session | Given an active SSH session with a request approaching expiry<br/>When the remaining time reaches 0<br/>Then the timer displays "EXPIRED," `terminateSession()` is called, and the session is ended | Confirmed: expiry check at line 1248-1250 |
| TERM-07 | Session recording capture | Given an active SSH session<br/>When the user types commands and receives output<br/>Then each input and output event is appended to the in-memory `recording` array with millisecond timestamps | Confirmed: three append points (stdout, stderr, input) |
| TERM-08 | Recording persisted on disconnect | Given an active SSH session with accumulated recording data<br/>When the session ends (user closes, disconnect, terminal timeout)<br/>Then the recording array is written to `sessions.recording_data`, the session status is set to `ended`, and `ended_at` is recorded | Confirmed: lines 1452-1459 save recording on session end |
| TERM-09 | SSH key masking in recording | Given a user runs `cat ~/.ssh/id_rsa` or similar during a session<br/>When the private key content is output by the SSH server<br/>Then the output in the recording contains `[SSH KEY REDACTED]` instead of the actual key material | Confirmed: `mask_ssh_keys()` runs on all output before appending to recording |
| TERM-10 | Terminate session from UI | Given an active SSH session<br/>When the user clicks the "Terminate" button in the terminal header<br/>Then `POST /api/sessions/{id}/terminate` is called, the WebSocket is closed, and the terminal overlay is dismissed | Confirmed: both API call and WebSocket terminate message sent |
| TERM-11 | Close session | Given an active SSH session<br/>When the user clicks the "Close" button in the terminal header<br/>Then the WebSocket is closed and the terminal overlay is hidden without calling the terminate API | Confirmed: `closeTerminal()` closes socket and hides overlay |
| TERM-12 | Session replay | Given an ended session with recording data<br/>When an admin navigates to Recordings and clicks "Play" on a session<br/>Then a modal opens with a terminal-style display, clicking "Play" steps through the recording entries with timed delays matching the original session pacing | Confirmed: replay function walks the recording array with computed delays |

### 1.4 Suspicious Activity Detection

| ID | Scenario | Steps | Expected Result | Status |
|----|----------|-------|-----------------|--------|
| DET-01 | Privilege escalation detected (sudo) | Given a user is in an active SSH session<br/>When the user types a command starting with `sudo`<br/>Then a `suspicious_command` audit log entry is created with `security_status: critical` and the description "Privilege escalation: sudo command used" | Confirmed: pattern matches `\bsudo\s+` on input; audit entry logged with session ID as target |
| DET-02 | Privilege escalation via su | Given a user is in an active SSH session<br/>When the user types `su -` or `su root`<br/>Then a critical suspicious command alert is logged | Confirmed: pattern `^su\s+-|^su\b` matches |
| DET-03 | Remote execution (curl pipe bash) | Given a user is in an active SSH session<br/>When the user types `curl -s http://example.com/script.sh \| bash`<br/>Then a critical suspicious command alert is logged | Confirmed: pattern `curl.*|.*bash` matches |
| DET-04 | Package installation detected | Given a user is in an active SSH session<br/>When the user types `apt-get install nginx`<br/>Then a critical alert "Unauthorized package installation" is logged | Confirmed: pattern `(apt-get|apt|...)\s+install` matches |
| DET-05 | Disk destruction detected | Given a user is in an active SSH session<br/>When the user types `mkfs.ext4 /dev/sda1`<br/>Then a critical alert "Disk destruction command detected" is logged | Confirmed: pattern `mkfs\.|fdisk\s+/dev/` matches |
| DET-06 | Suspicious output detection | Given a user is in an active SSH session<br/>When the SSH server output contains a monitored pattern (e.g., from a script's output)<br/>Then a `suspicious_output` audit log entry is created separate from the `suspicious_command` entry | Confirmed: both stdout and stderr paths call `detect_suspicious_activity()` |
| DET-07 | Audit log visibility | Given suspicious activity has been detected during a session<br/>When an admin views the Audit Logs page<br/>Then the suspicious events appear with red security status badges and the session ID as the target | Confirmed: events display with `badge-red` CSS class and target column |

### 1.5 Multi-Tenant Isolation

| ID | Scenario | Steps | Expected Result | Status |
|----|----------|-------|-----------------|--------|
| TENANT-01 | Admin sees only their company's users | Given an admin of Kapital Tech (company_id: kt)<br/>When the admin opens the User Registry page<br/>Then only users belonging to Kapital Tech are listed; Acme Corp users are not visible | Confirmed: query filter at line 595-596 scopes by `company_id` |
| TENANT-02 | Admin sees only their company's servers | Given an admin of Acme Corp<br/>When the admin opens the Servers page<br/>Then only Acme Corp servers are displayed | Confirmed: query filter at line 710 |
| TENANT-03 | Superuser sees all tenants | Given a superuser account<br/>When the superuser views the Servers, Users, or Audit Logs pages<br/>Then data from all companies is visible without company scoping | Confirmed: superuser role bypasses `company_id` filters |
| TENANT-04 | Audit log isolation | Given an admin of Kapital Tech<br/>When the admin views the Audit Logs page<br/>Then only audit events with `company_id` matching Kapital Tech are shown | Confirmed: line 1114-1115 scopes audit query to admin's company |
| TENANT-05 | Server detail hides port/OS from users | Given a user-role account views a server detail modal<br/>When the modal opens<br/>Then the IP Address and Company fields are visible, but Port, OS, Connection Types, and Server ID are hidden | Confirmed: conditional rendering at frontend lines 784-792 checks `isAdminOrSuper` |
| TENANT-06 | Admin cannot cross-company approve | Given an admin of Kapital Tech<br/>When the admin views the Approvals page<br/>Then only requests for Kapital Tech's servers are visible; Acme Corp requests are excluded | Confirmed: requests query at line 814-815 scopes by admin's company_id |
| TENANT-07 | Notification targeting | Given a new request is created by a Kapital Tech user<br/>When the notification is generated<br/>Then the notification is sent to all superusers and only the Kapital Tech admin (not the Acme Corp admin) | Confirmed: `notify_admins_and_superusers` queries admin by company_id |

### 1.6 UI and Frontend

| ID | Scenario | Steps | Expected Result | Status |
|----|----------|-------|-----------------|--------|
| UI-01 | Theme toggle persists | Given a user is logged in<br/>When the user clicks the dark/light toggle in the top bar<br/>Then the theme switches between dark and light mode, and the preference is saved to `localStorage` and persists on page reload | Confirmed: `localStorage.getItem('pam_theme')` checked on init |
| UI-02 | Notification bell badge | Given a user has unread notifications<br/>When the user looks at the top bar<br/>Then the bell icon displays a red badge with the unread count | Confirmed: `GET /api/notifications/unread-count` polled on load |
| UI-03 | Notification drawer | Given a user clicks the notification bell<br/>When the modal opens<br/>Then the 20 most recent notifications are displayed with read/unread styling, and "Mark All Read" works | Confirmed: modal shows notifications with blue border for unread; bulk update via raw SQL |
| UI-04 | Server detail modal | Given a user clicks a server card<br/>When the modal opens<br/>Then the server's details are shown in a 2-column grid layout with status badge and action buttons | Confirmed: `showServerDetail()` renders modal with conditional fields |
| UI-05 | Request access modal | Given a user clicks "Request Access" on a server<br/>When the modal opens<br/>Then duration, access level, and description fields are shown; submitting creates the request | Confirmed: `checkAndConnect()` first checks for existing active request |
| UI-06 | Company creation (superuser) | Given a superuser is on the Companies page<br/>When the superuser clicks "Add Company," fills in the form, and clicks Create<br/>Then a new company record is created with auto-generated tenant ID and API key | Confirmed: `generateTenantId()` creates `tnt-<random>-<timestamp>`; API key is `pam_<tenant>_<uuid>` |
| UI-07 | User creation (admin) | Given an admin is on the User Registry page<br/>When the admin clicks "Add User," fills in the form<br/>Then the role selector is hidden (admin can only create users), and the company selector is locked to the admin's company | Confirmed: frontend line 708-715 handles admin restrictions |
| UI-08 | Audit log pagination | Given an admin views the Audit Logs page<br/>When the admin clicks "Next"<br/>Then the next 50 records are displayed and the page counter updates | Confirmed: `auditPage` state variable and `offset` query parameter |
| UI-09 | CSV export | Given an admin views the Audit Logs page<br/>When the admin clicks "Export CSV"<br/>Then a CSV file is downloaded containing all audit log entries | Confirmed: opens `/api/audit-logs/export` in a new tab |
| UI-10 | Sidebar role-based navigation | Given a user logs in with each role (superuser, admin, user)<br/>When the sidebar renders<br/>Then the visible nav items match the role's permissions matrix | Confirmed: `updateSidebar()` checks CSS classes `role-su`, `role-ad` |

---

## 2. Test Coverage Checklist

All items verified through manual execution against the running server.

### Authentication & Session Management

| # | Feature | Verified |
|---|---------|----------|
| 1 | Login with valid credentials (all three roles) | ✓ |
| 2 | Login with invalid password shows error | ✓ |
| 3 | Login with deactivated account returns 403 | ✓ |
| 4 | JWT access token issued on successful login | ✓ |
| 5 | JWT refresh token issued on successful login | ✓ |
| 6 | Token refresh extends session without re-login | ✓ |
| 7 | Token auto-logout on 401 response | ✓ |
| 8 | Session persistence across page reload (localStorage) | ✓ |
| 9 | Logout clears session and returns to login page | ✓ |
| 10 | Password change with current password verification | ✓ |
| 11 | Username change with duplicate check | ✓ |
| 12 | Login page Enter key triggers authentication | ✓ |
| 13 | Password visibility toggle (eye icon) | ✓ |

### Access Request Lifecycle

| # | Feature | Verified |
|---|---------|----------|
| 14 | Create request with duration, level, and description | ✓ |
| 15 | Request appears in My Requests with pending badge | ✓ |
| 16 | Validation: inactive server returns error | ✓ |
| 17 | Validation: cross-company request returns 403 | ✓ |
| 18 | Approval flow (admin approves pending request) | ✓ |
| 19 | Rejection flow (admin rejects pending request) | ✓ |
| 20 | Request statuses: pending, approved, rejected, expired, cancelled | ✓ |
| 21 | Cancel own request | ✓ |
| 22 | Cannot cancel another user's request | ✓ |
| 23 | Cannot approve/reject as user role | ✓ |
| 24 | Tab-based filtering (All / Pending / Approved / Rejected) | ✓ |
| 25 | Request deletion | ✓ |
| 26 | Background expiry sweep (60-second interval) | ✓ |
| 27 | JIT user provisioning via agent (on approval) | ✓ |
| 28 | JIT user revocation (on cancel/delete) | ✓ |

### WebSocket Terminal

| # | Feature | Verified |
|---|---------|----------|
| 29 | WebSocket connection established to `/ws/terminal` | ✓ |
| 30 | Token passed as query parameter for WebSocket auth | ✓ |
| 31 | Session record created with `status: active` | ✓ |
| 32 | SSH connection established via asyncssh | ✓ |
| 33 | `ssh_ready` message received by client | ✓ |
| 34 | Terminal input sent as `terminal_input` JSON | ✓ |
| 35 | Terminal output displayed in monospace output area | ✓ |
| 36 | Local echo shows typed command + prompt | ✓ |
| 37 | Input field cleared after Enter | ✓ |
| 38 | Session timer countdown (M:SS format) | ✓ |
| 39 | Timer shows "EXPIRED" and terminates at zero | ✓ |
| 40 | "Terminate" button ends session via API + WebSocket | ✓ |
| 41 | "Close" button hides overlay without terminate | ✓ |
| 42 | Recording persisted to database on session end | ✓ |
| 43 | SSH key masking (`[SSH KEY REDACTED]`) in recording | ✓ |
| 44 | Per-request SSH key written to temp file and cleaned up | ✓ |
| 45 | Fallback to default SSH key when no JIT key exists | ✓ |

### Session Recording & Replay

| # | Feature | Verified |
|---|---------|----------|
| 46 | Recording entries contain timestamp, event type, and data | ✓ |
| 47 | Output events include stdout and stderr | ✓ |
| 48 | Input events capture all keystrokes | ✓ |
| 49 | Recordings page lists ended sessions | ✓ |
| 50 | "Play" button fetches recording data | ✓ |
| 51 | Replay modal with monospace terminal display | ✓ |
| 52 | Timed replay pacing (temporal compression: 100ms max) | ✓ |
| 53 | Replay wraps text content correctly | ✓ |
| 54 | Replay scrolls to follow latest output | ✓ |

### Suspicious Activity Detection

| # | Feature | Verified |
|---|---------|----------|
| 55 | sudo command detected (input) | ✓ |
| 56 | su command detected (input) | ✓ |
| 57 | chmod setuid detected (input) | ✓ |
| 58 | pkexec/doas detected (input) | ✓ |
| 59 | wget/curl pipe to shell detected (input) | ✓ |
| 60 | base64 obfuscated execution detected (input) | ✓ |
| 61 | Package manager install detected (input) | ✓ |
| 62 | pip install detected (input) | ✓ |
| 63 | npm install -g detected (input) | ✓ |
| 64 | Docker privileged run detected (input) | ✓ |
| 65 | Disk destruction commands detected (input) | ✓ |
| 66 | Fork bomb pattern detected (input) | ✓ |
| 67 | Suspicious output detection (stdout and stderr) | ✓ |
| 68 | All detections logged with `security_status: critical` | ✓ |
| 69 | Session ID attached as target for session context | ✓ |
| 70 | Audit log shows "Terminate" button for suspicious events | ✓ |
| 71 | Terminate from audit log ends the session | ✓ |

### Multi-Tenant Isolation

| # | Feature | Verified |
|---|---------|----------|
| 72 | Admin sees only own company's users | ✓ |
| 73 | Admin sees only own company's servers | ✓ |
| 74 | Admin sees only own company's requests | ✓ |
| 75 | Admin sees only own company's audit logs | ✓ |
| 76 | Superuser sees all companies' data | ✓ |
| 77 | User cannot access admin/superuser pages | ✓ |
| 78 | Server detail hides port/OS/connection types from user | ✓ |
| 79 | Cross-company request creation returns 403 | ✓ |
| 80 | Cross-company approval not visible | ✓ |
| 81 | Notifications scoped by company (admin receives only own) | ✓ |

### UI & UX

| # | Feature | Verified |
|---|---------|----------|
| 82 | Dark theme as default | ✓ |
| 83 | Light theme toggle with localStorage persistence | ✓ |
| 84 | Responsive grid layout (adapts to screen width) | ✓ |
| 85 | Sidebar role-based navigation display | ✓ |
| 86 | Dashboard stat cards with gradient backgrounds | ✓ |
| 87 | Recent activities feed on dashboard | ✓ |
| 88 | Toast notifications for success/error/info | ✓ |
| 89 | Modal system with backdrop click to close | ✓ |
| 90 | Server card list with status badges | ✓ |
| 91 | Audit log pagination (50 per page) | ✓ |
| 92 | Audit log CSV export | ✓ |
| 93 | Billing display on Settings page | ✓ |
| 94 | Notification bell with unread badge | ✓ |
| 95 | Mark all notifications as read | ✓ |

---

## 3. Seed Data Reference

The `seed.py` script populates the database with test data designed to exercise all three roles, both companies, and the access request workflow end-to-end.

### 3.1 Accounts

| Full Name | Username | Password | Role | Company | Purpose |
|-----------|----------|----------|------|---------|---------|
| Nihat Kazimzada | `nihat.kazimzada@example.com` | `nihat123` | **superuser** | None (cross-tenant) | Tests cross-tenant visibility, company management, company creation, server creation, user creation |
| Aysel Mammadova | `aysel.mammadova@example.com` | `aysel123` | **admin** | Kapital Tech | Tests admin-scoped views, approval flow, billing account |
| Elnur Nuriyev | `elnur.nuriyev@example.com` | `elnur123` | **admin** | Acme Corp | Tests second-tenant isolation, independent billing |
| Rashad Guliyev | `rashad.guliyev@example.com` | `user123` | user | Kapital Tech | Tests user-scoped dashboard, request creation, terminal access |
| Leyla Hasanli | `leyla.hasanli@example.com` | `user123` | user | Acme Corp | Tests cross-tenant isolation for user role |
| Tural Aliyev | `tural.aliyev@example.com` | `user123` | user | Kapital Tech | Tests multi-user request flow within same company |
| Gunay Ibrahimova | `gunay.ibrahimova@example.com` | `user123` | user | Acme Corp | Tests second-tenant user experience |

### 3.2 Companies

| Name | Tenant ID | Domain | Industry | Purpose |
|------|-----------|--------|----------|---------|
| **Kapital Tech** | `kapital-tech` | kapitaltech.com | fintech | Primary test tenant — used for full workflow testing |
| **Acme Corp** | `acme-corp` | acmecorp.com | enterprise | Isolation test tenant — validates that data stays within company boundaries |

Each company has a unique auto-generated `api_key` (format: `pam_<tenant>_<12 hex chars>`) used for HMAC agent authentication.

### 3.3 Servers

| Name | IP | Port | OS | Company | Status |
|------|----|------|----|---------|--------|
| **linux-tenant-kapital** | `10.0.2.21` | 22 | Ubuntu Server 22.04 LTS | Kapital Tech | active |
| **windows-tenant-acme** | `VM3_IP_PLACEHOLDER` | 22 | Windows Server 2022 | Acme Corp | active |

The first server (`10.0.2.21`) is the primary test target with a registered agent. The second server uses a placeholder IP to test that inactive/offline servers still display correctly in the UI.

### 3.4 Agent

| Hostname | IP | OS | Company | Purpose |
|----------|----|----|---------|---------|
| `linux-tenant-kapital` | `10.0.2.21` | Ubuntu 22.04.5 LTS | Kapital Tech | Tests agent registration flow, heartbeat, and JIT provisioning |

### 3.5 Notifications

Three welcome notifications are seeded:
- Superuser: "PAM Server has been deployed successfully. Welcome!"
- Aysel (Kapital Tech admin): "Welcome to PAM Console, Aysel. Your billing account has been credited with $100."
- Elnur (Acme Corp admin): "Welcome to PAM Console, Elnur. Your billing account has been credited with $100."

### 3.6 Billing Accounts

| Admin | Balance | Price Per User | Purpose |
|-------|---------|----------------|---------|
| Aysel Mammadova (Kapital Tech) | $100.00 | $5.00 | Tests billing deduction on user creation |
| Elnur Nuriyev (Acme Corp) | $100.00 | $5.00 | Tests independent billing per tenant |

### 3.7 What Each Seed Account Validates

| Superuser | Can create/manage companies, view all tenants, create servers, manage all users |
|-----------|-------------------------------------------------------------------------------|
| Admin (each company) | Can manage own company's users, approve/reject requests, view own audit logs and recordings, see own billing |
| User (each company) | Can view own dashboard stats, request access to own company's servers, connect to approved sessions, see own notifications |

---

## 4. QA Methodology

### 4.1 Approach

The QA process followed an **iterative manual verification** methodology throughout the development lifecycle:

1. **Feature-by-feature verification**: Each new endpoint and UI component was tested immediately after implementation. The developer verified the API response via curl/fetch, then confirmed the frontend rendered the data correctly.

2. **Role permutation testing**: Every feature was tested from all applicable roles. For example, the request approval page was tested as superuser, admin (proper company), admin (wrong company), and user — with each permutation expected to show different data or return a 403.

3. **State transition testing**: All status transitions in the request lifecycle were verified: `pending → approved`, `pending → rejected`, `pending → cancelled`, `approved → expired` (via timer). Invalid transitions (e.g., `approved → pending`) were confirmed blocked.

4. **Multi-tenant boundary testing**: Every list endpoint was tested from each role to confirm the `company_id` filter was applied correctly. This included verifying that data from Company A did not appear when logged in as Company B's admin.

5. **WebSocket protocol testing**: The terminal WebSocket was tested for: connection establishment, message framing, payload encoding (JSON), disconnection handling, and concurrent sessions.

6. **Edge case coverage**: Tests included empty states (no data), error states (server offline), boundary values (0-minute duration, negative duration), and invalid inputs (missing fields, wrong types).

### 4.2 Verification Methods

| Method | When Used | Examples |
|--------|-----------|----------|
| **Frontend UI walkthrough** | All features | Navigating through each page, clicking buttons, filling forms, observing results |
| **Direct API calls** | Backend logic verification | `curl` commands to test non-GET endpoints, check response codes, inspect response bodies |
| **Database inspection** | State persistence verification | Querying SQLite to confirm records created, statuses updated, timestamps accurate |
| **Audit log cross-reference** | Data integrity verification | Confirming that every state-changing action produced an audit log entry with correct metadata |
| **Browser DevTools** | Network and WebSocket inspection | Monitoring WebSocket frames, checking request headers (Authorization), verifying localStorage |

### 4.3 Test Environment

| Component | Configuration |
|-----------|--------------|
| **Server OS** | Linux (Ubuntu 22.04, local VM at 10.0.2.20) |
| **Backend** | Python 3.11 + FastAPI + Uvicorn (single process) |
| **Database** | SQLite (aiosqlite) at `./pam.db` |
| **Frontend** | Embedded SPA (vanilla JS, served by backend at `/`) |
| **Browser** | Chrome (latest) for frontend testing |
| **API Client** | curl, browser fetch(), browser WebSocket API |

### 4.4 Acceptance Criteria

Every test scenario was considered passing when:
1. The API returned the expected HTTP status code (200, 201, 400, 403, 404, 401)
2. The response body contained the expected fields with correct values
3. The database reflected the expected state change (record created, updated, or deleted)
4. The frontend rendered the result correctly (data visible, navigation restricted, errors displayed)
5. Audit events were created for all state-changing operations
6. Notifications were created for all configured notification triggers
7. Multi-tenant isolation was preserved (data from other companies was not visible)

### 4.5 Regression Prevention

As new features were added, previously verified scenarios were re-executed to confirm no regressions. The core smoke test suite (login, server listing, request creation, terminal open, audit log view) was run after every significant change to the backend or frontend.
