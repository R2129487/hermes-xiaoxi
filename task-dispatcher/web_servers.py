"""服务器管理页面 HTML 模板"""
_SERVERS_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>服务器管理</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Noto Sans SC',sans-serif;background:#f0f2f5;color:#333;padding:20px}
.container{max-width:900px;margin:0 auto}
h1{font-size:20px;margin-bottom:4px}
.subtitle{color:#999;font-size:13px;margin-bottom:20px}
.link-bar{text-align:right;margin-bottom:16px}
.link-bar a{color:#3498db;text-decoration:none;font-size:13px}
.link-bar a:hover{text-decoration:underline}
.card{background:#fff;border-radius:10px;padding:20px;margin-bottom:16px;box-shadow:0 1px 4px rgba(0,0,0,.06)}
.card h2{font-size:15px;font-weight:600;margin-bottom:14px;padding-bottom:10px;border-bottom:1px solid #eee}
.btn{background:#3498db;color:#fff;border:none;padding:8px 18px;border-radius:6px;font-size:13px;cursor:pointer;transition:background .15s}
.btn:hover{background:#2980b9}
.btn-sm{padding:5px 10px;font-size:12px}
.btn-danger{background:#e74c3c}
.btn-danger:hover{background:#c0392b}
.btn-success{background:#27ae60}
.btn-success:hover{background:#219a52}
table{width:100%;border-collapse:collapse}
th,td{text-align:left;padding:8px 6px;border-bottom:1px solid #eee;font-size:12px}
th{font-weight:600;color:#555;font-size:11px;white-space:nowrap}
tr:hover{background:#f8f9fa}
.form-group{margin-bottom:12px}
.form-group label{display:block;font-size:12px;font-weight:600;color:#555;margin-bottom:3px}
.form-group input,.form-group textarea,.form-group select{width:100%;padding:8px 12px;border:1px solid #ddd;border-radius:6px;font-size:13px;outline:none;font-family:inherit}
.form-group input:focus,.form-group textarea:focus,.form-group select:focus{border-color:#3498db}
.form-row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.modal{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.4);display:flex;align-items:center;justify-content:center;z-index:999}
.modal-content{background:#fff;border-radius:12px;padding:24px;width:90%;max-width:550px;max-height:80vh;overflow-y:auto}
.modal-content h3{margin-bottom:16px;font-size:16px}
.toast{position:fixed;top:20px;right:20px;padding:12px 20px;border-radius:8px;color:#fff;font-size:13px;z-index:9999;animation:fadeIn .3s;max-width:360px}
.toast.success{background:#27ae60}
.toast.error{background:#e74c3c}
@keyframes fadeIn{from{opacity:0;transform:translateY(-10px)}to{opacity:1;transform:translateY(0)}}
.empty{text-align:center;padding:40px;color:#999;font-size:14px}
.status-dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px}
.status-online{background:#07C160}
.status-offline{background:#bbb}
</style>
</head>
<body>
<div class="container">
  <div class="link-bar">
    <a href="/chat">← 聊天</a>
    <span style="margin:0 8px;color:#ddd">|</span>
    <a href="/agents">🤖 智能体</a>
    <span style="margin:0 8px;color:#ddd">|</span>
    <a href="/config">⚙️ 配置</a>
  </div>
  <h1>🖥️ 服务器管理</h1>
  <div class="subtitle">管理所有服务器节点，新增机器时在此添加</div>

  <div class="card">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;padding-bottom:10px;border-bottom:1px solid #eee">
      <h2 style="margin:0;padding:0;border:none">服务器列表</h2>
      <button class="btn btn-success" onclick="showAddModal()">➕ 新增</button>
    </div>
    <div id="server-list">
      <div class="empty">加载中...</div>
    </div>
  </div>
</div>

<div id="modal" class="modal" style="display:none" onclick="if(event.target===this)closeModal()">
  <div class="modal-content">
    <h3 id="modal-title">新增服务器</h3>
    <div class="form-row">
      <div class="form-group">
        <label>ID（唯一标识）</label>
        <input id="f-id" placeholder="aliyun-01" />
      </div>
      <div class="form-group">
        <label>名称（显示用）</label>
        <input id="f-name" placeholder="阿里云主节点" />
      </div>
    </div>
    <div class="form-row">
      <div class="form-group">
        <label>IP地址</label>
        <input id="f-host" placeholder="101.37.231.143" />
      </div>
      <div class="form-group">
        <label>SSH端口</label>
        <input id="f-port" placeholder="22" style="width:100px" />
      </div>
    </div>
    <div class="form-row">
      <div class="form-group">
        <label>SSH用户</label>
        <input id="f-ssh-user" placeholder="root" style="width:120px" />
      </div>
      <div class="form-group">
        <label>位置描述</label>
        <input id="f-location" placeholder="阿里云 / 本机 / 新云" />
      </div>
    </div>
    <div class="form-group">
      <label>备注</label>
      <input id="f-remark" placeholder="可选备注信息" />
    </div>
    <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:16px">
      <button class="btn" style="background:#95a5a6" onclick="closeModal()">取消</button>
      <button class="btn btn-success" id="save-btn" onclick="saveServer()">保存</button>
    </div>
  </div>
</div>

<script>
let servers = [];
let editingId = null;

async function loadServers() {
  try {
    const r = await fetch('/api/servers').then(r=>r.json());
    servers = r.data || [];
    render();
  } catch(e) {
    document.getElementById('server-list').innerHTML = '<div class="empty">加载失败</div>';
  }
}

function render() {
  const el = document.getElementById('server-list');
  if (!servers.length) {
    el.innerHTML = '<div class="empty">暂无服务器，点击「新增」添加</div>';
    return;
  }
  el.innerHTML = `<table>
    <tr><th>名称</th><th>ID</th><th>IP地址</th><th>端口</th><th>用户</th><th>位置</th><th>状态</th><th>操作</th></tr>
    ${servers.map(s => `<tr>
      <td><strong>${escHtml(s.name)}</strong></td>
      <td style="color:#999;font-size:11px">${escHtml(s.id)}</td>
      <td><code>${escHtml(s.host)}</code></td>
      <td>${s.port}</td>
      <td>${escHtml(s.ssh_user)}</td>
      <td style="color:#666">${escHtml(s.location||'-')}</td>
      <td><span class="status-dot status-${s.status||'offline'}"></span>${s.status==='online'?'在线':'离线'}</td>
      <td style="white-space:nowrap">
        <button class="btn btn-sm" onclick="editServer('${s.id}')">✏️</button>
        <button class="btn btn-sm btn-danger" onclick="deleteServer('${s.id}')">🗑</button>
      </td>
    </tr>`).join('')}
  </table>`;
}

function showAddModal() {
  editingId = null;
  document.getElementById('modal-title').textContent = '新增服务器';
  ['f-id','f-name','f-host','f-port','f-ssh-user','f-location','f-remark'].forEach(id => document.getElementById(id).value = '');
  document.getElementById('f-port').value = '22';
  document.getElementById('f-ssh-user').value = 'root';
  document.getElementById('modal').style.display = 'flex';
}

function editServer(id) {
  editingId = id;
  const s = servers.find(x => x.id === id);
  if (!s) return;
  document.getElementById('modal-title').textContent = '编辑 - ' + s.name;
  document.getElementById('f-id').value = s.id; document.getElementById('f-id').disabled = true;
  document.getElementById('f-name').value = s.name;
  document.getElementById('f-host').value = s.host;
  document.getElementById('f-port').value = s.port;
  document.getElementById('f-ssh-user').value = s.ssh_user;
  document.getElementById('f-location').value = s.location || '';
  document.getElementById('f-remark').value = s.remark || '';
  document.getElementById('modal').style.display = 'flex';
}

function closeModal() {
  document.getElementById('modal').style.display = 'none';
  document.getElementById('f-id').disabled = false;
}

async function saveServer() {
  const id = document.getElementById('f-id').value.trim();
  const name = document.getElementById('f-name').value.trim();
  const host = document.getElementById('f-host').value.trim();
  const port = parseInt(document.getElementById('f-port').value) || 22;
  const sshUser = document.getElementById('f-ssh-user').value.trim() || 'root';
  const location = document.getElementById('f-location').value.trim();
  const remark = document.getElementById('f-remark').value.trim();
  if (!id || !name || !host) { showToast('ID、名称、IP 不能为空', 'error'); return; }

  const btn = document.getElementById('save-btn');
  btn.disabled = true; btn.textContent = '保存中...';
  try {
    const body = {id, name, host, port, ssh_user: sshUser, location, remark};
    if (editingId) {
      await fetch('/api/servers/' + editingId, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    } else {
      const r = await fetch('/api/servers', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
      const d = await r.json();
      if (d.code !== 0) { showToast(d.message, 'error'); btn.disabled=false; btn.textContent='保存'; return; }
    }
    showToast(editingId ? '✅ 已更新' : '✅ 添加成功', 'success');
    closeModal();
    await loadServers();
  } catch(e) {
    showToast('操作失败: ' + e.message, 'error');
  }
  btn.disabled = false; btn.textContent = '保存';
}

async function deleteServer(id) {
  if (!confirm('确定删除服务器「' + id + '」？')) return;
  try {
    await fetch('/api/servers/' + id, {method:'DELETE'});
    showToast('已删除', 'success');
    await loadServers();
  } catch(e) {
    showToast('删除失败: ' + e.message, 'error');
  }
}

function showToast(msg, type) {
  const t = document.createElement('div');
  t.className = 'toast ' + type;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3000);
}

function escHtml(s) { return String(s).replace(/[<>&]/g,m=>{'<':'&lt;','>':'&gt;','&':'&amp;'}[m]); }
loadServers();
</script>
</body>
</html>"""

def get_servers_html() -> str:
    return _SERVERS_HTML
