"""Web 管理界面 HTML 模板"""
from __future__ import annotations

_WEB_HTML = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>小希-Mesh 管理</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}
body{background:#f0f2f5;color:#333;min-height:100vh}
header{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:1.5rem 2rem;text-align:center}
header h1{font-size:1.8rem;margin-bottom:0.3rem}
header p{opacity:.9;font-size:0.9rem}
#status-bar{background:#fff;border-bottom:1px solid #ddd;padding:0.7rem 2rem;display:flex;gap:1rem;flex-wrap:wrap;align-items:center}
#status-bar .stat{background:#f8f9fa;border-radius:6px;padding:0.3rem 0.8rem;font-size:0.85rem}
#status-bar .stat strong{color:#667eea}
nav{background:#fff;border-bottom:1px solid #ddd;display:flex;padding:0 2rem;gap:1rem;flex-wrap:wrap}
nav a{padding:0.8rem 0.2rem;text-decoration:none;color:#666;font-size:0.9rem;border-bottom:2px solid transparent;cursor:pointer}
nav a.active,nav a:hover{color:#667eea;border-bottom-color:#667eea}
main{padding:1.5rem 2rem;max-width:1400px;margin:0 auto}
.page{display:none}
.page.active{display:block}
.card{background:#fff;border-radius:10px;box-shadow:0 2px 8px rgba(0,0,0,0.08);padding:1.5rem;margin-bottom:1.5rem}
.card h2{font-size:1.2rem;margin-bottom:1rem;color:#444}
table{width:100%;border-collapse:collapse;font-size:0.9rem}
th,td{padding:0.7rem 0.8rem;text-align:left;border-bottom:1px solid #eee}
th{background:#f8f9fa;font-weight:600;color:#666;position:sticky;top:0}
tr:hover{background:#f5f7ff}
.tag{display:inline-block;padding:0.15rem 0.5rem;border-radius:10px;font-size:0.75rem;font-weight:600}
.tag.online{background:#d4edda;color:#155724}
.tag.offline{background:#f8d7da;color:#721c24}
.tag.busy{background:#fff3cd;color:#856404}
.tag.admin{background:#cce5ff;color:#004085}
.tag.agent{background:#e2e3e5;color:#383d41}
pre{background:#f5f5f5;padding:1rem;border-radius:6px;overflow-x:auto;font-size:0.8rem;max-height:400px;overflow-y:auto}
.btn{display:inline-block;padding:0.5rem 1.2rem;border:none;border-radius:6px;cursor:pointer;font-size:0.85rem;font-weight:600;text-decoration:none}
.btn-primary{background:#667eea;color:#fff}
.btn-primary:hover{background:#5a6fd6}
.btn-danger{background:#e74c3c;color:#fff}
.btn-danger:hover{background:#c0392b}
.btn-sm{padding:0.3rem 0.8rem;font-size:0.8rem}
input,select,textarea{padding:0.5rem;border:1px solid #ddd;border-radius:6px;font-size:0.85rem;width:100%}
.form-group{margin-bottom:1rem}
.form-group label{display:block;margin-bottom:0.3rem;font-size:0.85rem;color:#555;font-weight:600}
.form-row{display:flex;gap:1rem;flex-wrap:wrap}
.form-row>*{flex:1;min-width:200px}
.mt-1{margin-top:1rem}
.mb-1{margin-bottom:1rem}
.loading{text-align:center;padding:2rem;color:#999}
.error{color:#e74c3c;padding:1rem;background:#fdf0ef;border-radius:6px;margin:1rem 0}
.success{color:#155724;padding:1rem;background:#d4edda;border-radius:6px;margin:1rem 0}
.flex{display:flex;gap:1rem;align-items:center;flex-wrap:wrap}
.justify-between{justify-content:space-between}
.text-center{text-align:center}
@media(max-width:768px){header{padding:1rem}main{padding:1rem}nav{padding:0 1rem}table{font-size:0.8rem}th,td{padding:0.5rem}}
</style>
</head>
<body>
<header><h1>小希-Mesh</h1><p>智能体实时消息与服务管理平台</p></header>
<div id="status-bar"><span class="stat">在线: <strong id="online-count">0</strong></span><span class="stat">智能体: <strong id="agent-count">0</strong></span><span class="stat" id="connection-status" style="color:#27ae60">已连接</span></div>
<nav id="nav"><a class="active" data-page="dashboard">仪表盘</a><a data-page="agents">智能体</a><a data-page="tasks">任务</a><a data-page="messages">消息</a><a data-page="audit">审计日志</a><a data-page="stats">统计</a><a data-page="register">注册</a><a data-page="send">发送消息</a><a data-page="brain">智能管理员</a></nav>
<main id="main"><div id="page-dashboard" class="page active"><div class="card"><h2>系统概览</h2><div class="flex" style="gap:2rem;flex-wrap:wrap"><div style="text-align:center;padding:1rem 2rem;background:#f8f9fa;border-radius:10px;flex:1;min-width:150px"><div style="font-size:2rem;font-weight:700;color:#667eea" id="d-online">0</div><div style="font-size:0.85rem;color:#888;margin-top:0.3rem">在线智能体</div></div><div style="text-align:center;padding:1rem 2rem;background:#f8f9fa;border-radius:10px;flex:1;min-width:150px"><div style="font-size:2rem;font-weight:700;color:#764ba2" id="d-total">0</div><div style="font-size:0.85rem;color:#888;margin-top:0.3rem">注册智能体</div></div><div style="text-align:center;padding:1rem 2rem;background:#f8f9fa;border-radius:10px;flex:1;min-width:150px"><div style="font-size:2rem;font-weight:700;color:#e74c3c" id="d-msg">0</div><div style="font-size:0.85rem;color:#888;margin-top:0.3rem">今日消息</div></div><div style="text-align:center;padding:1rem 2rem;background:#f8f9fa;border-radius:10px;flex:1;min-width:150px"><div style="font-size:2rem;font-weight:700;color:#27ae60" id="d-task">0</div><div style="font-size:0.85rem;color:#888;margin-top:0.3rem">活跃任务</div></div></div></div><div class="card"><h2>最近活动</h2><div id="d-recent">加载中...</div></div></div>
<div id="page-agents" class="page"><div class="card"><div class="flex justify-between mb-1"><h2>智能体列表</h2></div><table><thead><tr><th>ID</th><th>名称</th><th>角色</th><th>状态</th><th>能力</th><th>最后在线</th><th>操作</th></tr></thead><tbody id="agents-table"><tr><td colspan="7" class="text-center loading">加载中...</td></tr></tbody></table></div><div class="card"><h2>能力矩阵</h2><div id="capability-matrix">加载中...</div></div></div>
<div id="page-tasks" class="page"><div class="card"><div class="flex justify-between mb-1"><h2>任务列表</h2><div><select id="task-filter" onchange="loadTasks()"><option value="">全部</option><option value="pending">待处理</option><option value="assigned">已分配</option><option value="in_progress">进行中</option><option value="completed">已完成</option><option value="failed">失败</option></select></div></div><table><thead><tr><th>ID</th><th>描述</th><th>分配人</th><th>执行人</th><th>状态</th><th>优先级</th><th>创建时间</th></tr></thead><tbody id="tasks-table"><tr><td colspan="7" class="text-center loading">加载中...</td></tr></tbody></table></div></div>
<div id="page-messages" class="page"><div class="card"><div class="flex justify-between mb-1"><h2>消息历史</h2></div><table><thead><tr><th>ID</th><th>发送方</th><th>接收方</th><th>类型</th><th>内容</th><th>时间</th><th>状态</th></tr></thead><tbody id="messages-table"><tr><td colspan="7" class="text-center loading">加载中...</td></tr></tbody></table></div></div>
<div id="page-audit" class="page"><div class="card"><div class="flex justify-between mb-1"><h2>审计日志</h2></div><table><thead><tr><th>时间</th><th>智能体</th><th>操作</th><th>详情</th></tr></thead><tbody id="audit-table"><tr><td colspan="4" class="text-center loading">加载中...</td></tr></tbody></table></div></div>
<div id="page-stats" class="page"><div class="card"><h2>系统统计</h2><div id="stats-content">加载中...</div></div><div class="card"><h2>消息统计 (近24小时)</h2><div id="msg-stats">加载中...</div></div></div>
<div id="page-register" class="page"><div class="card" style="max-width:500px"><h2>注册新智能体</h2><div class="form-group"><label>智能体ID</label><input id="reg-id" placeholder="例如: xiao-qing"/></div><div class="form-group"><label>名称</label><input id="reg-name" placeholder="小青"/></div><div class="form-group"><label>角色</label><select id="reg-role"><option value="agent">智能体 (Agent)</option><option value="admin">管理员 (Admin)</option></select></div><div class="form-group"><label>能力 (逗号分隔)</label><input id="reg-caps" placeholder="chat, code, search"/></div><div class="form-group"><label>专长 (逗号分隔)</label><input id="reg-spec" placeholder="自然语言处理, 代码生成"/></div><button class="btn btn-primary" onclick="registerAgent()">注册</button><div id="reg-result" class="mt-1"></div></div></div>
<div id="page-send" class="page"><div class="card" style="max-width:500px"><h2>发送消息</h2><div class="form-group"><label>接收方</label><select id="send-to"><option value="broadcast">广播 (所有智能体)</option></select></div><div class="form-group"><label>类型</label><select id="send-type"><option value="text">文本</option><option value="command">命令</option><option value="notice">通知</option></select></div><div class="form-group"><label>内容</label><textarea id="send-content" rows="4" placeholder="输入消息内容..."></textarea></div><div class="form-group"><label>优先级</label><select id="send-priority"><option value="normal">普通</option><option value="high">高</option><option value="low">低</option></select></div><button class="btn btn-primary" onclick="sendMessage()">发送</button><div id="send-result" class="mt-1"></div></div></div>
<div id="page-brain" class="page"><div class="card" style="max-width:600px"><h2>智能管理员配置</h2>
<div class="form-group"><label><input type="checkbox" id="brain-enabled" onchange="toggleEnabled()" style="width:auto;margin-right:0.5rem" />启用智能管理员</label></div>
<div class="form-group"><label>供应商</label><select id="brain-provider"><option value="mimo">Mimo</option><option value="dreamfield">DreamField</option><option value="deepseek">DeepSeek</option><option value="custom">自定义</option></select></div>
<div id="brain-custom-provider-group" class="form-group" style="display:none"><label>自定义供应商地址</label><input id="brain-custom-provider" placeholder="例如: myapi.example.com" /></div>
<div class="form-group"><label>模型名称</label><input id="brain-model" placeholder="例如: gpt-4o" /></div>
<div class="form-group"><label>API Key 文件路径</label><input id="brain-api-key-file" placeholder="/path/to/apikey.txt" /></div>
<div class="form-group"><label>API Key</label><input id="brain-api-key" type="password" placeholder="输入新的 API Key 以覆盖" /><small style="color:#999;display:block;margin-top:0.3rem">留空则保持现有 Key 不变</small></div>
<div class="form-group"><label>系统提示词</label><textarea id="brain-system-prompt" rows="8" placeholder="输入系统提示词..."></textarea></div>
<div class="flex" style="gap:1rem"><button class="btn btn-primary" onclick="saveBrainConfig()">保存配置</button><button class="btn" style="background:#764ba2;color:#fff" onclick="testBrain()">测试连接</button></div>
<div id="brain-result" class="mt-1"></div>
</div></div></main>
<script>
const API_BASE='';let token=localStorage.getItem('token'),ws=null,agentId=null
function showPage(id){document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));document.getElementById('page-'+id).classList.add('active');document.querySelectorAll('#nav a').forEach(a=>{a.classList.toggle('active',a.dataset.page===id)})}
document.querySelectorAll('#nav a').forEach(a=>a.onclick=()=>{showPage(a.dataset.page);switch(a.dataset.page){case'dashboard':loadDashboard();break;case'agents':loadAgents();break;case'tasks':loadTasks();break;case'messages':loadMessages();break;case'audit':loadAudit();break;case'stats':loadStats();break;case'brain':loadBrainConfig();break}})
async function api(path,opts={}){const h=opts.headers||{};if(token)h['Authorization']='Bearer '+token;const r=await fetch(API_BASE+path,{...opts,headers:h});if(r.status===401){token=null;localStorage.removeItem('token');showToast('请先登录');return null}if(!r.ok){const e=await r.json().catch(()=>({}));throw new Error(e.message||'请求失败')}return r.json()}
async function loadDashboard(){try{const d=await api('/api/stats/overview');if(!d)return;document.getElementById('d-online').textContent=d.data?.online_agents||0;document.getElementById('d-total').textContent=d.data?.total_agents||0;document.getElementById('d-msg').textContent=d.data?.today_messages||0;document.getElementById('d-task').textContent=d.data?.active_tasks||0}catch(e){document.getElementById('d-online').textContent='?'}try{const r=await api('/api/agents?limit=5');if(r){const t=document.getElementById('d-recent');t.innerHTML=r.data?.map(a=>'<div style="padding:0.3rem 0;border-bottom:1px solid #f0f0f0;font-size:0.85rem"><span class="tag '+(a.online?'online':'offline')+'">'+(a.online?'在线':'离线')+'</span> <strong>'+a.name+'</strong> ('+a.agent_id+') <span style="color:#999;float:right">能力: '+(a.capabilities?.length||0)+'</span></div>').join('')||'暂无数据'}}catch(e){}}loadDashboard()
async function loadAgents(){try{const r=await api('/api/agents');if(!r)return;const t=document.getElementById('agents-table');t.innerHTML=r.data?.map(a=>'<tr><td>'+a.agent_id+'</td><td><strong>'+a.name+'</strong></td><td><span class="tag '+(a.role==='admin'?'admin':'agent')+'">'+(a.role||'agent')+'</span></td><td><span class="tag '+(a.online?'online':'offline')+'">'+(a.online?'在线':'离线')+'</span></td><td>'+(a.capabilities?.join(', ')||'-')+'</td><td style="font-size:0.8rem;color:#999">'+(a.last_seen?new Date(a.last_seen).toLocaleString():'-')+'</td><td><button class="btn btn-sm btn-danger" onclick="deleteAgent(\''+a.agent_id+'\')">删除</button></td></tr>').join('')||'<tr><td colspan="7" class="text-center">暂无智能体</td></tr>'}catch(e){document.getElementById('agents-table').innerHTML='<tr><td colspan="7" class="text-center error">加载失败</td></tr>'}try{const r=await api('/api/capabilities/matrix');if(r){const m=document.getElementById('capability-matrix');m.innerHTML='<pre>'+JSON.stringify(r.data||r,null,2)+'</pre>'}}catch(e){}}
async function loadTasks(){try{const f=document.getElementById('task-filter').value;const r=await api('/api/tasks'+(f?'?status='+f:''));if(!r)return;const t=document.getElementById('tasks-table');t.innerHTML=r.data?.map(task=>'<tr><td style="font-size:0.8rem">'+(task.id?.substring(0,8)||'')+'</td><td>'+(task.description?.substring(0,40)||'-')+'</td><td>'+task.assigned_by+'</td><td>'+task.assigned_to+'</td><td><span class="tag '+(task.status==='completed'?'online':task.status==='failed'?'offline':'busy')+'">'+task.status+'</span></td><td>'+task.priority+'</td><td style="font-size:0.8rem;color:#999">'+(task.created_at?new Date(task.created_at).toLocaleString():'-')+'</td></tr>').join('')||'<tr><td colspan="7" class="text-center">暂无任务</td></tr>'}catch(e){document.getElementById('tasks-table').innerHTML='<tr><td colspan="7" class="text-center error">加载失败</td></tr>'}}
async function loadMessages(){try{const r=await api('/api/messages?limit=50');if(!r)return;const t=document.getElementById('messages-table');t.innerHTML=r.data?.map(m=>'<tr><td style="font-size:0.8rem">'+(m.id?.substring(0,8)||'')+'</td><td>'+m.from_id+'</td><td>'+m.to_id+'</td><td>'+m.type+'</td><td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'+(m.content?.substring(0,50)||'')+'</td><td style="font-size:0.8rem;color:#999">'+(m.created_at?new Date(m.created_at).toLocaleString():'-')+'</td><td>'+((m.delivered)?'<span class="tag online">已投递</span>':'<span class="tag busy">待投递</span>')+'</td></tr>').join('')||'<tr><td colspan="7" class="text-center">暂无消息</td></tr>'}catch(e){document.getElementById('messages-table').innerHTML='<tr><td colspan="7" class="text-center error">加载失败</td></tr>'}}
async function loadAudit(){try{const r=await api('/api/audit?limit=100');if(!r)return;const t=document.getElementById('audit-table');t.innerHTML=r.data?.map(a=>'<tr><td style="font-size:0.8rem;color:#999">'+(a.timestamp?new Date(a.timestamp).toLocaleString():'-')+'</td><td>'+a.agent_id+'</td><td>'+a.action+'</td><td style="font-size:0.8rem;color:#666;max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'+(a.detail||'')+'</td></tr>').join('')||'<tr><td colspan="4" class="text-center">暂无审计日志</td></tr>'}catch(e){document.getElementById('audit-table').innerHTML='<tr><td colspan="4" class="text-center error">加载失败</td></tr>'}}
async function loadStats(){try{const r=await api('/api/stats/overview');if(!r)return;document.getElementById('stats-content').innerHTML='<pre>'+JSON.stringify(r.data||r,null,2)+'</pre>'}catch(e){document.getElementById('stats-content').innerHTML='<div class="error">加载失败</div>'}try{const r=await api('/api/stats/messages');if(r){document.getElementById('msg-stats').innerHTML='<pre>'+JSON.stringify(r.data||r,null,2)+'</pre>'}}catch(e){}}
async function registerAgent(){const id=document.getElementById('reg-id').value.trim(),name=document.getElementById('reg-name').value.trim(),role=document.getElementById('reg-role').value,caps=document.getElementById('reg-caps').value.split(',').map(s=>s.trim()).filter(Boolean),specs=document.getElementById('reg-spec').value.split(',').map(s=>s.trim()).filter(Boolean);if(!id||!name){document.getElementById('reg-result').innerHTML='<div class="error">请填写ID和名称</div>';return}try{const r=await api('/api/agents/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({agent_id:id,name:name,role:role,capabilities:caps,specialties:specs})});document.getElementById('reg-result').innerHTML='<div class="success">注册成功！Token: '+(r.data?.token||'')+'</div>';document.getElementById('reg-id').value='';document.getElementById('reg-name').value='';loadAgents()}catch(e){document.getElementById('reg-result').innerHTML='<div class="error">注册失败: '+e.message+'</div>'}}
async function sendMessage(){const to=document.getElementById('send-to').value,type=document.getElementById('send-type').value,content=document.getElementById('send-content').value,priority=document.getElementById('send-priority').value;if(!content){document.getElementById('send-result').innerHTML='<div class="error">请输入内容</div>';return}try{const r=await api('/api/messages/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({to_id:to,type:type,content:content,priority:priority})});document.getElementById('send-result').innerHTML='<div class="success">发送成功！ID: '+(r.data?.message_id||'')+'</div>';document.getElementById('send-content').value=''}catch(e){document.getElementById('send-result').innerHTML='<div class="error">发送失败: '+e.message+'</div>'}}
async function deleteAgent(id){if(!confirm('确定删除智能体 '+id+'？'))return;try{await api('/api/agents/'+id,{method:'DELETE'});loadAgents()}catch(e){alert('删除失败: '+e.message)}}
function showToast(msg){const d=document.createElement('div');d.style.cssText='position:fixed;bottom:20px;right:20px;background:#333;color:#fff;padding:1rem 2rem;border-radius:8px;z-index:9999';d.textContent=msg;document.body.appendChild(d);setTimeout(()=>d.remove(),3000)}
function toggleEnabled(){document.getElementById('brain-enabled').checked?document.getElementById('brain-enabled').parentElement.style.color='inherit':document.getElementById('brain-enabled').parentElement.style.color='#999'}
document.getElementById('brain-provider').onchange=function(){document.getElementById('brain-custom-provider-group').style.display=this.value==='custom'?'block':'none'}
async function loadBrainConfig(){const r=document.getElementById('brain-result');r.innerHTML='<div class="loading">加载中...</div>';try{const d=await api('/api/brain/config');if(!d)return;document.getElementById('brain-enabled').checked=d.enabled;toggleEnabled();document.getElementById('brain-provider').value=d.provider;if(d.provider&&!['mimo','dreamfield','deepseek'].includes(d.provider)){document.getElementById('brain-provider').value='custom';document.getElementById('brain-custom-provider').value=d.provider;document.getElementById('brain-custom-provider-group').style.display='block'}document.getElementById('brain-model').value=d.model||'';document.getElementById('brain-api-key-file').value=d.api_key_file||'';document.getElementById('brain-api-key').value='';document.getElementById('brain-api-key').placeholder=d.api_key_masked?'当前: '+d.api_key_masked:'输入新的 API Key';document.getElementById('brain-system-prompt').value=d.system_prompt||'';r.innerHTML=''}catch(e){r.innerHTML='<div class="error">加载失败: '+e.message+'</div>'}}
async function saveBrainConfig(){const r=document.getElementById('brain-result');r.innerHTML='<div class="loading">保存中...</div>';const provider=document.getElementById('brain-provider').value==='custom'?document.getElementById('brain-custom-provider').value.trim():document.getElementById('brain-provider').value;const data={enabled:document.getElementById('brain-enabled').checked,provider:provider,model:document.getElementById('brain-model').value.trim(),api_key_file:document.getElementById('brain-api-key-file').value.trim(),api_key:document.getElementById('brain-api-key').value,system_prompt:document.getElementById('brain-system-prompt').value};try{await api('/api/brain/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});r.innerHTML='<div class="success">配置保存成功，已热重载！</div>';loadBrainConfig()}catch(e){r.innerHTML='<div class="error">保存失败: '+e.message+'</div>'}}
async function testBrain(){const r=document.getElementById('brain-result');r.innerHTML='<div class="loading">测试中，正在调用 LLM...</div>';try{const d=await api('/api/brain/test',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:'你好，这是一个连接测试消息'})});if(!d)return;const result=d.result;let html='<div class="success">测试成功！</div><pre style="margin-top:0.5rem">'+JSON.stringify(result,null,2)+'</pre>';r.innerHTML=html}catch(e){r.innerHTML='<div class="error">测试失败: '+e.message+'</div>'}}
</script>
</body>
</html>'''

def get_web_html() -> str:
    return _WEB_HTML
