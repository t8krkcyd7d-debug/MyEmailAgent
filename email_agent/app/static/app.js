const state = { folder: 'INBOX', filter: 'all', emails: [], selected: null, selectedAccount: null, account: 'all', detail: null, view: 'mail', accounts: [] };
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const titles = { INBOX: '收件箱', Sent: '已发送', Trash: '回收站' };

function esc(value = '') { const d = document.createElement('div'); d.textContent = value; return d.innerHTML; }
function senderName(from = '') { return from.replace(/<.*?>/g, '').replace(/^['"]|['"]$/g, '').trim() || from; }
function senderEmail(from = '') { return (from.match(/<([^>]+)>/) || [null, from])[1].trim(); }
function initials(from = '') { return senderName(from).slice(0, 1).toUpperCase() || '邮'; }
function shortDate(raw = '') { const d = new Date(raw); if (Number.isNaN(d.valueOf())) return raw || '时间未知'; return d.toLocaleString('zh-CN', {year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}); }
function toast(message, bad = false) { const el = $('#toast'); el.textContent = message; el.style.background = bad ? '#b73545' : '#20263a'; el.classList.remove('hidden'); clearTimeout(toast.timer); toast.timer = setTimeout(() => el.classList.add('hidden'), 2800); }
async function api(url, options = {}) { const res = await fetch(url, { headers: {'Content-Type':'application/json'}, ...options }); const data = await res.json().catch(() => ({})); if (!res.ok) throw new Error(data.detail || '暂时无法完成，请稍后再试'); return data; }

function filteredEmails() {
  if (state.filter === 'unread') return state.emails.filter(e => !e.is_read);
  if (state.filter === 'starred') return state.emails.filter(e => e.is_starred);
  if (state.filter === 'urgent') return state.emails.filter(e => e.urgency === '紧急');
  if (state.filter === 'normal') return state.emails.filter(e => e.urgency === '普通');
  if (state.filter === 'low') return state.emails.filter(e => e.urgency === '低');
  return state.emails;
}
function renderList() {
  const list = $('#mailList'), emails = filteredEmails();
  $('#inboxCount').textContent = state.folder === 'INBOX' ? state.emails.filter(e => !e.is_read).length || '' : '';
  if (!emails.length) { list.innerHTML = `<div class="empty-list"><div style="font-size:38px;margin-bottom:10px">✓</div><b>这里已经整理干净了</b><p>没有符合条件的邮件</p></div>`; return; }
  list.innerHTML = emails.map(e => `<button class="mail-item ${e.is_read?'':'unread'} ${state.selected===e.id&&state.selectedAccount===e.account?'selected':''}" data-id="${e.id}" data-account="${esc(e.account||'default')}">
    <span class="avatar">${esc(initials(e.from))}</span><span class="item-copy"><span class="sender-row"><span class="sender">${esc(senderName(e.from))}</span><span class="date">${esc(shortDate(e.date))}</span></span><span class="subject">${esc(e.subject || '（无主题）')}</span><span class="preview"><span class="priority ${e.urgency==='紧急'?'urgent':e.urgency==='普通'?'normal':'low'} ${e.priority_is_manual?'manual':e.priority_rule_applied?'rule':''}">${esc(e.urgency || '普通')} ${e.urgency==='紧急'?'!!!':e.urgency==='低'?'!':'!!'}</span> ${esc(e.account_label||'')}</span></span><span class="star ${e.is_starred?'on':''}">${e.is_starred?'★':'☆'}</span></button>`).join('');
  $$('.mail-item').forEach(el => el.onclick = () => openEmail(Number(el.dataset.id), el.dataset.account));
}
async function loadMailbox(query = '') {
  $('#mailList').innerHTML = '<div class="loading"><div class="spinner"></div>正在读取邮件…</div>';
  $('#folderTitle').textContent = titles[state.folder] || state.folder;
  $('#folderSubtitle').textContent = query ? `搜索“${query}”的结果` : '最新邮件排在最前面';
  try { const data = await api(`/api/mailbox?folder=${encodeURIComponent(state.folder)}&limit=80&q=${encodeURIComponent(query)}&account=${encodeURIComponent(state.account)}`); state.emails = data.emails; state.selected = null; renderList(); }
  catch (e) { $('#mailList').innerHTML = `<div class="error-state"><b>邮件暂时读不出来</b><p>${esc(e.message)}</p><button class="secondary" onclick="loadMailbox()">再试一次</button></div>`; }
}
async function openEmail(id, account) {
  state.selected = id; state.selectedAccount=account || state.account; renderList(); $('#detailPane').classList.add('open');
  $('#detailPane').innerHTML = '<div class="loading"><div class="spinner"></div>正在打开邮件…</div>';
  try { state.detail = await api(`/api/mailbox/${id}?folder=${encodeURIComponent(state.folder)}&account=${encodeURIComponent(state.selectedAccount)}`); renderDetail(); if (!state.detail.is_read) await action('read', false, id); }
  catch (e) { $('#detailPane').innerHTML = `<div class="error-state"><b>无法打开这封邮件</b><p>${esc(e.message)}</p></div>`; }
}
function renderDetail(analysis = null) {
  const e = state.detail;
  $('#detailPane').innerHTML = `<div class="detail"><div class="detail-toolbar"><button class="tool-button mobile-only" id="backButton">← 返回</button><div class="tool-group"><button class="tool-button" data-action="${e.is_read?'unread':'read'}">标为${e.is_read?'未读':'已读'}</button><button class="tool-button" data-action="${e.is_starred?'unstar':'star'}">${e.is_starred?'取消星标':'加星标'}</button></div><button class="tool-button danger" data-action="${state.folder==='Trash'?'delete':'trash'}">${state.folder==='Trash'?'永久删除':'移到回收站'}</button></div>
    <h2>${esc(e.subject || '（无主题）')}</h2><div class="sender-card"><span class="avatar">${esc(initials(e.from))}</span><div class="sender-info"><b>${esc(senderName(e.from))}</b><small>${esc(e.from)} · 发给 ${esc(e.to || '我')}</small></div><small>${esc(shortDate(e.date))}</small></div>
    <div style="display:flex;gap:10px;align-items:center;margin:18px 0"><label>紧急程度：<select class="priority-select" id="prioritySelect"><option value="紧急">紧急 !!!</option><option value="普通">普通 !!</option><option value="低">低 !</option></select></label><button class="primary" id="todoButton">＋ 设置提醒/待办</button></div>
    ${analysis ? aiMarkup(analysis) : `<div class="ai-card"><div class="ai-title"><b>✦ 智能助手</b></div><p>可以帮你用简单的话概括这封邮件，并准备一份回复。</p><div class="ai-actions"><button class="primary" id="analyzeButton">总结并起草回复</button></div></div>`}
    <div class="email-body">${esc(e.body)}</div><div class="reply-box"><button data-reply>↩ 回复</button><button data-forward>转发 ➜</button></div></div>`;
  $('#backButton')?.addEventListener('click', () => $('#detailPane').classList.remove('open'));
  $$('[data-action]').forEach(b => b.onclick = () => { if (b.dataset.action === 'delete' && !confirm('永久删除后无法恢复，确定继续吗？')) return; action(b.dataset.action); });
  $('#analyzeButton')?.addEventListener('click', analyzeCurrent);
  $('#prioritySelect').value = state.emails.find(x=>x.id===state.selected)?.urgency || '普通';
  $('#prioritySelect').onchange = e => changePriority(e.target.value);
  $('#todoButton').onclick = openTodo;
  $('[data-reply]')?.addEventListener('click', () => openCompose({to:senderEmail(e.from), subject:`回复：${e.subject}`}));
  $('[data-forward]')?.addEventListener('click', () => openCompose({subject:`转发：${e.subject}`, body:`\n\n---------- 原邮件 ----------\n发件人：${e.from}\n${e.body}`}));
  $('#useDraft')?.addEventListener('click', () => openCompose({to:senderEmail(e.from), subject:`回复：${e.subject}`, body:analysis.draft_reply}));
}
async function changePriority(urgency) { try { await api(`/api/mailbox/${state.selected}/priority`, {method:'PUT',body:JSON.stringify({folder:state.folder,urgency,account:state.selectedAccount})}); const item=state.emails.find(e=>e.id===state.selected&&e.account===state.selectedAccount); if(item){item.urgency=urgency;item.priority_is_manual=true;} renderList(); toast(`已改为“${urgency}”`); } catch(e){toast(e.message,true);} }

function openTodo() { const form=$('#todoForm'); form.reset(); form.title.value=`处理：${state.detail?.subject || '这封邮件'}`; $('#todoModal').classList.remove('hidden'); form.title.focus(); }
$$('[data-todo-close]').forEach(b=>b.onclick=()=>$('#todoModal').classList.add('hidden'));
$('#todoForm').onsubmit=async e=>{e.preventDefault();const form=e.currentTarget, values=Object.fromEntries(new FormData(form));try{await api('/api/todos',{method:'POST',body:JSON.stringify({email_id:state.selected,folder:state.folder,title:values.title,due_at:values.due_at||null})});$('#todoModal').classList.add('hidden');toast('待办已保存');refreshTodoCount();}catch(err){toast(err.message,true);}};

async function refreshTodoCount(){try{const d=await api('/api/todos');$('#todoCount').textContent=d.todos.filter(t=>!t.completed).length||'';}catch{}}
async function loadTodos(){state.view='todos';$('#folderTitle').textContent='提醒与待办';$('#folderSubtitle').textContent='需要处理的事项排在最前面';$('#filterSelect').style.display='none';$('#detailPane').innerHTML='<div class="empty-detail"><div class="empty-art">✓</div><h2>把重要邮件变成行动</h2><p>打开一封邮件，点击“设置提醒/待办”即可添加。</p></div>';$('#detailPane').classList.remove('open');$('#mailList').innerHTML='<div class="loading"><div class="spinner"></div>正在读取待办…</div>';try{const d=await api('/api/todos');$('#todoCount').textContent=d.todos.filter(t=>!t.completed).length||'';renderTodos(d.todos);}catch(e){$('#mailList').innerHTML=`<div class="error-state">${esc(e.message)}</div>`;}}
function renderTodos(todos){if(!todos.length){$('#mailList').innerHTML='<div class="empty-list"><div style="font-size:38px">✓</div><b>还没有待办事项</b><p>可以从任意邮件中添加</p></div>';return;}const now=new Date();$('#mailList').innerHTML=`<div class="todo-list">${todos.map(t=>{const overdue=t.due_at&&!t.completed&&new Date(t.due_at)<now;return `<div class="todo-item ${t.completed?'completed':''}"><input class="todo-check" type="checkbox" ${t.completed?'checked':''} data-todo-check="${t.id}"><div class="todo-copy"><b>${esc(t.title)}</b><small class="${overdue?'todo-overdue':''}">${t.due_at?`${overdue?'已逾期 · ':'提醒：'}${esc(shortDate(t.due_at))}`:'未设置提醒时间'}</small></div><button class="todo-delete" data-todo-delete="${t.id}">删除</button></div>`}).join('')}</div>`;$$('[data-todo-check]').forEach(x=>x.onchange=async()=>{await api(`/api/todos/${x.dataset.todoCheck}?completed=${x.checked}`,{method:'PATCH'});loadTodos();});$$('[data-todo-delete]').forEach(x=>x.onclick=async()=>{if(confirm('确定删除这条待办吗？')){await api(`/api/todos/${x.dataset.todoDelete}`,{method:'DELETE'});loadTodos();}});}

async function loadRules(){state.view='rules';$('#folderTitle').textContent='分类规则';$('#folderSubtitle').textContent='新规则优先应用';$('#filterSelect').style.display='none';$('#detailPane').innerHTML='<div class="empty-detail"><div class="empty-art">⚙</div><h2>按你的方式整理邮件</h2><p>规则会自动识别发件人或主题，并设置紧急程度。</p></div>';$('#detailPane').classList.remove('open');$('#mailList').innerHTML='<div class="loading"><div class="spinner"></div>正在读取规则…</div>';try{const d=await api('/api/priority-rules');renderRules(d.rules);}catch(e){$('#mailList').innerHTML=`<div class="error-state">${esc(e.message)}</div>`;}}
function renderRules(rules){$('#mailList').innerHTML=`<div class="rule-banner"><b>${rules.length} 条规则</b><button class="primary" id="newRule">＋ 新建规则</button></div>${rules.length?rules.map(r=>`<div class="rule-item"><div class="rule-head"><b>${esc(r.name)}</b><button class="todo-delete" data-rule-delete="${r.id}">删除</button></div><span class="priority ${r.urgency==='紧急'?'urgent':r.urgency==='普通'?'normal':'low'}">${esc(r.urgency)} ${r.urgency==='紧急'?'!!!':r.urgency==='低'?'!':'!!'}</span><p class="rule-condition">${r.sender_contains?`发件人包含“${esc(r.sender_contains)}”`:''}${r.sender_contains&&r.subject_contains?'，并且 ':''}${r.subject_contains?`主题包含“${esc(r.subject_contains)}”`:''}</p></div>`).join(''):'<div class="empty-list">还没有自定义规则</div>'}`;$('#newRule').onclick=()=>{$('#ruleForm').reset();$('#ruleModal').classList.remove('hidden');};$$('[data-rule-delete]').forEach(b=>b.onclick=async()=>{if(confirm('确定删除这条规则吗？')){await api(`/api/priority-rules/${b.dataset.ruleDelete}`,{method:'DELETE'});loadRules();}});}
$$('[data-rule-close]').forEach(b=>b.onclick=()=>$('#ruleModal').classList.add('hidden'));
$('#ruleForm').onsubmit=async e=>{e.preventDefault();const values=Object.fromEntries(new FormData(e.currentTarget));if(!values.sender_contains.trim()&&!values.subject_contains.trim()){toast('请填写发件人或主题关键词',true);return;}try{await api('/api/priority-rules',{method:'POST',body:JSON.stringify(values)});$('#ruleModal').classList.add('hidden');toast('分类规则已保存');loadRules();}catch(err){toast(err.message,true);}};
function aiMarkup(a) { const marks=a.urgency==='紧急'?'!!!':a.urgency==='低'?'!':'!!'; return `<div class="ai-card"><div class="ai-title"><b>✦ 智能摘要</b><span class="urgency">${esc(a.urgency)} ${marks}</span></div><p>${esc(a.summary)}</p>${a.draft_reply?`<div class="ai-actions"><button class="primary" id="useDraft">使用建议回复</button><button class="secondary" id="analyzeButton">重新生成</button></div>`:''}</div>`; }
async function analyzeCurrent() { const button = $('#analyzeButton'); if (button) { button.disabled = true; button.textContent = '正在思考…'; } try { const a = await api(`/api/mailbox/${state.selected}/analyze`, {method:'POST', body:JSON.stringify({folder:state.folder,account:state.selectedAccount,instruction:'请用简单的话总结，并准备一份简洁礼貌的回复'})}); renderDetail(a); } catch(e) { toast(e.message, true); if(button){button.disabled=false;button.textContent='重试';} } }
async function action(name, reload = true, emailId = state.selected) { if (!emailId) return; try { await api(`/api/mailbox/${emailId}/action`, {method:'POST', body:JSON.stringify({action:name,folder:state.folder,account:state.selectedAccount})}); if (!reload) { const item=state.emails.find(e=>e.id===emailId&&e.account===state.selectedAccount); if(item)item.is_read=true; return; } if (['trash','delete'].includes(name)) { $('#detailPane').classList.remove('open'); $('#detailPane').innerHTML='<div class="empty-detail"><div class="empty-art">✓</div><h2>已经处理好了</h2><p>请选择下一封邮件</p></div>'; } toast('操作成功'); await loadMailbox($('#searchInput').value.trim()); } catch(e) { toast(e.message,true); } }

function openCompose(values = {}) { const form = $('#composeForm'); form.reset(); form.to.value = values.to || ''; form.subject.value = values.subject || ''; form.body.value = values.body || ''; $('#composeModal').classList.remove('hidden'); setTimeout(() => (form.to.value ? form.body : form.to).focus(), 50); }
$$('[data-compose]').forEach(b => b.onclick = () => openCompose());
$$('[data-close]').forEach(b => b.onclick = () => $('#composeModal').classList.add('hidden'));
$('#composeModal').onclick = e => { if(e.target === $('#composeModal')) $('#composeModal').classList.add('hidden'); };
$('#composeForm').onsubmit = async e => { e.preventDefault(); const form = e.currentTarget, button = form.querySelector('[type=submit]'); button.disabled=true; button.textContent='正在发送…'; try { await api('/api/send',{method:'POST',body:JSON.stringify(Object.fromEntries(new FormData(form)))}); $('#composeModal').classList.add('hidden'); form.reset(); toast('邮件发送成功'); } catch(err){toast(err.message,true);} finally {button.disabled=false;button.innerHTML='发送邮件 <span>➤</span>';} };
$$('.nav-item').forEach(b => b.onclick = () => { $$('.nav-item').forEach(x=>x.classList.remove('active')); b.classList.add('active'); $('#sidebar').classList.remove('open'); if(b.dataset.view==='todos'){loadTodos();return;}if(b.dataset.view==='rules'){loadRules();return;} state.view='mail';$('#filterSelect').style.display='';if(b.dataset.filter){state.folder='INBOX';state.filter=b.dataset.filter;$('#filterSelect').value=b.dataset.filter;}else{state.folder=b.dataset.folder;state.filter='all';$('#filterSelect').value='all';} loadMailbox(); });
$('#filterSelect').onchange = e => {state.filter=e.target.value;renderList();};
$('#refreshButton').onclick = () => loadMailbox($('#searchInput').value.trim());
$('#searchInput').onkeydown = e => {if(e.key==='Enter')loadMailbox(e.target.value.trim());};
$('#menuButton').onclick = () => $('#sidebar').classList.toggle('open');

api('/api/account').then(a => {state.accounts=a.accounts||[];$('#accountAddress').textContent=state.accounts.length>1?`${state.accounts.length} 个邮箱已连接`:(a.address||'尚未配置邮箱');$('#avatar').textContent=(a.address||'我')[0].toUpperCase();const options=state.accounts.map(x=>`<option value="${esc(x.id)}">${esc(x.label)} · ${esc(x.address)}</option>`).join('');$('#accountSelect').innerHTML='<option value="all">全部邮箱</option>'+options;$('#sendAccount').innerHTML=options;$('#accountSelect').onchange=e=>{state.account=e.target.value;loadMailbox($('#searchInput').value.trim());};if(!a.configured)toast('请先在 .env 文件中配置邮箱',true);});
loadMailbox();
refreshTodoCount();
