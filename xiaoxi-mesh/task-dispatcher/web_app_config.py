"""APP配置管理页面 + API"""
import json
import os
from datetime import datetime

# APP配置存储路径
APP_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "data", "app_config.json")

# 默认配置
DEFAULT_APP_CONFIG = {
    "version": "v0.2.0",
    "version_date": "2026-06-28",
    "app_name": "小希",
    "features": {
        "voice_recognition": True,
        "dark_mode": True,
        "user_management": True,
        "work_groups": True,
        "notification": True,
        "contact_search": True,
        "agent_register": True,
    },
    "work_groups": [
        {
            "id": "g1",
            "name": "核心开发",
            "icon": "💻",
            "agents": ["xiaolan", "xiaoqing"],
            "description": "系统开发和维护"
        },
        {
            "id": "g2",
            "name": "运维监控",
            "icon": "📊",
            "agents": ["xiaolan", "xiaobai"],
            "description": "服务器运维和监控"
        },
        {
            "id": "g3",
            "name": "内容创作",
            "icon": "✍️",
            "agents": ["xiaoqing", "xiaohei"],
            "description": "内容生成和知识管理"
        }
    ],
    "ui": {
        "theme": "dark",
        "logo_text": "希",
        "primary_color": "#6366f1",
        "show_online_status": True,
        "message_preview_length": 50,
    },
    "update_url": "https://mesh.xixisz.top/changelog.html",
}


def load_app_config() -> dict:
    """加载APP配置"""
    if os.path.exists(APP_CONFIG_PATH):
        try:
            with open(APP_CONFIG_PATH, "r") as f:
                saved = json.load(f)
            # 合并默认值（新增字段自动补全）
            merged = DEFAULT_APP_CONFIG.copy()
            merged.update(saved)
            if "features" in saved:
                merged["features"] = {**DEFAULT_APP_CONFIG["features"], **saved["features"]}
            if "ui" in saved:
                merged["ui"] = {**DEFAULT_APP_CONFIG["ui"], **saved["ui"]}
            return merged
        except Exception:
            pass
    return DEFAULT_APP_CONFIG.copy()


def save_app_config(config: dict):
    """保存APP配置"""
    os.makedirs(os.path.dirname(APP_CONFIG_PATH), exist_ok=True)
    with open(APP_CONFIG_PATH, "w") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_app_config_html() -> str:
    """返回APP配置管理页面"""
    return _APP_CONFIG_HTML


# ==================== HTML模板 ====================

