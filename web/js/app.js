// ═══ Page Navigation ═══════════════════════════════
document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.getElementById('page-' + btn.dataset.page).classList.add('active');
    refreshCurrentPage();
  });
});

function refreshCurrentPage() {
  const id = document.querySelector('.page.active').id;
  if (id === 'page-dashboard') refreshDashboard();
  else if (id === 'page-tunnels') refreshTunnelPage();
  else if (id === 'page-domains') refreshDomainPage();
  else if (id === 'page-logs') refreshLogPage();
}

// ═══ Called by Python ═══════════════════════════════
function pushLogLine(msg) {
  const pre = document.getElementById('log-output');
  if (pre.querySelector('.log-hint')) pre.textContent = '';
  pre.textContent += msg + '\n';
  pre.scrollTop = pre.scrollHeight;
  const lines = pre.textContent.split('\n');
  if (lines.length > 2000) pre.textContent = lines.slice(-1000).join('\n');
}

function updateState(state) {
  const el = document.getElementById('tunnel-state');
  const sEl = document.getElementById('s-tunnel');
  const logStart = document.getElementById('log-btn-start');
  const logStop = document.getElementById('log-btn-stop');
  const sbStart = document.getElementById('btn-start');
  const sbStop = document.getElementById('btn-stop');

  const map = {
    running:  ['success', '● 运行中'],
    starting: ['warn',    '● 启动中...'],
    stopping: ['warn',    '● 停止中...'],
    stopped:  ['muted',   '● 未运行'],
  };
  const [cls, txt] = map[state] || map.stopped;
  const active = state === 'running' || state === 'starting';

  el.textContent = txt; el.className = 'state ' + cls;
  sEl.textContent = state === 'running' ? '运行中' : state === 'starting' ? '启动中...' : '';
  sEl.className = state === 'running' ? 'state success' : state === 'starting' ? 'state warn' : '';

  logStart.disabled = active;
  logStop.disabled = !active;
  sbStart.disabled = active;
  sbStop.disabled = !active;
}

// ═══ Status Bar ═════════════════════════════════════
function refreshStatusBar() {
  pywebview.api.get_status().then(s => {
    document.getElementById('s-version').textContent = s.installed
      ? (s.version ? 'cloudflared v' + s.version : 'cloudflared 已安装')
      : 'cloudflared 未安装';
    const login = document.getElementById('s-login');
    login.textContent = s.logged_in ? '已登录' : '未登录';
    login.className = s.logged_in ? 'state success' : '';
  });
}

// ═══ Dashboard ══════════════════════════════════════
function refreshDashboard() {
  pywebview.api.get_status().then(s => {
    // 安装状态卡片
    const ins = document.getElementById('status-installed');
    const ver = document.getElementById('status-version');
    const scIns = document.getElementById('sc-installed');
    ins.textContent = s.installed ? '已安装' : '未安装';
    ver.textContent = s.version ? 'v' + s.version : '';
    scIns.className = 'stat-card ' + (s.installed ? 'sc-ok' : 'sc-err');

    // 登录状态卡片
    const login = document.getElementById('status-login');
    const scLogin = document.getElementById('sc-login');
    login.textContent = s.logged_in ? '已登录' : '未登录';
    scLogin.className = 'stat-card ' + (s.logged_in ? 'sc-ok' : 'sc-err');
  });

  refreshTunnelTable();
  refreshAutostart();
  refreshStatusBar();
}

function refreshTunnelTable() {
  pywebview.api.list_tunnels().then(data => {
    const tbody = document.querySelector('#tunnel-table tbody');
    tbody.innerHTML = '';
    if (!data || !data.tunnels) return;
    data.tunnels.forEach(t => {
      const name = t.id === data.current_id ? t.name + ' (当前)' : t.name;
      const tid = t.id.substring(0, 12) + '...';
      const conn = t.connections > 0 ? '<b>' + t.connections + '</b>' : '0';
      const tr = document.createElement('tr');
      tr.innerHTML = '<td>' + esc(name) + '</td><td>' + esc(tid) + '</td><td class="right">' + conn + '</td>';
      if (t.id === data.current_id) tr.style.background = 'rgba(63,185,80,.05)';
      tbody.appendChild(tr);
    });
  });
}

