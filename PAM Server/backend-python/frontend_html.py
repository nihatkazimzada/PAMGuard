"""Embedded frontend HTML for the PAM Server - served at /"""
FRONTEND_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PAM Console</title>
<style>
:root {
  --bg: #0f172a; --card-bg: #1e293b; --card-alt: #1a2235;
  --border: #334155; --text: #e2e8f0; --muted: #94a3b8;
  --text-muted: #64748b; --hover-bg: #1e293b; --input-bg: #1e293b;
  --primary: #3b82f6; --primary-dark: #2563eb; --primary-light: #60a5fa;
  --accent-bg: #1e3a5f; --sidebar-bg: #0f172a; --danger: #dc2626;
  --success: #16a34a; --warning: #d97706;
  --badge-green-bg: #14532d; --badge-green-text: #4ade80;
  --badge-red-bg: #450a0a; --badge-red-text: #f87171;
  --badge-yellow-bg: #451a03; --badge-yellow-text: #fbbf24;
  --badge-blue-bg: #1e3a5f; --badge-blue-text: #60a5fa;
  --badge-purple-bg: #3b0764; --badge-purple-text: #c084fc;
}
[data-theme="light"] {
  --bg: #f1f5f9; --card-bg: #ffffff; --card-alt: #f8fafc;
  --border: #e2e8f0; --text: #1e293b; --muted: #64748b;
  --text-muted: #94a3b8; --hover-bg: #f1f5f9; --input-bg: #ffffff;
  --sidebar-bg: #ffffff; --accent-bg: #dbeafe;
  --badge-green-bg: #dcfce7; --badge-green-text: #16a34a;
  --badge-red-bg: #fee2e2; --badge-red-text: #dc2626;
  --badge-yellow-bg: #fef3c7; --badge-yellow-text: #d97706;
  --badge-blue-bg: #dbeafe; --badge-blue-text: #2563eb;
  --badge-purple-bg: #f3e8ff; --badge-purple-text: #7c3aed;
}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--text);overflow:hidden;height:100vh}
a{color:var(--primary-light);text-decoration:none}
input,select,textarea{background:var(--input-bg);border:1px solid var(--border);color:var(--text);padding:10px 14px;border-radius:8px;font-size:14px;width:100%;outline:none;transition:border .2s}
input:focus,select:focus,textarea:focus{border-color:var(--primary)}
button{cursor:pointer;border:none;border-radius:8px;font-size:14px;font-weight:500;padding:10px 20px;transition:all .2s;background:var(--card-bg);color:var(--text)}
.btn-primary{background:linear-gradient(135deg,var(--primary-dark),var(--primary));color:#fff;box-shadow:0 4px 15px rgba(37,99,235,.3)}.btn-primary:hover{background:linear-gradient(135deg,var(--primary),var(--primary-light));box-shadow:0 6px 20px rgba(37,99,235,.4);transform:translateY(-1px)}
.btn-danger{background:linear-gradient(135deg,#dc2626,#ef4444);color:#fff;box-shadow:0 4px 15px rgba(220,38,38,.3)}.btn-danger:hover{background:linear-gradient(135deg,#ef4444,#f87171);box-shadow:0 6px 20px rgba(220,38,38,.4);transform:translateY(-1px)}
.btn-success{background:linear-gradient(135deg,#16a34a,#22c55e);color:#fff;box-shadow:0 4px 15px rgba(22,163,74,.3)}.btn-success:hover{background:linear-gradient(135deg,#22c55e,#4ade80);box-shadow:0 6px 20px rgba(22,163,74,.4);transform:translateY(-1px)}
.btn-secondary{background:var(--border);color:var(--text)}.btn-secondary:hover{background:var(--text-muted);transform:translateY(-1px)}
.btn-warning{background:linear-gradient(135deg,#d97706,#f59e0b);color:#fff;box-shadow:0 4px 15px rgba(217,119,6,.3)}.btn-warning:hover{background:linear-gradient(135deg,#f59e0b,#fbbf24);box-shadow:0 6px 20px rgba(217,119,6,.4);transform:translateY(-1px)}
.btn-sm{padding:6px 12px;font-size:12px}
.btn:disabled{opacity:.5;cursor:not-allowed;transform:none!important}
.card{background:linear-gradient(135deg,var(--card-bg),var(--card-alt));border:1px solid var(--border);border-radius:12px;padding:20px;margin-bottom:16px;box-shadow:0 4px 20px rgba(0,0,0,.2);transition:all .2s}
.card:hover{box-shadow:0 8px 30px rgba(0,0,0,.3);border-color:var(--primary)}
h1{font-size:24px;font-weight:700;margin-bottom:24px}
h2{font-size:18px;font-weight:600;margin-bottom:16px}
h3{font-size:15px;font-weight:600;margin-bottom:8px}
table{width:100%;border-collapse:collapse;font-size:14px}
th{text-align:left;padding:12px 16px;background:var(--bg);color:var(--muted);font-weight:500;font-size:12px;text-transform:uppercase;letter-spacing:.5px}
td{padding:10px 16px;border-top:1px solid var(--card-bg)}
tr:hover{background:var(--hover-bg)}
.badge{display:inline-block;padding:2px 10px;border-radius:20px;font-size:11px;font-weight:600;text-transform:uppercase}
.badge-green{background:var(--badge-green-bg);color:var(--badge-green-text)}
.badge-red{background:var(--badge-red-bg);color:var(--badge-red-text)}
.badge-yellow{background:var(--badge-yellow-bg);color:var(--badge-yellow-text)}
.badge-blue{background:var(--badge-blue-bg);color:var(--badge-blue-text)}
.badge-purple{background:var(--badge-purple-bg);color:var(--badge-purple-text)}
.badge-gray{background:var(--card-bg);color:var(--muted)}
.grid{display:grid;gap:16px}
.grid-2{grid-template-columns:1fr 1fr}
.grid-3{grid-template-columns:1fr 1fr 1fr}
.grid-4{grid-template-columns:1fr 1fr 1fr 1fr}
@media(max-width:768px){.grid-2,.grid-3,.grid-4{grid-template-columns:1fr}}
.flex{display:flex;gap:12px;align-items:center}
.flex-wrap{flex-wrap:wrap}
.flex-1{flex:1}
.gap-2{gap:8px}
.gap-4{gap:16px}
.mt-4{margin-top:16px}
.mb-4{margin-bottom:16px}
.ml-auto{margin-left:auto}
.text-center{text-align:center}
.text-sm{font-size:13px;color:var(--muted)}
.text-xs{font-size:11px;color:var(--text-muted)}
.text-green{color:var(--badge-green-text)}
.text-red{color:var(--badge-red-text)}
.text-yellow{color:var(--badge-yellow-text)}
.text-blue{color:var(--badge-blue-text)}
.text-muted{color:var(--muted)}
.font-mono{font-family:'SF Mono','Fira Code',monospace}
.w-full{width:100%}
.hidden{display:none!important}
/* Layout */
#app{display:flex;height:100vh}
#sidebar{width:240px;background:var(--sidebar-bg);border-right:1px solid var(--border);display:flex;flex-direction:column;flex-shrink:0;overflow:hidden}
#sidebar .logo{padding:20px;font-size:18px;font-weight:700;display:flex;align-items:center;gap:10px;border-bottom:1px solid var(--border)}
#sidebar .logo svg{color:var(--primary)}
#sidebar nav{padding:12px;flex:1;overflow-y:auto}
#sidebar nav a{display:flex;align-items:center;gap:10px;padding:10px 14px;border-radius:8px;color:var(--muted);font-size:14px;margin-bottom:2px;transition:all .15s}
#sidebar nav a:hover,#sidebar nav a.active{background:var(--hover-bg);color:var(--text)}
#sidebar nav a.active{color:var(--primary-light)}
#sidebar .user-info{padding:16px;border-top:1px solid var(--border);font-size:13px}
#sidebar .user-info .name{color:var(--text);font-weight:500}
#sidebar .user-info .role{color:var(--primary);font-size:11px;font-weight:600;text-transform:uppercase}
#main{flex:1;display:flex;flex-direction:column;overflow:hidden}
#topbar{height:60px;display:flex;align-items:center;padding:0 24px;border-bottom:1px solid var(--border);flex-shrink:0}
#topbar h1{font-size:18px;font-weight:600;margin:0}
#topbar .right{display:flex;align-items:center;gap:16px;margin-left:auto}
#notif-bell{position:relative;cursor:pointer;padding:8px;border-radius:8px;transition:background .2s;color:var(--muted)}
#notif-bell:hover{background:var(--hover-bg);color:var(--text)}
#notif-badge{position:absolute;top:2px;right:2px;background:#dc2626;color:#fff;font-size:10px;padding:2px 5px;border-radius:10px;min-width:16px;text-align:center}
#theme-toggle{width:48px;height:24px;cursor:pointer;flex-shrink:0;position:relative;border:none;background:none;padding:0;display:block}
.toggle-track{width:100%;height:100%;border-radius:12px;background:var(--border);border:1px solid var(--border);position:relative;overflow:hidden;display:flex;align-items:center;padding:0 7px;justify-content:space-between;transition:background .3s}
.toggle-thumb{width:16px;height:16px;border-radius:50%;background:var(--primary);position:absolute;top:3px;left:3px;transition:left .25s ease;z-index:2;box-shadow:0 1px 4px rgba(0,0,0,.4)}
#theme-toggle[data-state="light"] .toggle-thumb{left:28px}
.toggle-label{font-size:9px;font-weight:700;color:var(--muted);z-index:1;user-select:none;line-height:1;letter-spacing:.3px}
#theme-toggle:hover .toggle-thumb{box-shadow:0 0 10px rgba(59,130,246,.4)}
#content{padding:24px;overflow-y:auto;flex:1}
/* Login */
#login-page{display:flex;align-items:center;justify-content:center;height:100vh;background:linear-gradient(135deg,var(--bg) 0%,var(--card-bg) 50%,var(--bg) 100%);animation:fadeIn .6s ease}
@keyframes fadeIn{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}
#login-card{background:var(--card-bg);border:1px solid var(--border);border-radius:16px;padding:40px;width:100%;max-width:420px;box-shadow:0 25px 50px rgba(0,0,0,.4)}
#login-card .logo{text-align:center;margin-bottom:32px}
#login-card .logo svg{width:48px;height:48px;color:var(--primary);margin-bottom:12px}
#login-card .logo h1{font-size:24px;margin:0;margin-bottom:4px}
#login-card .logo p{font-size:13px;color:var(--text-muted)}
#login-card .field{margin-bottom:16px}
#login-card .field label{display:block;font-size:13px;color:var(--muted);margin-bottom:6px;font-weight:500}
#login-card .field .pw-row{display:flex;gap:8px;align-items:stretch}
#login-card .field .pw-row input{flex:1}
#login-card .field .toggle-pw{background:var(--card-bg);border:1px solid var(--border);color:var(--text-muted);cursor:pointer;width:44px;display:flex;align-items:center;justify-content:center;border-radius:8px;flex-shrink:0;transition:all .2s}
#login-card .field .toggle-pw:hover{border-color:var(--primary);color:var(--primary-light);background:var(--accent-bg)}
#login-card .error{color:#f87171;font-size:13px;margin-bottom:12px;min-height:20px}
#login-card button{width:100%;padding:12px;font-size:15px}
#login-card .loader{display:inline-block;width:18px;height:18px;border:2px solid rgba(255,255,255,.3);border-top-color:#fff;border-radius:50%;animation:spin .6s linear infinite;vertical-align:middle;margin-right:8px}
@keyframes spin{to{transform:rotate(360deg)}}
/* Modal */
.modal-overlay{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.7);display:flex;align-items:center;justify-content:center;z-index:1000;animation:fadeIn .2s ease}
.modal{background:var(--card-bg);border:1px solid var(--border);border-radius:16px;padding:28px;width:90%;max-width:520px;max-height:85vh;overflow-y:auto}
.modal h2{font-size:18px;margin-bottom:20px}
.modal .field{margin-bottom:14px}
.modal .field label{display:block;font-size:12px;color:var(--muted);margin-bottom:4px;font-weight:500}
.modal .actions{display:flex;gap:12px;justify-content:flex-end;margin-top:20px}
/* Tabs */
.tabs{display:flex;gap:4px;margin-bottom:20px;background:var(--bg);border-radius:10px;padding:4px}
.tabs button{padding:8px 16px;border-radius:8px;font-size:13px;background:transparent;color:var(--muted)}
.tabs button.active{background:var(--card-bg);color:var(--text)}
/* Stat Card */
.stat-card{background:var(--card-bg);border:1px solid var(--border);border-radius:12px;padding:20px;text-align:center}
.stat-card .icon{width:40px;height:40px;border-radius:10px;display:flex;align-items:center;justify-content:center;margin:0 auto 12px;font-size:20px}
.stat-card .value{font-size:28px;font-weight:700;color:var(--primary-light)}
.stat-card .label{font-size:13px;color:var(--muted);margin-top:4px}
/* Form */
.form-row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media(max-width:600px){.form-row{grid-template-columns:1fr}}
/* Scrollbar */
::-webkit-scrollbar{width:6px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:var(--text-muted)}
/* Toast */
.toast{position:fixed;bottom:24px;right:24px;padding:12px 20px;border-radius:10px;color:#fff;font-size:14px;z-index:2000;animation:slideUp .3s ease;max-width:400px}
.toast-success{background:#166534;box-shadow:0 4px 20px rgba(22,101,52,.4)}
.toast-error{background:#7f1d1d;box-shadow:0 4px 20px rgba(127,29,29,.4)}
.toast-info{background:var(--accent-bg);box-shadow:0 4px 20px rgba(30,58,95,.4)}
@keyframes slideUp{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}
/* Server Cards */
.server-card{background:var(--card-bg);border:1px solid var(--border);border-radius:12px;overflow:hidden;transition:all .25s ease;cursor:pointer}
.server-card:hover{box-shadow:0 8px 30px rgba(0,0,0,.4);border-color:var(--primary);transform:translateY(-2px)}
.server-card .header{padding:16px 20px;display:flex;align-items:center;gap:12px;position:relative;color:var(--text)}
.server-card .header .arrow{color:var(--text-muted);transition:transform .25s ease;font-size:12px;margin-left:auto}
.server-card.expanded .header .arrow{transform:rotate(180deg)}
.server-card .body{padding:0 20px 16px;display:none}
.server-card.expanded .body{display:block;animation:fadeIn .2s ease}
.server-card .body .info-row{display:flex;padding:8px 0;border-bottom:1px solid var(--border);font-size:14px}
.server-card .body .info-row:last-child{border-bottom:none}
.server-card .body .info-row .label{color:var(--muted);width:120px;flex-shrink:0}
.server-card .body .info-row .value{color:#e2e8f0}
.server-card .body .actions{display:flex;gap:8px;margin-top:12px;padding-top:12px;border-top:1px solid #334155}
/* Server detail modal */
.server-detail-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.server-detail-grid .item{padding:12px;background:#0f172a;border-radius:8px}
.server-detail-grid .item .lbl{font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px}
.server-detail-grid .item .val{font-size:14px;color:#e2e8f0}
/* Terminal */
#terminal-wrap{position:fixed;top:0;left:0;right:0;bottom:0;background:#0f172a;z-index:3000;display:none}
#terminal-wrap.active{display:flex;flex-direction:column}
#terminal-header{height:48px;display:flex;align-items:center;padding:0 16px;background:#0f172a;border-bottom:1px solid #1e293b;gap:12px}
#terminal-header .badge-type{background:#1e3a5f;color:#60a5fa;padding:3px 10px;border-radius:4px;font-size:11px;font-weight:600}
#terminal-header .info{font-size:13px;color:#94a3b8}
#terminal-header .timer{font-size:14px;font-weight:600;color:#4ade80;margin-left:auto}
#terminal-header .actions{display:flex;gap:8px}
#terminal{flex:1;display:flex;flex-direction:column;overflow:hidden;background:#0f172a}
</style>
</head>
<body>
<div id="app">
  <div id="sidebar" class="hidden">
    <div class="logo">
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2l7 4v5c0 5-3.5 9.7-7 11-3.5-1.3-7-6-7-11V6l7-4z"/></svg>
      PAM Console
    </div>
    <nav id="nav">
      <a href="#" data-page="dashboard"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="9"/><rect x="14" y="3" width="7" height="5"/><rect x="14" y="12" width="7" height="9"/><rect x="3" y="16" width="7" height="5"/></svg>Dashboard</a>
      <a href="#" data-page="companies" class="role-su"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 21h18"/><path d="M9 21V9l6-4v16"/><path d="M15 21V9l-6-4v16"/></svg>Company Tenants</a>
      <a href="#" data-page="users" class="role-su role-ad"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>User Registry</a>
      <a href="#" data-page="servers"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="8" rx="2" ry="2"/><rect x="2" y="14" width="20" height="8" rx="2" ry="2"/><line x1="6" y1="6" x2="6" y2="6"/><line x1="6" y1="18" x2="6" y2="18"/></svg>Servers</a>
      <a href="#" data-page="my-requests"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>My Requests</a>
      <a href="#" data-page="approvals" class="role-su role-ad"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>Pending Approvals</a>
      <a href="#" data-page="recordings" class="role-su role-ad"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>Recordings</a>
      <a href="#" data-page="audit" class="role-su role-ad"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>Audit Logs</a>
      <a href="#" data-page="settings"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>Settings</a>
    </nav>
    <div class="user-info" id="sidebar-user">
      <div class="name" id="sidebar-name"></div>
      <div class="role" id="sidebar-role"></div>
    </div>
  </div>
  <div id="main">
    <div id="topbar" class="hidden">
      <h1 id="page-title">Dashboard</h1>
      <div class="right">
        <div id="theme-toggle" onclick="toggleTheme()" title="Toggle theme" data-state="dark">
          <div class="toggle-track">
            <div class="toggle-thumb"></div>
            <span class="toggle-label">D</span>
            <span class="toggle-label">L</span>
          </div>
        </div>
        <div id="notif-bell" onclick="showNotifications()">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>
          <span id="notif-badge" class="hidden">0</span>
        </div>
        <button class="btn-sm btn-danger" onclick="handleLogout()" title="Logout" style="padding:6px 10px;display:flex;align-items:center;gap:6px">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
          Logout
        </button>
      </div>
    </div>
    <div id="content">
      <div id="login-page">
        <div id="login-card">
          <div class="logo">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2l7 4v5c0 5-3.5 9.7-7 11-3.5-1.3-7-6-7-11V6l7-4z"/></svg>
            <h1>PAM Console</h1>
            <p>Privileged Access Management</p>
          </div>
          <div class="error" id="login-error"></div>
          <div class="field">
            <label>Username / Email</label>
            <input type="text" id="login-user" placeholder="Enter your username" autocomplete="username">
          </div>
          <div class="field">
            <label>Password</label>
            <div class="pw-row">
              <input type="password" id="login-pass" placeholder="Enter your password" autocomplete="current-password">
              <button class="toggle-pw" onclick="togglePassword()" type="button" tabindex="-1" title="Show/Hide password">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
              </button>
            </div>
          </div>
          <button class="btn-primary" onclick="handleLogin()" id="login-btn">
            <span id="login-btn-text">Sign In</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</div>
<div id="terminal-wrap">
  <div id="terminal-header">
    <span class="badge-type">SSH ACCESS</span>
    <span class="info" id="term-info"></span>
    <span class="timer" id="term-timer"></span>
    <div class="actions">
      <button class="btn-danger btn-sm" onclick="terminateSession()">Terminate</button>
      <button class="btn-secondary btn-sm" onclick="closeTerminal()">Close</button>
    </div>
  </div>
  <div id="terminal"></div>
</div>

<script>
// ─── State ──────────────────────────────────────────────────────────────────
const API = '/api';
let user = null;
let token = null;
let companies = [];
let servers = [];
let users = [];
let requests = [];
let notifications = [];
let currentPage = 'dashboard';
let ws = null;
let terminalSession = null;
let terminalTimer = null;
let termWs = null;
let terminalData = [];

// ─── Auth ────────────────────────────────────────────────────────────────────

function togglePassword() {
  const p = document.getElementById('login-pass');
  p.type = p.type === 'password' ? 'text' : 'password';
}

async function handleLogin() {
  const username = document.getElementById('login-user').value.trim();
  const password = document.getElementById('login-pass').value;
  const error = document.getElementById('login-error');
  const btn = document.getElementById('login-btn');
  const btnText = document.getElementById('login-btn-text');

  if (!username || !password) { error.textContent = 'Please enter username and password'; return; }
  error.textContent = '';
  btn.disabled = true;
  btnText.innerHTML = '<span class="loader"></span>Signing in...';

  try {
    const res = await fetch(API + '/auth/login', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({username, password})
    });
    const data = await res.json();
    if (!res.ok) { throw new Error(data.detail || 'Invalid username or password'); }
    token = data.access_token;
    user = data.user;
    localStorage.setItem('pam_token', token);
    localStorage.setItem('pam_user', JSON.stringify(user));
    document.getElementById('login-page').classList.add('hidden');
    document.getElementById('sidebar').classList.remove('hidden');
    document.getElementById('topbar').classList.remove('hidden');
    showApp();
  } catch(e) {
    error.textContent = 'Invalid username or password';
  } finally {
    btn.disabled = false;
    btnText.textContent = 'Sign In';
  }
}

function setThemeToggle(state) {
  const el = document.getElementById('theme-toggle');
  if (el) el.dataset.state = state;
}

function toggleTheme() {
  const html = document.documentElement;
  const isLight = html.getAttribute('data-theme') === 'light';
  if (isLight) {
    html.removeAttribute('data-theme');
    localStorage.setItem('pam_theme', 'dark');
    setThemeToggle('dark');
  } else {
    html.setAttribute('data-theme', 'light');
    localStorage.setItem('pam_theme', 'light');
    setThemeToggle('light');
  }
}

function handleLogout() {
  if (!confirm('Are you sure you want to logout?')) return;
  localStorage.removeItem('pam_token');
  localStorage.removeItem('pam_user');
  token = null;
  user = null;
  document.getElementById('login-page').classList.remove('hidden');
  document.getElementById('sidebar').classList.add('hidden');
  document.getElementById('topbar').classList.add('hidden');
  document.getElementById('content').innerHTML = '';
  document.getElementById('login-error').textContent = '';
}

function showApp() {
  updateSidebar();
  loadNotifications();
  navigateTo(user.role === 'user' ? 'servers' : 'dashboard');
}

function updateSidebar() {
  document.getElementById('sidebar-name').textContent = user.fullName;
  document.getElementById('sidebar-role').textContent = user.role;
  document.querySelectorAll('#nav a').forEach(a => {
    const roles = a.className.replace('role-', '').split(' ');
    if (a.dataset.page === 'dashboard' || a.dataset.page === 'servers' || a.dataset.page === 'my-requests' || a.dataset.page === 'settings') {
      a.style.display = '';
    } else if (user.role === 'superuser') {
      a.style.display = '';
    } else if (user.role === 'admin' && (a.classList.contains('role-ad') || a.classList.contains('role-su'))) {
      a.style.display = '';
    } else {
      a.style.display = 'none';
    }
  });
  document.querySelectorAll('#nav a').forEach(a => {
    a.classList.toggle('active', a.dataset.page === currentPage);
  });
  document.getElementById('page-title').textContent = 
    document.querySelector(`#nav a[data-page="${currentPage}"]`)?.textContent.trim() || 'Dashboard';
}

// ─── Navigation ──────────────────────────────────────────────────────────────

document.querySelectorAll('#nav a').forEach(a => {
  a.addEventListener('click', e => {
    e.preventDefault();
    navigateTo(a.dataset.page);
  });
});

function navigateTo(page) {
  if (!user) return;
  currentPage = page;
  updateSidebar();
  const content = document.getElementById('content');
  switch(page) {
    case 'dashboard': renderDashboard(); break;
    case 'companies': user.role === 'superuser' ? renderCompanies() : (content.innerHTML = '<p>Access denied</p>'); break;
    case 'users': renderUsers(); break;
    case 'servers': renderServers(); break;
    case 'my-requests': renderMyRequests(); break;
    case 'approvals': user.role !== 'user' ? renderApprovals() : (content.innerHTML = '<p>Access denied</p>'); break;
    case 'recordings': user.role !== 'user' ? renderRecordings() : (content.innerHTML = '<p>Access denied</p>'); break;
    case 'audit': user.role !== 'user' ? renderAuditLogs() : (content.innerHTML = '<p>Access denied</p>'); break;
    case 'settings': renderSettings(); break;
    default: renderDashboard();
  }
}

// ─── API Helper ──────────────────────────────────────────────────────────────

async function api(url, opts = {}) {
  const headers = {'Content-Type': 'application/json', ...opts.headers};
  if (token) {
    headers['Authorization'] = 'Bearer ' + token;
    const sep = url.includes('?') ? '&' : '?';
    url += sep + 'token=' + encodeURIComponent(token);
  }
  const res = await fetch(API + url, {...opts, headers});
  if (res.status === 401) { localStorage.removeItem('pam_token'); localStorage.removeItem('pam_user'); location.reload(); }
  const text = await res.text();
  try { return {ok: res.ok, data: text ? JSON.parse(text) : null, status: res.status}; }
  catch { return {ok: res.ok, data: text, status: res.status}; }
}

function toast(msg, type = 'info') {
  const t = document.createElement('div');
  t.className = 'toast toast-' + type;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3000);
}

// ─── Dashboard ───────────────────────────────────────────────────────────────

async function renderDashboard() {
  const content = document.getElementById('content');
  content.innerHTML = '<div class="text-center text-muted" style="padding:40px">Loading dashboard...</div>';
  try {
    if (user.role === 'user') {
      const {ok, data} = await api('/dashboard/user-stats');
      if (!ok) { content.innerHTML = '<p>Failed to load dashboard</p>'; return; }
      const s = data;
      content.innerHTML = `
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:28px;flex-wrap:wrap;gap:12px">
          <div>
            <h1 style="font-size:26px;margin:0;background:linear-gradient(135deg,#60a5fa,#818cf8);-webkit-background-clip:text;-webkit-text-fill-color:transparent">Dashboard</h1>
            <p style="color:var(--muted);font-size:13px;margin-top:4px">Welcome back, ${user.fullName}</p>
          </div>
          <div style="display:flex;gap:8px">
            <span class="badge badge-blue" style="font-size:12px;padding:4px 14px">${new Date().toLocaleDateString('en-US',{weekday:'long',month:'short',day:'numeric'})}</span>
          </div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin-bottom:24px">
          <div style="background:linear-gradient(135deg,#1e3a5f,#1e40af);border-radius:14px;padding:18px 20px;display:flex;align-items:center;gap:14px;box-shadow:0 4px 15px rgba(30,58,95,.3)">
            <div style="background:rgba(255,255,255,.12);width:44px;height:44px;border-radius:12px;display:flex;align-items:center;justify-content:center;flex-shrink:0">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color:#fbbf24"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
            </div>
            <div><div style="font-size:28px;font-weight:700;color:#fff">${s.pendingCount}</div><div style="font-size:12px;color:#fbbf24;font-weight:500">Pending Requests</div></div>
          </div>
          <div style="background:linear-gradient(135deg,#14532d,#15803d);border-radius:14px;padding:18px 20px;display:flex;align-items:center;gap:14px;box-shadow:0 4px 15px rgba(22,163,74,.2)">
            <div style="background:rgba(255,255,255,.12);width:44px;height:44px;border-radius:12px;display:flex;align-items:center;justify-content:center;flex-shrink:0">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color:#86efac"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
            </div>
            <div><div style="font-size:28px;font-weight:700;color:#fff">${s.approvedCount}</div><div style="font-size:12px;color:#86efac;font-weight:500">Approved</div></div>
          </div>
          <div style="background:linear-gradient(135deg,#1e3a5f,#1e40af);border-radius:14px;padding:18px 20px;display:flex;align-items:center;gap:14px;box-shadow:0 4px 15px rgba(30,58,95,.3)">
            <div style="background:rgba(255,255,255,.12);width:44px;height:44px;border-radius:12px;display:flex;align-items:center;justify-content:center;flex-shrink:0">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color:#93c5fd"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
            </div>
            <div><div style="font-size:28px;font-weight:700;color:#fff">${s.serverCount}</div><div style="font-size:12px;color:#93c5fd;font-weight:500">Servers Available</div></div>
          </div>
        </div>
        <div class="card">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color:var(--primary-light)"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
            <h2 style="font-size:16px;margin:0">My Recent Requests</h2>
          </div>
          <div>${(s.recentRequests||[]).map(r => {
            const badge = r.status === 'approved' ? 'green' : r.status === 'pending' ? 'yellow' : 'red';
            return '<div style="display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid var(--border)">' +
              '<span class="badge badge-' + badge + '" style="flex-shrink:0;min-width:60px;text-align:center">' + r.status + '</span>' +
              '<span style="flex:1;font-size:13px;color:var(--text)"><strong>' + r.server_name + '</strong> &middot; ' + r.access_level + ' &middot; ' + r.duration_minutes + 'm</span>' +
              '<span style="font-size:11px;color:var(--text-muted);white-space:nowrap">' + timeAgo(r.requested_at) + '</span>' +
            '</div>';
          }).join('') || '<div style="text-align:center;color:var(--muted);padding:20px">No requests yet — go to My Requests to create one</div>'}
          </div>
        </div>
        <div class="card">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color:var(--primary-light)"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
            <h2 style="font-size:16px;margin:0">My Recent Activity</h2>
          </div>
          <div>${(s.recentActivities||[]).slice(0,6).map(a => {
            const dot = a.security_status === 'critical' ? '#ef4444' : a.security_status === 'warning' ? '#f59e0b' : '#3b82f6';
            return '<div style="display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid var(--border)">' +
              '<div style="width:8px;height:8px;border-radius:50%;background:' + dot + ';flex-shrink:0"></div>' +
              '<span class="badge badge-' + (a.security_status === 'critical' ? 'red' : a.security_status === 'warning' ? 'yellow' : 'blue') + '" style="flex-shrink:0">' + a.event_type + '</span>' +
              '<span style="flex:1;font-size:13px;color:var(--text)">' + (a.action_detail || '') + '</span>' +
            '</div>';
          }).join('') || '<div style="text-align:center;color:var(--muted);padding:20px">No recent activity</div>'}
          </div>
        </div>`;
    } else {
      const {ok, data} = await api('/dashboard/stats');
      if (!ok) { content.innerHTML = '<p>Failed to load dashboard</p>'; return; }
      const s = data;
      content.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:28px;flex-wrap:wrap;gap:12px">
        <div>
          <h1 style="font-size:26px;margin:0;background:linear-gradient(135deg,#60a5fa,#818cf8);-webkit-background-clip:text;-webkit-text-fill-color:transparent">Dashboard</h1>
          <p style="color:var(--muted);font-size:13px;margin-top:4px">Welcome back, ${user.fullName}</p>
        </div>
        <div style="display:flex;gap:8px">
          <span class="badge badge-blue" style="font-size:12px;padding:4px 14px">${new Date().toLocaleDateString('en-US',{weekday:'long',month:'short',day:'numeric'})}</span>
        </div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin-bottom:20px">
        <div style="background:linear-gradient(135deg,#1e3a5f,#1e40af);border-radius:14px;padding:18px 20px;display:flex;align-items:center;gap:14px;box-shadow:0 4px 15px rgba(30,58,95,.3)">
          <div style="background:rgba(255,255,255,.12);width:44px;height:44px;border-radius:12px;display:flex;align-items:center;justify-content:center;flex-shrink:0">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color:#93c5fd"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
          </div>
          <div><div style="font-size:28px;font-weight:700;color:#fff">${s.adminCount}</div><div style="font-size:12px;color:#93c5fd;font-weight:500">Admins</div></div>
        </div>
        <div style="background:linear-gradient(135deg,#1e3a5f,#1e40af);border-radius:14px;padding:18px 20px;display:flex;align-items:center;gap:14px;box-shadow:0 4px 15px rgba(30,58,95,.3)">
          <div style="background:rgba(255,255,255,.12);width:44px;height:44px;border-radius:12px;display:flex;align-items:center;justify-content:center;flex-shrink:0">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color:#93c5fd"><path d="M3 21h18"/><path d="M9 21V9l6-4v16"/><path d="M15 21V9l-6-4v16"/></svg>
          </div>
          <div><div style="font-size:28px;font-weight:700;color:#fff">${s.companyCount}</div><div style="font-size:12px;color:#93c5fd;font-weight:500">Companies</div>
            <div style="font-size:10px;color:rgba(255,255,255,.5);margin-top:2px">${(s.companies||[]).map(c => c.name).join(', ')}</div>
          </div>
        </div>
        <div style="background:linear-gradient(135deg,#14532d,#15803d);border-radius:14px;padding:18px 20px;display:flex;align-items:center;gap:14px;box-shadow:0 4px 15px rgba(22,163,74,.2)">
          <div style="background:rgba(255,255,255,.12);width:44px;height:44px;border-radius:12px;display:flex;align-items:center;justify-content:center;flex-shrink:0">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color:#86efac"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/></svg>
          </div>
          <div><div style="font-size:28px;font-weight:700;color:#fff">${s.userCount}</div><div style="font-size:12px;color:#86efac;font-weight:500">Users</div></div>
        </div>
        <div style="background:linear-gradient(135deg,#1e3a5f,#312e81);border-radius:14px;padding:18px 20px;display:flex;align-items:center;gap:14px;box-shadow:0 4px 15px rgba(79,70,229,.2)">
          <div style="background:rgba(255,255,255,.12);width:44px;height:44px;border-radius:12px;display:flex;align-items:center;justify-content:center;flex-shrink:0">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color:#a78bfa"><rect x="2" y="2" width="20" height="8" rx="2" ry="2"/><rect x="2" y="14" width="20" height="8" rx="2" ry="2"/><line x1="6" y1="6" x2="6" y2="6"/><line x1="6" y1="18" x2="6" y2="18"/></svg>
          </div>
          <div><div style="font-size:28px;font-weight:700;color:#fff">${s.serverCount ?? 0}</div><div style="font-size:12px;color:#a78bfa;font-weight:500">Servers</div></div>
        </div>
        <div style="background:linear-gradient(135deg,#1e3a5f,#1e40af);border-radius:14px;padding:18px 20px;display:flex;align-items:center;gap:14px;box-shadow:0 4px 15px rgba(30,58,95,.3)">
          <div style="background:rgba(255,255,255,.12);width:44px;height:44px;border-radius:12px;display:flex;align-items:center;justify-content:center;flex-shrink:0">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color:#93c5fd"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
          </div>
          <div><div style="font-size:28px;font-weight:700;color:#fff">${s.requestCount}</div><div style="font-size:12px;color:#93c5fd;font-weight:500">Requests</div></div>
        </div>
        <div style="background:linear-gradient(135deg,#14532d,#15803d);border-radius:14px;padding:18px 20px;display:flex;align-items:center;gap:14px;box-shadow:0 4px 15px rgba(22,163,74,.2)">
          <div style="background:rgba(255,255,255,.12);width:44px;height:44px;border-radius:12px;display:flex;align-items:center;justify-content:center;flex-shrink:0">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color:#86efac"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
          </div>
          <div><div style="font-size:28px;font-weight:700;color:#fff">${s.activeSessionCount}</div><div style="font-size:12px;color:#86efac;font-weight:500">Active Sessions</div></div>
        </div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:20px">
        <div style="background:linear-gradient(135deg,#450a0a,#7f1d1d);border-radius:14px;padding:18px 20px;display:flex;align-items:center;gap:14px;box-shadow:0 4px 15px rgba(220,38,38,.2);border:1px solid rgba(239,68,68,.2)">
          <div style="background:rgba(255,255,255,.1);width:44px;height:44px;border-radius:12px;display:flex;align-items:center;justify-content:center;flex-shrink:0">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color:#fca5a5"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          </div>
          <div><div style="font-size:24px;font-weight:700;color:#fca5a5">${s.criticalCount}</div><div style="font-size:12px;color:#fca5a5;font-weight:500">Critical Alerts</div></div>
        </div>
        <div style="background:linear-gradient(135deg,#451a03,#78350f);border-radius:14px;padding:18px 20px;display:flex;align-items:center;gap:14px;box-shadow:0 4px 15px rgba(217,119,6,.2);border:1px solid rgba(245,158,11,.2)">
          <div style="background:rgba(255,255,255,.1);width:44px;height:44px;border-radius:12px;display:flex;align-items:center;justify-content:center;flex-shrink:0">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color:#fde68a"><path d="M12 20V10"/><path d="M18 20V5"/><path d="M6 20v-2"/></svg>
          </div>
          <div><div style="font-size:24px;font-weight:700;color:#fde68a">${s.highCount}</div><div style="font-size:12px;color:#fde68a;font-weight:500">High Alerts</div></div>
        </div>
      </div>
      <div class="card">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color:var(--primary-light)"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
          <h2 style="font-size:16px;margin:0">Recent Activities</h2>
        </div>
        <div>${(s.recentActivities||[]).slice(0,8).map(a => {
          const dot = a.security_status === 'critical' ? '#ef4444' : a.security_status === 'warning' ? '#f59e0b' : '#3b82f6';
          return `<div style="display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid var(--border)">
            <div style="width:8px;height:8px;border-radius:50%;background:${dot};flex-shrink:0"></div>
            <span class="badge badge-${a.security_status === 'critical' ? 'red' : a.security_status === 'warning' ? 'yellow' : 'blue'}" style="flex-shrink:0">${a.event_type}</span>
            <span style="flex:1;font-size:13px;color:var(--text)">${a.action_detail || ''}</span>
            <span style="font-size:11px;color:var(--text-muted);white-space:nowrap">${a.performed_by}</span>
          </div>`;
        }).join('') || '<div style="text-align:center;color:var(--muted);padding:20px">No recent activities</div>'}
        </div>
      </div>`;
    }
  } catch(e) { content.innerHTML = '<p>Error loading dashboard</p>'; }
}

// ─── Companies ───────────────────────────────────────────────────────────────

async function renderCompanies() {
  const content = document.getElementById('content');
  try {
    const {ok, data} = await api('/companies');
    if (!ok) { content.innerHTML = '<p>Access denied</p>'; return; }
    companies = data || [];
    content.innerHTML = `
      <div class="flex mb-4">
        <button class="btn-primary" onclick="showAddCompany()">+ Add Company</button>
      </div>
      <div class="card"><table>
        <thead><tr><th>Name</th><th>Tenant ID</th><th>Domain</th><th>Servers</th><th>Users</th><th>Actions</th></tr></thead>
        <tbody>${companies.map(c => `<tr>
          <td>${c.name}</td><td class="font-mono">${c.tenant_id}</td><td>${c.domain||'-'}</td>
          <td>${c.server_count||0}</td><td>${c.user_count||0}</td>
          <td><button class="btn-danger btn-sm" onclick="deleteCompany('${c.id}')">Delete</button></td>
        </tr>`).join('')}</tbody>
      </table></div>`;
  } catch(e) { content.innerHTML = '<p>Error</p>'; }
}

function generateTenantId() {
  return 'tnt-' + Math.random().toString(36).substring(2, 10) + '-' + Date.now().toString(36);
}

function showAddCompany() {
  showModal(`
    <h2>Add Company</h2>
    <div class="field"><label>Company Name *</label><input id="f-cname" placeholder="Company name"></div>
    <div class="form-row">
      <div class="field"><label>Tenant ID</label><input id="f-tenid" readonly style="background:#0f172a;color:#94a3b8;cursor:not-allowed" value="${generateTenantId()}"></div>
      <div class="field"><label>Industry</label><select id="f-ind"><option>fintech</option><option>enterprise</option><option>healthcare</option><option>technology</option><option>education</option><option>other</option></select></div>
    </div>
    <div class="field"><label>Domain</label><input id="f-dom" placeholder="example.com"></div>
    <div class="form-row">
      <div class="field"><label>Contact Email *</label><input id="f-cemail" type="email"></div>
      <div class="field"><label>Contact Phone</label><input id="f-phone" placeholder="+1-555-0100"></div>
    </div>
    <div class="field"><label>Billing Email</label><input id="f-bemail" type="email"></div>
    <div class="actions">
      <button class="btn-secondary" onclick="closeModal()">Cancel</button>
      <button class="btn-primary" onclick="addCompany()">Create</button>
    </div>
  `);
}

async function addCompany() {
  const cname = document.getElementById('f-cname').value;
  const tenid = document.getElementById('f-tenid').value;
  if (!cname || !tenid) { toast('Name and Tenant ID required', 'error'); return; }
  const {ok, data} = await api('/companies', {method:'POST', body: JSON.stringify({
    name: cname, tenant_id: tenid, industry: document.getElementById('f-ind').value,
    domain: document.getElementById('f-dom').value, contact_email: document.getElementById('f-cemail').value,
    contact_phone: document.getElementById('f-phone').value, billing_email: document.getElementById('f-bemail').value
  })});
  if (ok) { toast('Company created'); closeModal(); renderCompanies(); }
  else { toast(data?.detail || 'Error', 'error'); }
}

async function deleteCompany(id) {
  if (!confirm('Delete this company?')) return;
  const {ok} = await api('/companies/' + id, {method:'DELETE'});
  if (ok) { toast('Company deleted'); renderCompanies(); }
  else toast('Delete failed', 'error');
}

// ─── Users ───────────────────────────────────────────────────────────────────

async function renderUsers() {
  const content = document.getElementById('content');
  try {
    const ep = user.role === 'superuser' ? '/users/all' : '/users';
    const {ok, data} = await api(ep);
    if (!ok) { content.innerHTML = '<p>Access denied</p>'; return; }
    users = data || [];
    content.innerHTML = `
      <div class="flex mb-4">
        <button class="btn-primary" onclick="showAddUser()">+ Add User</button>
      </div>
      <div class="card"><table>
        <thead><tr><th>Name</th><th>Username</th><th>Role</th><th>Company</th><th>Status</th><th>Last Login</th><th>Actions</th></tr></thead>
        <tbody>${users.map(u => `<tr>
          <td>${u.full_name}</td><td class="font-mono">${u.username}</td>
          <td><span class="badge badge-${u.role === 'superuser' ? 'purple' : u.role === 'admin' ? 'blue' : 'green'}">${u.role}</span></td>
          <td>${u.company_name||'-'}</td>
          <td><span class="badge ${u.status === 'active' ? 'badge-green' : 'badge-red'}">${u.status}</span></td>
          <td class="text-sm">${u.last_login ? new Date(u.last_login).toLocaleString() : '-'}</td>
          <td>${u.role !== 'superuser' ? `<button class="btn-sm ${u.status === 'active' ? 'btn-warning' : 'btn-success'}" onclick="toggleUserStatus('${u.id}','${u.status}')">${u.status === 'active' ? 'Deactivate' : 'Activate'}</button>` : ''}</td>
        </tr>`).join('')}</tbody>
      </table></div>`;
  } catch(e) { content.innerHTML = '<p>Error</p>'; }
}

async function showAddUser() {
  const {data: companies} = await api('/companies');
  const isAdmin = user.role === 'admin';
  showModal(`
    <h2>Add User</h2>
    <div class="field"><label>Full Name *</label><input id="u-name"></div>
    <div class="field"><label>Username *</label><input id="u-username"></div>
    <div class="field"><label>Password * (min 6 chars)</label><input id="u-pass" type="password"></div>
    ${isAdmin ? '' : `<div class="field"><label>Role</label><select id="u-role"><option value="user">User</option><option value="admin">Admin</option></select></div>`}
    <div class="field"><label>Company</label><select id="u-company">${(companies||[]).map(c => `<option value="${c.id}" ${isAdmin && c.id === user.companyId ? 'selected' : ''}>${c.name}</option>`).join('')}</select></div>
    <div class="actions">
      <button class="btn-secondary" onclick="closeModal()">Cancel</button>
      <button class="btn-primary" onclick="addUser()">Create</button>
    </div>
  `);
  if (isAdmin) { const s = document.getElementById('u-company'); if (s) s.disabled = true; }
}

async function addUser() {
  const name = document.getElementById('u-name').value;
  const username = document.getElementById('u-username').value;
  const pass = document.getElementById('u-pass').value;
  const company = document.getElementById('u-company').value;
  if (!name || !username || !pass || pass.length < 6) { toast('Fill all required fields, password min 6 chars', 'error'); return; }
  const role = user.role === 'admin' ? 'user' : document.getElementById('u-role').value;
  const {ok, data} = await api('/users', {method:'POST', body: JSON.stringify({full_name:name, username, password:pass, role, company_id:company})});
  if (ok) { toast('User created'); closeModal(); renderUsers(); }
  else toast(data?.detail || 'Error creating user', 'error');
}

async function toggleUserStatus(id, currentStatus) {
  const newStatus = currentStatus === 'active' ? 'inactive' : 'active';
  const {ok} = await api('/users/' + id + '/status', {method:'PATCH', body: JSON.stringify({status: newStatus})});
  if (ok) { toast('Status updated'); renderUsers(); }
  else toast('Failed', 'error');
}

// ─── Servers ─────────────────────────────────────────────────────────────────

async function renderServers() {
  const content = document.getElementById('content');
  try {
    const {ok, data} = await api('/servers' + (user.role === 'superuser' ? '' : ''));
    if (!ok) { content.innerHTML = '<p>Error</p>'; return; }
    servers = data || [];
    let html = '';
    if (user.role === 'superuser') {
      html += '<div class="flex mb-4"><button class="btn-primary" onclick="showAddServer()">+ Add Target Server</button></div>';
    }
    for (const s of servers) {
      html += `<div class="server-card" onclick="showServerDetail('${s.id}')">
        <div class="header">
          <span class="badge ${s.status === 'active' ? 'badge-green' : 'badge-red'}">${s.status}</span>
          <strong style="font-size:15px;flex:1">${s.name}</strong>
          <span class="font-mono text-sm" style="color:#94a3b8">${s.ip}</span>
          <span class="arrow">▼</span>
        </div>
      </div>`;
    }
    if (!servers.length) html += '<div class="text-center text-muted" style="padding:40px">No servers found</div>';
    content.innerHTML = html;
    // Check active requests for each server
    for (const s of servers) {
      if (s.status === 'active') {
        const r = await api('/requests/check-active/' + s.id);
        if (r.ok && r.data?.hasActive) {
          // Mark as connectable - stored for detail modal
        }
      }
    }
  } catch(e) { content.innerHTML = '<p>Error loading servers</p>'; }
}

function showServerDetail(serverId) {
  const s = servers.find(x => x.id === serverId);
  if (!s) return;
  const isAdminOrSuper = user.role === 'superuser' || user.role === 'admin';
  showModal(`
    <h2 style="display:flex;align-items:center;gap:12px">
      <span class="badge ${s.status === 'active' ? 'badge-green' : 'badge-red'}">${s.status}</span>
      ${s.name}
    </h2>
    <div class="server-detail-grid">
      <div class="item"><div class="lbl">IP Address</div><div class="val font-mono">${s.ip}</div></div>
      ${isAdminOrSuper ? `
      <div class="item"><div class="lbl">Port</div><div class="val font-mono">${s.port}</div></div>
      <div class="item"><div class="lbl">Operating System</div><div class="val">${s.os || '-'}</div></div>
      <div class="item"><div class="lbl">Connection Types</div><div class="val">${(s.allowed_connection_types||[]).join(', ') || '-'}</div></div>
      <div class="item"><div class="lbl">Company</div><div class="val">${s.company_name || '-'}</div></div>
      <div class="item"><div class="lbl">Server ID</div><div class="val font-mono text-xs">${s.id}</div></div>
      ` : `
      <div class="item"><div class="lbl">Company</div><div class="val">${s.company_name || '-'}</div></div>
      `}
    </div>
    <div class="actions" style="margin-top:16px;display:flex;gap:8px;flex-wrap:wrap">
      ${s.status === 'active'
        ? `<button class="btn-primary" onclick="closeModal();checkAndConnect('${s.id}')">Request Access</button>`
        : `<button class="btn-secondary" disabled>Unavailable</button>`
      }
      ${user.role === 'superuser' ? `<button class="btn-danger" onclick="closeModal();deleteServer('${s.id}')">Delete Server</button>` : ''}
      <button class="btn-secondary" onclick="closeModal()">Close</button>
    </div>
  `);
}

async function deleteServer(serverId) {
  if (!confirm('Delete this server permanently?')) return;
  const {ok} = await api('/servers/' + serverId, {method:'DELETE'});
  if (ok) { toast('Server deleted'); renderServers(); }
  else toast('Delete failed', 'error');
}

async function checkAndConnect(serverId) {
  const r = await api('/requests/check-active/' + serverId);
  if (r.ok && r.data?.hasActive) {
    openTerminal(serverId, r.data.request.id);
    return;
  }
  showModal(`
    <h2>Request Access</h2>
    <div class="field"><label>Duration (minutes) *</label><input id="req-dur" type="number" value="30" min="5"></div>
    <div class="field"><label>Access Level</label><select id="req-level"><option value="user">User</option><option value="root">Root</option></select></div>
    <div class="field"><label>Description</label><textarea id="req-desc" rows="3"></textarea></div>
    <div class="actions">
      <button class="btn-secondary" onclick="closeModal()">Cancel</button>
      <button class="btn-primary" onclick="submitRequest('${serverId}')">Submit Request</button>
    </div>
  `);
}

async function submitRequest(serverId) {
  const dur = parseInt(document.getElementById('req-dur').value);
  const level = document.getElementById('req-level').value;
  const desc = document.getElementById('req-desc').value;
  if (!dur || dur < 1) { toast('Invalid duration', 'error'); return; }
  const {ok, data} = await api('/requests', {method:'POST', body: JSON.stringify({server_id: serverId, access_level: level, duration_minutes: dur, description: desc})});
  if (ok) { toast('Request submitted! Waiting for approval.'); closeModal(); }
  else toast(data?.detail || 'Error', 'error');
}

async function showAddServer() {
  const {data: companies} = await api('/companies');
  showModal(`
    <h2>Add Target Server</h2>
    <div class="field"><label>Server Name *</label><input id="s-name"></div>
    <div class="field"><label>IP Address *</label><input id="s-ip" placeholder="10.0.0.1"></div>
    <div class="form-row">
      <div class="field"><label>Port</label><input id="s-port" type="number" value="22"></div>
      <div class="field"><label>OS</label><select id="s-os"><option>Ubuntu Server 22.04 LTS</option><option>Ubuntu Server 20.04 LTS</option><option>Windows Server 2022</option><option>Windows Server 2019</option><option>CentOS 9</option><option>Rocky Linux 9</option></select></div>
    </div>
    <div class="field"><label>Company *</label><select id="s-company">${(companies||[]).map(c => `<option value="${c.id}">${c.name}</option>`).join('')}</select></div>
    <div class="actions">
      <button class="btn-secondary" onclick="closeModal()">Cancel</button>
      <button class="btn-primary" onclick="addServer()">Add Server</button>
    </div>
  `);
}

async function addServer() {
  const name = document.getElementById('s-name').value;
  const ip = document.getElementById('s-ip').value;
  const company = document.getElementById('s-company').value;
  if (!name || !ip || !company) { toast('Name, IP, and Company required', 'error'); return; }
  const {ok} = await api('/servers', {method:'POST', body: JSON.stringify({
    name, ip, port: parseInt(document.getElementById('s-port').value) || 22,
    os: document.getElementById('s-os').value, company_id: company
  })});
  if (ok) { toast('Server added'); closeModal(); renderServers(); }
  else toast('Error', 'error');
}

// ─── My Requests ─────────────────────────────────────────────────────────────

async function renderMyRequests(statusFilter) {
  const content = document.getElementById('content');
  try {
    const url = '/requests/my' + (statusFilter ? '?status=' + statusFilter : '');
    const {ok, data} = await api(url);
    if (!ok) { content.innerHTML = '<p>Error</p>'; return; }
    requests = data || [];
    content.innerHTML = `
      <div class="tabs">
        <button class="${!statusFilter?'active':''}" onclick="renderMyRequests()">All</button>
        <button class="${statusFilter==='pending'?'active':''}" onclick="renderMyRequests('pending')">Pending</button>
        <button class="${statusFilter==='approved'?'active':''}" onclick="renderMyRequests('approved')">Approved</button>
        <button class="${statusFilter==='rejected'?'active':''}" onclick="renderMyRequests('rejected')">Rejected</button>
      </div>
      <div class="card"><table>
        <thead><tr><th>ID</th><th>Server</th><th>Level</th><th>Duration</th><th>Status</th><th>Requested</th><th>Actions</th></tr></thead>
        <tbody>${requests.map(r => `<tr>
          <td class="font-mono text-xs">${r.id?.slice(0,8)}...</td>
          <td>${r.server_name}</td>
          <td><span class="badge ${r.access_level === 'root' ? 'badge-red' : 'badge-green'}">${r.access_level}</span></td>
          <td>${r.duration_minutes}m</td>
          <td><span class="badge ${r.status === 'approved' ? 'badge-green' : r.status === 'pending' ? 'badge-yellow' : r.status === 'rejected' ? 'badge-red' : 'badge-gray'}">${r.status}</span></td>
          <td class="text-sm">${timeAgo(r.requested_at)}</td>
          <td>
            ${r.status === 'pending' ? `<button class="btn-sm btn-warning" onclick="cancelReq('${r.id}')">Cancel</button>` : ''}
            ${r.status === 'approved' && r.expires_at && new Date(r.expires_at) > new Date() ? `<button class="btn-sm btn-success" onclick="openTerminal('${r.server_id}','${r.id}')">Connect</button>` : ''}
            <button class="btn-sm btn-danger" onclick="deleteReq('${r.id}')">Delete</button>
          </td>
        </tr>`).join('')||'<tr><td colspan="7" class="text-center text-muted">No requests found</td></tr>'}</tbody>
      </table></div>`;
  } catch(e) { content.innerHTML = '<p>Error</p>'; }
}

async function cancelReq(id) {
  if (!confirm('Cancel this request?')) return;
  const {ok} = await api('/requests/' + id + '/cancel', {method:'POST'});
  if (ok) { toast('Request cancelled'); renderMyRequests(); }
}

async function deleteReq(id) {
  if (!confirm('Delete this request permanently?')) return;
  const {ok} = await api('/requests/' + id, {method:'DELETE'});
  if (ok) { toast('Request deleted'); renderMyRequests(); }
  else toast('Delete failed', 'error');
}

// ─── Pending Approvals ───────────────────────────────────────────────────────

async function renderApprovals() {
  const content = document.getElementById('content');
  try {
    const {ok, data} = await api('/requests?status=pending');
    if (!ok) { content.innerHTML = '<p>Error</p>'; return; }
    const pending = data || [];
    content.innerHTML = `
      <div class="card"><table>
        <thead><tr><th>Requester</th><th>Server</th><th>Company</th><th>Level</th><th>Duration</th><th>Requested</th><th>Actions</th></tr></thead>
        <tbody>${pending.map(r => `<tr>
          <td>${r.requester_name||r.requester_username}</td>
          <td>${r.server_name}</td>
          <td>${r.company_name}</td>
          <td><span class="badge ${r.access_level === 'root' ? 'badge-red' : 'badge-green'}">${r.access_level}</span></td>
          <td>${r.duration_minutes}m</td>
          <td class="text-sm">${timeAgo(r.requested_at)}</td>
          <td><button class="btn-sm btn-success" onclick="approveReq('${r.id}')">Approve</button>
              <button class="btn-sm btn-danger" onclick="rejectReq('${r.id}')">Reject</button></td>
        </tr>`).join('')||'<tr><td colspan="7" class="text-center text-muted">No pending approvals</td></tr>'}</tbody>
      </table></div>`;
  } catch(e) { content.innerHTML = '<p>Error</p>'; }
}

async function approveReq(id) {
  if (!confirm('Approve this request?')) return;
  const {ok} = await api('/requests/' + id + '/approve', {method:'POST'});
  if (ok) { toast('Request approved'); renderApprovals(); }
  else toast('Error', 'error');
}

async function rejectReq(id) {
  if (!confirm('Reject this request?')) return;
  const {ok} = await api('/requests/' + id + '/reject', {method:'POST'});
  if (ok) { toast('Request rejected'); renderApprovals(); }
  else toast('Error', 'error');
}

// ─── Session Recordings ──────────────────────────────────────────────────────

async function renderRecordings() {
  const content = document.getElementById('content');
  try {
    const {ok, data} = await api('/sessions');
    if (!ok) { content.innerHTML = '<p>Error</p>'; return; }
    content.innerHTML = `
      <div class="card"><table>
        <thead><tr><th>User</th><th>Server</th><th>Company</th><th>Duration</th><th>Date</th><th>Actions</th></tr></thead>
        <tbody>${(data||[]).filter(s => s.status !== 'active').map(s => {
          const dur = s.ended_at ? Math.floor((new Date(s.ended_at) - new Date(s.started_at))/1000) : 0;
          return `<tr>
            <td>${s.user_name||s.user_username}</td>
            <td>${s.server_name}</td>
            <td>${s.company_name}</td>
            <td>${Math.floor(dur/60)}m ${dur%60}s</td>
            <td class="text-sm">${new Date(s.started_at).toLocaleDateString()}</td>
            <td><button class="btn-sm btn-primary" onclick="playRecording('${s.id}')">Play</button></td>
          </tr>`;
        }).join('')||'<tr><td colspan="6" class="text-center text-muted">No recordings</td></tr>'}</tbody>
      </table></div>`;
  } catch(e) { content.innerHTML = '<p>Error</p>'; }
}

async function playRecording(sessionId) {
  const {ok, data} = await api('/sessions/' + sessionId + '/recording');
  if (!ok || !data?.recording) { toast('Recording not found', 'error'); return; }
  const rec = data.recording;
  showModal(`
    <h2>Session Replay</h2>
    <div id="replay-wrap" style="background:#000;border-radius:8px;padding:16px;font-family:monospace;font-size:13px;max-height:500px;overflow-y:auto;white-space:pre-wrap;line-height:1.5;color:#00ff00"></div>
    <div class="actions"><button class="btn-primary" onclick="document.getElementById('replay-wrap').innerHTML=''; replayIndex=0; replayRecording(${JSON.stringify(rec).replace(/"/g,'&quot;')})">▶ Play</button>
    <button class="btn-secondary" onclick="closeModal()">Close</button></div>
  `);
}

let replayIndex = 0;
let replayTimeout = null;

function replayRecording(rec) {
  const wrap = document.getElementById('replay-wrap');
  if (!wrap) return;
  if (replayIndex >= rec.length) { toast('Replay complete'); return; }
  const entry = rec[replayIndex];
  if (entry.event === 'output') {
    const pre = wrap.textContent;
    wrap.textContent = pre + entry.data;
    wrap.scrollTop = wrap.scrollHeight;
  }
  replayIndex++;
  const delay = replayIndex < rec.length ? Math.min((rec[replayIndex].timestamp - entry.timestamp), 100) : 100;
  replayTimeout = setTimeout(() => replayRecording(rec), Math.max(delay, 15));
}

// ─── Audit Logs ──────────────────────────────────────────────────────────────

let auditPage = 0;
async function renderAuditLogs() {
  const content = document.getElementById('content');
  try {
    const {ok, data} = await api('/audit-logs?limit=50&offset=' + (auditPage * 50));
    if (!ok) { content.innerHTML = '<p>Error</p>'; return; }
    const logs = data?.rows || [];
    const total = data?.total || 0;
    const pages = Math.ceil(total / 50);
    content.innerHTML = `
      <div class="flex mb-4">
        <button class="btn-success btn-sm" onclick="exportCsv()">📥 Export CSV</button>
        <button class="btn-secondary btn-sm" onclick="auditPage=0;renderAuditLogs()">Clear Filters</button>
        <div class="ml-auto flex gap-2">
          <button class="btn-secondary btn-sm" ${auditPage <= 0 ? 'disabled' : ''} onclick="auditPage--;renderAuditLogs()">← Prev</button>
          <span class="text-sm" style="padding:6px 0">Page ${auditPage+1}/${Math.max(pages,1)}</span>
          <button class="btn-secondary btn-sm" ${auditPage >= pages-1 ? 'disabled' : ''} onclick="auditPage++;renderAuditLogs()">Next →</button>
        </div>
      </div>
      <div class="card"><table>
        <thead><tr><th>Timestamp</th><th>Event</th><th>By</th><th>Target</th><th>Details</th><th>Status</th><th>Action</th></tr></thead>
        <tbody>${logs.map(l => `<tr>
          <td class="text-sm">${new Date(l.timestamp).toLocaleString()}</td>
          <td><span class="badge badge-blue">${l.event_type}</span></td>
          <td>${l.performed_by}</td>
          <td class="text-sm">${l.target?.slice(0,12)||'-'}</td>
          <td class="text-sm">${l.action_detail||''}</td>
          <td><span class="badge ${l.security_status === 'critical' ? 'badge-red' : l.security_status === 'warning' ? 'badge-yellow' : 'badge-blue'}">${l.security_status}</span></td>
          <td>${(l.event_type === 'suspicious_command' || l.event_type === 'suspicious_output') && l.target ? `<button class="btn-sm btn-danger" onclick="terminateSessionFromLog('${l.target}')">Terminate</button>` : ''}</td>
        </tr>`).join('')||'<tr><td colspan="7" class="text-center text-muted">No logs</td></tr>'}</tbody>
      </table></div>`;
  } catch(e) { content.innerHTML = '<p>Error</p>'; }
}

async function exportCsv() {
  window.open(API + '/audit-logs/export?token=' + token, '_blank');
}

async function terminateSessionFromLog(sessionId) {
  if (!confirm('Terminate this session?')) return;
  const {ok} = await api('/sessions/' + sessionId + '/terminate', {method:'POST'});
  if (ok) { toast('Session terminated'); renderAuditLogs(); }
  else toast('Failed to terminate', 'error');
}

// ─── Settings ────────────────────────────────────────────────────────────────

function renderSettings() {
  document.getElementById('content').innerHTML = `
    <div class="grid grid-2">
      <div class="card">
        <h2>Change Username</h2>
        <div class="field"><label>Current Username</label><input value="${user.username}" disabled></div>
        <div class="field"><label>New Username</label><input id="set-username" placeholder="New username"></div>
        <button class="btn-primary" onclick="changeUsername()">Save</button>
        <div id="user-msg" class="text-sm mt-4"></div>
      </div>
      <div class="card">
        <h2>Change Password</h2>
        <div class="field"><label>Current Password</label><input id="set-curpass" type="password"></div>
        <div class="field"><label>New Password</label><input id="set-newpass" type="password"></div>
        <div class="field"><label>Confirm Password</label><input id="set-confirm" type="password"></div>
        <button class="btn-primary" onclick="changePassword()">Save</button>
        <div id="pass-msg" class="text-sm mt-4"></div>
      </div>
    </div>
    <div class="card mt-4" id="billing-section" style="${user.role === 'user' ? 'display:none' : ''}">
      <h2>Billing Account</h2>
      <div id="billing-info">Loading...</div>
    </div>`;
  loadBilling();
}

async function loadBilling() {
  if (user.role === 'user') return;
  const {ok, data} = await api('/billing/my');
  if (ok) {
    document.getElementById('billing-info').innerHTML = `
      <div class="flex gap-4">
        <div><span class="text-muted">Balance:</span> <span style="font-size:20px;font-weight:700;color:#4ade80">$${data.balance}</span></div>
        <div><span class="text-muted">Price per user:</span> <span style="font-size:20px;font-weight:700">$${data.price_per_user}</span></div>
      </div>`;
  }
}

async function changeUsername() {
  const nu = document.getElementById('set-username').value;
  if (!nu) { document.getElementById('user-msg').textContent = 'Enter new username'; return; }
  const {ok, data} = await api('/auth/change-username', {method:'POST', body: JSON.stringify({newUsername: nu})});
  document.getElementById('user-msg').textContent = ok ? 'Username changed!' : (data?.detail || 'Error');
  document.getElementById('user-msg').style.color = ok ? '#4ade80' : '#f87171';
}

async function changePassword() {
  const cur = document.getElementById('set-curpass').value;
  const np = document.getElementById('set-newpass').value;
  const conf = document.getElementById('set-confirm').value;
  if (!cur || !np) { document.getElementById('pass-msg').textContent = 'Fill all fields'; return; }
  if (np !== conf) { document.getElementById('pass-msg').textContent = 'Passwords do not match'; return; }
  if (np.length < 6) { document.getElementById('pass-msg').textContent = 'Password too short'; return; }
  const {ok, data} = await api('/auth/change-password', {method:'POST', body: JSON.stringify({currentPassword: cur, newPassword: np})});
  document.getElementById('pass-msg').textContent = ok ? 'Password changed!' : (data?.detail || 'Error');
  document.getElementById('pass-msg').style.color = ok ? '#4ade80' : '#f87171';
}

// ─── Notifications ───────────────────────────────────────────────────────────

async function loadNotifications() {
  try {
    const {ok, data} = await api('/notifications/unread-count');
    if (ok && data?.count > 0) {
      document.getElementById('notif-badge').textContent = data.count;
      document.getElementById('notif-badge').classList.remove('hidden');
    } else {
      document.getElementById('notif-badge').classList.add('hidden');
    }
    const r = await api('/notifications?limit=20');
    if (r.ok) notifications = r.data || [];
  } catch(e) {}
}

async function showNotifications() {
  await loadNotifications();
  showModal(`
    <h2>Notifications</h2>
    <div class="flex mb-4"><button class="btn-sm btn-secondary" onclick="markAllRead()">Mark All Read</button></div>
    <div style="max-height:400px;overflow-y:auto">
      ${notifications.map(n => `<div class="flex" style="padding:12px;border-bottom:1px solid #1e293b;${n.read ? 'opacity:.6' : 'border-left:3px solid #3b82f6;padding-left:9px'}" onclick="markNotifRead('${n.id}','${n.link||''}')">
        <div class="flex-1"><div class="text-sm">${n.message}</div><div class="text-xs text-muted">${new Date(n.created_at).toLocaleString()}</div></div>
      </div>`).join('')||'<div class="text-center text-muted" style="padding:20px">No notifications</div>'}
    </div>
    <div class="actions"><button class="btn-secondary" onclick="closeModal()">Close</button></div>
  `);
}

async function markNotifRead(id, link) {
  await api('/notifications/' + id + '/read', {method:'PATCH'});
  if (link) { closeModal(); navigateTo(link.replace('/','')); }
  loadNotifications();
}

async function markAllRead() {
  await api('/notifications/read-all', {method:'POST'});
  toast('All marked as read');
  closeModal();
  loadNotifications();
}

// ─── Terminal / Session ──────────────────────────────────────────────────────

function openTerminal(serverId, requestId) {
  document.getElementById('terminal-wrap').classList.add('active');
  document.getElementById('term-info').textContent = user.username.split('@')[0] + '@server:' + serverId.slice(0,8);
  
  const termDiv = document.getElementById('terminal');
  if (termWs) termWs.close();
  termDiv.innerHTML = '<div id="term-output" style="flex:1;overflow-y:auto;padding:16px;white-space:pre-wrap;word-break:break-all;font-family:Menlo,Monaco,\'Courier New\',monospace;font-size:14px;line-height:1.5;color:#4ade80;background:#0f172a;min-height:100px"></div><div id="term-inputline" style="display:flex;align-items:center;gap:8px;padding:8px 16px;border-top:1px solid #1e293b;background:#0a0f1a;flex-shrink:0"><span id="term-prompt" style="color:#4ade80;font-weight:700;font-size:14px;white-space:nowrap">$</span><input id="term-input" style="flex:1;background:#0f172a;border:1px solid #334155;border-radius:4px;color:#e2e8f0;font-family:Menlo,Monaco,\'Courier New\',monospace;font-size:14px;padding:8px 10px;outline:none" autofocus></div>';
  
  const termOut = document.getElementById('term-output');
  termOut.textContent = 'Connecting to session...';
  
  const wsUrl = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws/terminal?token=' + token;
  termWs = new WebSocket(wsUrl);
  
  termWs.onopen = () => {
    termOut.textContent += '\nWebSocket connected. Joining session...';
    termWs.send(JSON.stringify({action: 'join_session', requestId, serverId}));
  };
  
  termWs.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data);
      if (msg.type === 'terminal_output') {
        termOut.textContent += msg.data;
        termOut.scrollTop = termOut.scrollHeight;
      } else if (msg.type === 'session_created') {
        terminalSession = msg.data.sessionId;
        showTimer(requestId);
      } else if (msg.type === 'ssh_ready') {
        termOut.textContent += '\nSSH Connection established';
        termOut.scrollTop = termOut.scrollHeight;
        document.getElementById('term-prompt').textContent = user.username.split('@')[0] + '@' + serverId.slice(0,8) + ':~$';
        document.getElementById('term-input').focus();
      } else if (msg.type === 'session_ended') {
        termOut.textContent += '\n\n*** Session ' + msg.data.reason + ' ***';
        termOut.scrollTop = termOut.scrollHeight;
        showTimer(null);
      } else if (msg.type === 'session_error') {
        termOut.textContent += '\n*** Error: ' + msg.data + ' ***';
        termOut.scrollTop = termOut.scrollHeight;
      } else if (msg.type === 'error') {
        termOut.textContent += '\n*** Error: ' + msg.data + ' ***';
        termOut.scrollTop = termOut.scrollHeight;
      }
    } catch(e2) {}
  };
  
  termWs.onerror = () => {
    const out = document.getElementById('term-output');
    if (out) out.textContent += '\n*** WebSocket connection failed ***';
  };
  
  termWs.onclose = () => {
    const out = document.getElementById('term-output');
    if (out) out.textContent += '\n*** Connection closed ***';
  };
  
  document.getElementById('term-input').addEventListener('keydown', function handleTermKey(e) {
    if (e.key === 'Enter') {
      const inp = document.getElementById('term-input');
      const cmd = inp.value;
      const text = cmd + '\n';
      if (termWs && termWs.readyState === WebSocket.OPEN) {
        termOut.textContent += '\n' + document.getElementById('term-prompt').textContent + ' ' + cmd + '\n';
        termOut.scrollTop = termOut.scrollHeight;
        termWs.send(JSON.stringify({type: 'terminal_input', data: text}));
      }
      inp.value = '';
      e.preventDefault();
    }
  });
}

function showTimer(requestId) {
  if (terminalTimer) { clearInterval(terminalTimer); terminalTimer = null; }
  if (!requestId) { document.getElementById('term-timer').textContent = ''; return; }
  terminalTimer = setInterval(async () => {
    try {
      const {ok, data} = await api('/requests?status=approved');
      if (ok && data) {
        const req = data.find(r => r.id === requestId);
        if (req?.expires_at) {
          const remaining = Math.floor((new Date(req.expires_at) - new Date()) / 1000);
          if (remaining <= 0) {
            document.getElementById('term-timer').textContent = 'EXPIRED';
            terminateSession();
          } else {
            const m = Math.floor(remaining / 60);
            const s = remaining % 60;
            document.getElementById('term-timer').textContent = m + ':' + s.toString().padStart(2, '0');
          }
        }
      }
    } catch(e) {}
  }, 1000);
}

function terminateSession() {
  if (terminalSession) {
    api('/sessions/' + terminalSession + '/terminate', {method:'POST'});
  }
  if (termWs) { termWs.send(JSON.stringify({type: 'terminate_session'})); termWs.close(); }
  closeTerminal();
}

function closeTerminal() {
  document.getElementById('terminal-wrap').classList.remove('active');
  if (termWs) { termWs.close(); termWs = null; }
  if (terminalTimer) { clearInterval(terminalTimer); terminalTimer = null; }
  terminalSession = null;
}

// ─── Modal ───────────────────────────────────────────────────────────────────

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

// ─── Helpers ─────────────────────────────────────────────────────────────────

function timeAgo(dateStr) {
  const now = new Date();
  const d = new Date(dateStr);
  const sec = Math.floor((now - d) / 1000);
  if (sec < 60) return sec + 's ago';
  const min = Math.floor(sec / 60);
  if (min < 60) return min + 'm ago';
  const h = Math.floor(min / 60);
  if (h < 24) return h + 'h ago';
  return Math.floor(h / 24) + 'd ago';
}

function $(id) { return document.getElementById(id); }

// ─── Init ────────────────────────────────────────────────────────────────────

// Theme init
const savedTheme = localStorage.getItem('pam_theme');
if (savedTheme === 'light') {
  document.documentElement.setAttribute('data-theme', 'light');
  setThemeToggle('light');
} else {
  setThemeToggle('dark');
}

// Check for saved session
const savedToken = localStorage.getItem('pam_token');
const savedUser = localStorage.getItem('pam_user');
if (savedToken && savedUser) {
  try {
    token = savedToken;
    user = JSON.parse(savedUser);
    document.getElementById('login-page').classList.add('hidden');
    document.getElementById('sidebar').classList.remove('hidden');
    document.getElementById('topbar').classList.remove('hidden');
    showApp();
  } catch(e) {}
}

// Also handle login page Enter key
document.getElementById('login-pass').addEventListener('keydown', e => {
  if (e.key === 'Enter') handleLogin();
});
document.getElementById('login-user').addEventListener('keydown', e => {
  if (e.key === 'Enter') handleLogin();
});
</script>
</body>
</html>"""