_APP_CONFIG_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>APP 配置管理</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Noto Sans SC',sans-serif;background:#f0f2f5;color:#333;padding:20px}
.container{max-width:800px;margin:0 auto}
h1{font-size:20px;margin-bottom:4px}
.subtitle{color:#999;font-size:13px;margin-bottom:20px}
.card{background:#fff;border-radius:10px;padding:20px;margin-bottom:16px;box-shadow:0 1px 4px rgba(0,0,0,.06)}
.card h2{font-size:15px;font-weight:600;margin-bottom:14px;padding-bottom:10px;border-bottom:1px solid #eee}
.form-group{margin-bottom:14px}
.form-group label{display:block;font-size:12px;font-weight:600;color:#555;margin-bottom:4px}
.form-group input,.form-group textarea,.form-group select{width:100%;padding:8px 12px;border:1px solid #ddd;border-radius:6px;font-size:13px;outline:none;transition:border .15s}
.form-group input:focus,.form-group textarea:focus{border-color:#3498db}
.form-group textarea{min-height:60px;resize:vertical;line-height:1.5}
.form-group .hint{font-size:11px;color:#999;margin-top:3px}
.form-row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.btn-row{display:flex;gap:10px;margin-top:20px;align-items:center}
.btn{background:#3498db;color:#fff;border:none;padding:10px 24px;border-radius:8px;font-size:14px;cursor:pointer;transition:background .15s}
.btn:hover{background:#2980b9}
.btn:disabled{background:#bbb;cursor:not-allowed}
.btn-danger{background:#e74c3c}
.btn-danger:hover{background:#c0392b}
.btn-sm{padding:6px 14px;font-size:12px}
.toast{position:fixed;top:20px;right:20px;padding:12px 20px;border-radius:8px;color:#fff;font-size:13px;z-index:999;animation:fadeIn .3s}
.toast.success{background:#27ae60}
.toast.error{background:#e74c3c}
@keyframes fadeIn{from{opacity:0;transform:translateY(-10px)}to{opacity:1;transform:translateY(0)}}
.link-bar{text-align:right;margin-bottom:16px}
.link-bar a{color:#3498db;text-decoration:none;font-size:13px}
.link-bar a:hover{text-decoration:underline}
.feature-toggle{display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid #f0f0f0}
.feature-toggle:last-child{border:none}
.feature-name{font-size:13px;font-weight:500}
.feature-desc{font-size:11px;color:#999}
.switch{position:relative;width:40px;height:22px}
.switch input{opacity:0;width:0;height:0}
.slider{position:absolute;cursor:pointer;top:0;left:0;right:0;bottom:0;background:#ccc;transition:.3s;border-radius:22px}
.slider:before{position:absolute;content:"";height:16px;width:16px;left:3px;bottom:3px;background:#fff;transition:.3s;border-radius:50%}
input:checked+.slider{background:#3498db}
input:checked+.slider:before{transform:translateX(18px)}
.group-card{background:#f8f9fa;border:1px solid #e9ecef;border-radius:8px;padding:12px;margin-bottom:10px;display:flex;align-items:center;gap:12px}
.group-card .group-icon{font-size:24px}
.group-card .group-info{flex:1}
.group-card .group-name{font-size:14px;font-weight:600}
.group-card .group-desc{font-size:12px;color:#666}
.group-card .group-agents{font-size:11px;color:#999;margin-top:2px}
.group-card .group-actions{display:flex;gap:6px}
.version-preview{background:#f0f7ff;border:1px solid #b3d9ff;border-radius:8px;padding:12px;margin-top:10px;font-size:13px;color:#0066cc}
</style>
</head>
<body>
<div class="container">
  <div class="link-bar">
    <a href="/chat">← 聊天</a>
    <span style="margin:0 8px;color:#ddd">|</span>
    <a href="/config">⚙️ 调度配置</a>
    <span style="margin:0 8px;color:#ddd">|</span>
    <a href="/agents">🤖 智能体</a>
    <span style="margin:0 8px;color:#ddd">|</span>
    <a href="/admin" target="_blank">📊 调度面板</a>
  </div>
  <h1>📱 APP 配置管理</h1>
  <div class="subtitle">修改后保存，APP 下次启动自动同步</div>

  <!-- 版本信息 -->
  <div class="card">
    <h2>📦 版本信息</h2>
    <div class="form-row">
      <div class="form-group">
        <label>当前版本号</label>
        <input id="version" placeholder="v0.2.0" />
        <div class="hint">APP显示的版本号</div>
      </div>
      <div class="form-group">
        <label>发布日期</label>
        <input id="version_date" placeholder="2026-06-28" />
      </div>
    </div>
    <div class="form-group">
      <label>应用名称</label>
      <input id="app_name" placeholder="小希" />
    </div>
    <div class="form-group">
      <label>更新日志链接</label>
      <input id="update_url" placeholder="https://mesh.xixisz.top/changelog.html" />
    </div>
    <div class="version-preview" id="version-preview"></div>
  </div>

  <!-- 功能开关 -->
  <div class="card">
    <h2>🔧 功能开关</h2>
    <div id="features-list"></div>
  </div>

  <!-- 工作组管理 -->
  <div class="card">
    <h2>👥 工作组管理</h2>
    <div id="groups-list"></div>
    <div class="btn-row">
      <button class="btn btn-sm" onclick="addGroup()">+ 添加工作组</button>
    </div>
  </div>

  <!-- UI配置 -->
  <div class="card">
    <h2>🎨 界面配置</h2>
    <div class="form-row">
      <div class="form-group">
        <label>Logo 文字</label>
        <input id="logo_text" placeholder="希" />
      </div>
      <div class="form-group">
        <label>主题色</label>
        <input id="primary_color" type="color" value="#6366f1" />
      </div>
    </div>
    <div class="form-group">
      <label>
        <input type="checkbox" id="show_online_status" checked /> 显示在线状态
      </label>
    </div>
    <div class="form-group">
      <label>消息预览长度</label>
      <input id="message_preview_length" type="number" value="50" />
    </div>
  </div>

  <div class="btn-row">
    <button class="btn" onclick="saveConfig()">💾 保存配置</button>
    <button class="btn" style="background:#27ae60" onclick="previewConfig()">👁️ 预览API返回</button>
  </div>
</div>

<script>
const FEATURES = {
  voice_recognition: {name: '语音识别', desc: '流式语音转文字'},
  dark_mode: {name: '暗色模式', desc: '一键切换深色主题'},
  user_management: {name: '用户管理', desc: '管理员查看/修改用户角色'},
  work_groups: {name: '工作组', desc: '多智能体协作分组'},
  notification: {name: '系统通知', desc: '状态栏通知+角标'},
  contact_search: {name: '联系人搜索', desc: '按名称/ID实时过滤'},
  agent_register: {name: 'APP内注册智能体', desc: '联系人页直接注册'},
};

let config = {};

async function loadConfig() {
  try {
    const r = await fetch('/api/app-config');
    config = await r.json();
  } catch(e) {
    config = {};
  }
  
  document.getElementById('version').value = config.version || 'v0.2.0';
  document.getElementById('version_date').value = config.version_date || '2026-06-28';
  document.getElementById('app_name').value = config.app_name || '小希';
  document.getElementById('update_url').value = config.update_url || '';
  document.getElementById('logo_text').value = (config.ui || {}).logo_text || '希';
  document.getElementById('primary_color').value = (config.ui || {}).primary_color || '#6366f1';
  document.getElementById('show_online_status').checked = (config.ui || {}).show_online_status !== false;
  document.getElementById('message_preview_length').value = (config.ui || {}).message_preview_length || 50;
  
  renderFeatures();
  renderGroups();
  updatePreview();
  
  ['version','version_date','app_name'].forEach(id => {
    document.getElementById(id).addEventListener('input', updatePreview);
  });
}

function renderFeatures() {
  const el = document.getElementById('features-list');
  const features = config.features || {};
  el.innerHTML = Object.entries(FEATURES).map(([key, info]) => `
    <div class="feature-toggle">
      <div>
        <div class="feature-name">${info.name}</div>
        <div class="feature-desc">${info.desc}</div>
      </div>
      <label class="switch">
        <input type="checkbox" data-feature="${key}" ${features[key] !== false ? 'checked' : ''} />
        <span class="slider"></span>
      </label>
    </div>
  `).join('');
}

function renderGroups() {
  const el = document.getElementById('groups-list');
  const groups = config.work_groups || [];
  el.innerHTML = groups.map((g, i) => `
    <div class="group-card">
      <div class="group-icon">${g.icon || '📁'}</div>
      <div class="group-info">
        <div class="group-name">${g.name}</div>
        <div class="group-desc">${g.description || ''}</div>
        <div class="group-agents">智能体: ${(g.agents || []).join(', ')}</div>
      </div>
      <div class="group-actions">
        <button class="btn btn-sm" onclick="editGroup(${i})">编辑</button>
        <button class="btn btn-sm btn-danger" onclick="removeGroup(${i})">删除</button>
      </div>
    </div>
  `).join('') || '<div style="color:#999;font-size:13px;padding:12px">暂无工作组</div>';
}

function addGroup() {
  const name = prompt('工作组名称：');
  if (!name) return;
  const icon = prompt('图标（emoji）：', '📁') || '📁';
  const desc = prompt('描述：', '') || '';
  if (!config.work_groups) config.work_groups = [];
  config.work_groups.push({
    id: 'g' + Date.now(),
    name, icon, description: desc,
    agents: []
  });
  renderGroups();
}

function editGroup(idx) {
  const g = config.work_groups[idx];
  const name = prompt('工作组名称：', g.name);
  if (!name) return;
  g.name = name;
  g.icon = prompt('图标：', g.icon) || g.icon;
  g.description = prompt('描述：', g.description) || g.description;
  const agentsStr = prompt('智能体（逗号分隔）：', (g.agents || []).join(', '));
  if (agentsStr !== null) {
    g.agents = agentsStr.split(',').map(s => s.trim()).filter(Boolean);
  }
  renderGroups();
}

function removeGroup(idx) {
  if (!confirm('确定删除此工作组？')) return;
  config.work_groups.splice(idx, 1);
  renderGroups();
}

function updatePreview() {
  const v = document.getElementById('version').value;
  const d = document.getElementById('version_date').value;
  const n = document.getElementById('app_name').value;
  document.getElementById('version-preview').innerHTML = 
    `<strong>APP显示预览：</strong> ${n} ${v} · ${d}`;
}

async function saveConfig() {
  const features = {};
  document.querySelectorAll('[data-feature]').forEach(el => {
    features[el.dataset.feature] = el.checked;
  });
  
  config.version = document.getElementById('version').value;
  config.version_date = document.getElementById('version_date').value;
  config.app_name = document.getElementById('app_name').value;
  config.update_url = document.getElementById('update_url').value;
  config.features = features;
  config.ui = {
    logo_text: document.getElementById('logo_text').value,
    primary_color: document.getElementById('primary_color').value,
    show_online_status: document.getElementById('show_online_status').checked,
    message_preview_length: parseInt(document.getElementById('message_preview_length').value) || 50,
  };
  
  try {
    const r = await fetch('/api/app-config', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(config)
    });
    const result = await r.json();
    if (result.success) {
      showToast('配置已保存 ✓', 'success');
    } else {
      showToast('保存失败: ' + (result.error || ''), 'error');
    }
  } catch(e) {
    showToast('保存失败: ' + e.message, 'error');
  }
}

async function previewConfig() {
  try {
    const r = await fetch('/api/app-config');
    const data = await r.json();
    const w = window.open('', '_blank');
    w.document.write('<pre>' + JSON.stringify(data, null, 2) + '</pre>');
  } catch(e) {
    showToast('预览失败', 'error');
  }
}

function showToast(msg, type) {
  const t = document.createElement('div');
  t.className = 'toast ' + type;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3000);
}

loadConfig();
</script>
</body>
</html>"""