function refreshAutostart() {
  pywebview.api.get_autostart().then(as => {
    const el = document.getElementById('autostart-status');
    const sc = document.getElementById('sc-autostart');
    const on = document.getElementById('btn-autostart-on');
    const off = document.getElementById('btn-autostart-off');

    if (as.enabled) {
      el.textContent = '已开启'; el.className = 'sc-val';
      sc.className = 'stat-card sc-ok';
      on.style.display = 'none'; off.style.display = '';
    } else {
      el.textContent = '未设置'; el.className = 'sc-val';
      sc.className = 'stat-card sc-warn';
      on.style.display = ''; off.style.display = 'none';
    }
  });
}

function installCloudflared() {
  const btn = document.getElementById('btn-install');
  btn.disabled = true; btn.textContent = '安装中...';
  pywebview.api.install().then(r => { alert(r.message); refreshDashboard(); });
}

function loginCloudflare() {
  const btn = document.getElementById('btn-login');
  btn.disabled = true; btn.textContent = '登录中...';
  pywebview.api.login().then(r => { alert(r.message); refreshDashboard(); });
}

function refreshTunnels() { refreshTunnelTable(); refreshStatusBar(); }

function enableAutostart() {
  pywebview.api.enable_autostart().then(r => { alert(r.message); refreshDashboard(); });
}

function disableAutostart() {
  pywebview.api.disable_autostart().then(r => { alert(r.message); refreshDashboard(); });
}

// ═══ Tunnel Page ════════════════════════════════════
function refreshTunnelPage() {
  pywebview.api.list_tunnels().then(data => {
    const tbody = document.querySelector('#tunnel-list-table tbody');
    tbody.innerHTML = '';
    if (!data || !data.tunnels) return;
    data.tunnels.forEach(t => {
      const checked = t.id === data.current_id ? ' checked' : '';
      const tr = document.createElement('tr');
      tr.innerHTML = '<td><input type="radio" name="tunnel-select" value="' + esc(t.id) + '"' + checked + '></td>' +
        '<td>' + esc(t.name) + '</td><td>' + esc(t.id) + '</td>' +
        '<td class="right">' + t.connections + '</td>' +
        '<td>' + (t.id === data.current_id ? '当前使用' : (t.connections > 0 ? '运行中' : '-')) + '</td>';
      tr.addEventListener('click', () => tr.querySelector('input').checked = true);
      tbody.appendChild(tr);
    });
  });
  refreshStatusBar();
}

function createTunnel() {
  const name = document.getElementById('new-tunnel-name').value.trim();
  if (!name) { alert('请输入隧道名称'); return; }
  pywebview.api.create_tunnel(name).then(r => {
    alert(r.message);
    document.getElementById('new-tunnel-name').value = '';
    refreshTunnelPage();
  });
}

function getSelectedTunnelId() {
  const r = document.querySelector('#tunnel-list-table input[name="tunnel-select"]:checked');
  return r ? r.value : null;
}

function setCurrentTunnel() {
  const tid = getSelectedTunnelId();
  if (!tid) { alert('请先选择一个隧道'); return; }
  pywebview.api.set_current_tunnel(tid).then(() => refreshTunnelPage());
}

function deleteSelectedTunnel() {
  const tid = getSelectedTunnelId();
  if (!tid) { alert('请先选择一个隧道'); return; }
  if (!confirm('确定要删除此隧道吗？此操作不可撤销！')) return;
  pywebview.api.delete_tunnel(tid).then(() => refreshTunnelPage());
}

// ═══ Domain Page ════════════════════════════════════
function refreshDomainPage() {
  pywebview.api.get_config().then(cfg => {
    document.getElementById('config-tunnel').textContent = cfg.current_tunnel
      ? cfg.current_tunnel.substring(0, 12) + '...' : '未设置';
    document.getElementById('config-status').textContent = cfg.has_config ? '已创建' : '未创建';

    const tbody = document.querySelector('#domain-table tbody');
    tbody.innerHTML = '';
    if (cfg.rules) cfg.rules.forEach(r => {
      const tr = document.createElement('tr');
      tr.innerHTML = '<td><input type="radio" name="domain-select"></td>' +
        '<td>' + esc(r.hostname) + '</td><td>' + esc(r.service) + '</td>';
      tr.addEventListener('click', () => tr.querySelector('input').checked = true);
      tbody.appendChild(tr);
    });
  });
  refreshStatusBar();
}

function addDomainRule() {
  const h = document.getElementById('domain-hostname').value.trim();
  const s = document.getElementById('domain-service').value.trim();
  if (!h || !s) { alert('请填写域名和本地服务地址'); return; }
  pywebview.api.add_rule(h, s).then(r => {
    alert(r.message);
    document.getElementById('domain-hostname').value = '';
    refreshDomainPage();
  });
}

function getSelectedDomain() {
  const r = document.querySelector('#domain-table input[name="domain-select"]:checked');
  if (!r) return null;
  return { hostname: r.closest('tr').cells[1].textContent };
}

function deleteDomainRule() {
  const d = getSelectedDomain();
  if (!d) { alert('请先选择一条规则'); return; }
  if (!confirm('确定要删除此映射规则吗？')) return;
  pywebview.api.delete_rule(d.hostname).then(() => refreshDomainPage());
}

function bindDns() {
  const d = getSelectedDomain();
  if (!d) { alert('请先选择一条域名映射规则'); return; }
  pywebview.api.bind_dns(d.hostname).then(r => { alert(r.message); refreshDomainPage(); });
}

function refreshDomains() { refreshDomainPage(); }

// ═══ Log Page ═══════════════════════════════════════
function refreshLogPage() {
  refreshLogPageAsync();
  pywebview.api.get_state().then(r => updateState(r.state));
  refreshStatusBar();
}

async function refreshLogPageAsync() {
  const data = await pywebview.api.list_tunnels();
  const sel = document.getElementById('tunnel-select');
  sel.innerHTML = '<option value="">-- 选择隧道 --</option>';
  if (data && data.tunnels) data.tunnels.forEach(t => {
    const o = document.createElement('option');
    o.value = t.name; o.textContent = t.name;
    if (t.id === data.current_id) o.selected = true;
    sel.appendChild(o);
  });
  return data;
}

function startTunnel() {
  const name = document.getElementById('tunnel-select').value;
  if (!name) { alert('请选择一个隧道'); return; }
  pywebview.api.start_tunnel(name).then(r => { if (!r.success) alert(r.message); });
}

function stopTunnel() { pywebview.api.stop_tunnel(); }

async function killAllTunnels() {
  const ok = await pywebview.api.confirm_kill();
  if (ok) pywebview.api.kill_all();
}

function clearLogs() {
  const pre = document.getElementById('log-output');
  pre.innerHTML = '<span class="log-hint">等待隧道启动...</span>';
}

function copyLogs() {
  navigator.clipboard.writeText(document.getElementById('log-output').textContent);
}

// ═══ Utility ════════════════════════════════════════
function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function refreshAll() {
  refreshStatusBar();
  const id = document.querySelector('.page.active').id;
  if (id === 'page-dashboard') refreshDashboard();
  else if (id === 'page-tunnels') refreshTunnelPage();
  else if (id === 'page-domains') refreshDomainPage();
  else if (id === 'page-logs') refreshLogPage();
}

// ═══ Sidebar Actions ════════════════════════════════
async function sidebarStart() {
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.querySelector('.nav-btn[data-page="logs"]').classList.add('active');
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById('page-logs').classList.add('active');
  await refreshLogPageAsync();
  setTimeout(() => startTunnel(), 300);
}

// ═══ Init ═══════════════════════════════════════════
refreshDashboard();
refreshStatusBar();
