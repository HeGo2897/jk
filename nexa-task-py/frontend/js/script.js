/* NEXA TASK: script.js
 * Three layers:
 *   1) DATA LAYER   - loads/saves tasks through api.js (Python Flask backend -> SQL database)
 *   2) LOGIC LAYER  - pure functions: status, statistics, filter, sort (no DOM, no network)
 *   3) UI LAYER     - renders the dashboard and handles clicks
 * The database is the single source of truth: after every change the tasks are re-loaded from the server. */
'use strict';

const THEME_KEY = 'nexa.theme';               // only the colour theme is kept in the browser
const PROGRESS = { PENDING: 20, IN_PROGRESS: 60, COMPLETED: 100 };
const LABEL = { PENDING: 'Pending', IN_PROGRESS: 'In Progress', COMPLETED: 'Completed', OVERDUE: 'Overdue' };
const PRIORITY_RANK = { HIGH: 0, MEDIUM: 1, LOW: 2 };
const STATUS_FILTERS = ['PENDING', 'IN_PROGRESS', 'COMPLETED', 'OVERDUE'];
const state = {
  tasks: [], activity: [], view: 'dashboard', filter: 'all', sort: 'deadline', query: '',
  loaded: false, offline: false, busy: false
};

/* ---------- helpers ---------- */
const $ = s => document.querySelector(s);
const pad = n => String(n).padStart(2, '0');
const toISODate = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const todayStr = () => toISODate(new Date());
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmtDate = d => d ? new Date(d + 'T00:00:00').toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : 'No deadline';
function daysLeft(d) { return d ? Math.round((new Date(d + 'T00:00:00') - new Date(todayStr() + 'T00:00:00')) / 864e5) : null; }
function remaining(d) {
  const n = daysLeft(d);
  if (n === null) return 'No deadline';
  if (n < 0) return `${-n}d overdue`;
  if (n === 0) return 'Due today';
  return n === 1 ? 'Tomorrow' : `${n} days left`;
}
function timeAgo(ts) {
  const m = Math.floor((Date.now() - ts) / 6e4);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  return h < 24 ? `${h}h ago` : `${Math.floor(h / 24)}d ago`;
}
function toast(message, type = 'ok') {
  const el = document.createElement('div');
  el.className = 'toast ' + type;
  el.textContent = message;
  $('#toasts').appendChild(el);
  setTimeout(() => el.classList.add('out'), 3200);
  setTimeout(() => el.remove(), 3600);
}

/* =====================================================
 * 1. DATA LAYER: every function here talks to the Python backend
 *    Python: routes (app.py) -> TaskService (service.py) -> SqlTaskDao (dao.py) -> database
 * ===================================================== */
async function loadTasks() {                 // GET /api/tasks  ->  SELECT ... FROM tasks
  const [tasks, activity] = await Promise.all([Api.listTasks(), Api.listActivity()]);
  state.tasks = tasks;
  state.activity = activity;
}
const addTask = data => Api.createTask(data);                         // POST   -> INSERT
const updateTask = (id, changes) => Api.updateTask(id, changes);     // PUT    -> UPDATE
const deleteTask = id => Api.deleteTask(id);                          // DELETE -> DELETE
const completeTask = id => Api.updateTask(id, { status: 'COMPLETED' });
const findTask = id => state.tasks.find(t => t.id === id);

/** Runs one server action, then reloads the data from the database and redraws the screen. */
async function perform(action, successMessage) {
  if (state.busy) return false;
  setBusy(true);
  try {
    await action();
    await loadTasks();
    setOffline(false);
    refresh();
    if (successMessage) toast(successMessage);
    return true;
  } catch (err) {
    handleError(err);
    return false;
  } finally {
    setBusy(false);
  }
}
function handleError(err) {
  if (err.status === 0) { setOffline(true, err.message); refresh(); }
  else toast(err.message || 'Something went wrong', 'error');
}
function setBusy(flag) {
  state.busy = flag;
  document.body.classList.toggle('busy', flag);
  $('#saveBtn').disabled = flag;
}
function setOffline(flag, message) {
  state.offline = flag;
  $('#offlineBanner').hidden = !flag;
  if (message) $('#offlineMsg').textContent = message;
}

/* =====================================================
 * 2. LOGIC LAYER: pure task logic, no DOM, no network
 * ===================================================== */
function effectiveStatus(t) { return t.status !== 'COMPLETED' && t.deadline && t.deadline < todayStr() ? 'OVERDUE' : t.status; }
function computeStats() {
  const c = { PENDING: 0, IN_PROGRESS: 0, COMPLETED: 0, OVERDUE: 0 };
  state.tasks.forEach(t => c[effectiveStatus(t)]++);
  const total = state.tasks.length;
  return { ...c, total, pct: n => total ? Math.round(n / total * 100) : 0 };
}
const SORTERS = {
  deadline: (a, b) => (a.deadline || '9999').localeCompare(b.deadline || '9999'),
  priority: (a, b) => PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority],
  created: (a, b) => new Date(b.created_at) - new Date(a.created_at),
  alpha: (a, b) => a.title.localeCompare(b.title)
};
function getVisibleTasks() {
  const q = state.query.trim().toLowerCase();
  return state.tasks.filter(t => {
    if (q && ![t.title, t.description, t.category].some(s => (s || '').toLowerCase().includes(q))) return false;
    if (state.filter === 'all') return true;
    return STATUS_FILTERS.includes(state.filter) ? effectiveStatus(t) === state.filter : t.priority === state.filter;
  }).sort(SORTERS[state.sort]);
}

/* =====================================================
 * 3. UI LAYER
 * ===================================================== */
function applyWidths(root) {
  root.querySelectorAll('[data-w]').forEach(el => requestAnimationFrame(() => { el.style.width = el.dataset.w + '%'; }));
}
function taskCard(t) {
  const st = effectiveStatus(t), done = t.status === 'COMPLETED', prog = PROGRESS[t.status];
  return `<article class="task s-${st}${done ? ' done' : ''}">
    <div class="task-top"><h3>${esc(t.title)}</h3><span class="badge s-${st}">${LABEL[st]}</span></div>
    <p class="desc">${esc(t.description) || 'No description'}</p>
    <div class="tags"><span class="badge p-${t.priority}">${t.priority}</span><span class="tag">${esc(t.category || 'General')}</span></div>
    <div class="meta"><span>⏱ ${fmtDate(t.deadline)}</span><span>Created ${new Date(t.created_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })}</span></div>
    <div class="progress"><div class="bar"><i data-w="${prog}"></i></div><b>${prog}%</b></div>
    <div class="actions">
      <button data-act="complete" data-id="${t.id}">${done ? '↺ Reopen' : '✓ Complete'}</button>
      <button data-act="edit" data-id="${t.id}">✎ Edit</button>
      <button data-act="delete" data-id="${t.id}">✕ Delete</button>
    </div></article>`;
}
function renderTasks() {
  const box = $('#taskList');
  if (!state.loaded) {                                   // first load: shimmering placeholders
    box.innerHTML = '<div class="task skeleton"></div>'.repeat(3);
    $('#emptyState').hidden = true;
    return;
  }
  if (state.offline) {                                   // server down: do not claim "all caught up"
    box.innerHTML = '';
    $('#emptyState').hidden = true;
    $('#taskCount').textContent = '';
    return;
  }
  const list = getVisibleTasks();
  box.innerHTML = list.map(taskCard).join('');
  $('#taskCount').textContent = `${list.length} task${list.length === 1 ? '' : 's'}`;
  const none = list.length === 0, noTasksAtAll = state.tasks.length === 0;
  $('#emptyState').hidden = !none;
  $('#emptyTitle').textContent = noTasksAtAll ? "You're all caught up." : 'No matching tasks';
  $('#emptyText').textContent = noTasksAtAll ? 'No tasks yet. Capture your first one and let NEXA keep track of it.' : 'Try a different search, filter or sort option.';
  $('#emptyAdd').hidden = !noTasksAtAll;
  applyWidths(box);
}
function renderStats(s) {
  const set = (id, v) => { $(id).textContent = v; };
  set('#statTotal', s.total); set('#statDone', s.COMPLETED); set('#statPending', s.PENDING); set('#statOverdue', s.OVERDUE);
  const week = state.tasks.filter(t => Date.now() - new Date(t.created_at) < 7 * 864e5).length;
  set('#trendTotal', `▲ ${week} added this week`);
  set('#trendDone', `▲ ${s.pct(s.COMPLETED)}% of all tasks`);
  set('#trendPending', `● ${s.pct(s.PENDING)}% waiting`);
  set('#trendOverdue', s.OVERDUE ? `▼ ${s.pct(s.OVERDUE)}% need attention` : '✓ Nothing late');
}
function renderAnalytics(s) {
  const score = s.pct(s.COMPLETED);
  $('#scoreRing').style.setProperty('--p', score);
  $('#scoreVal').textContent = score + '%';
  $('#totalTasks').textContent = s.total;
  $('#scoreNote').textContent = !s.total ? 'Add tasks to start tracking.' : score >= 70 ? 'Excellent momentum.' : score >= 40 ? 'Steady progress.' : 'Time to focus.';
  const rows = [['COMPLETED', 'Completed'], ['IN_PROGRESS', 'In Progress'], ['PENDING', 'Pending'], ['OVERDUE', 'Overdue']];
  const box = $('#statusBars');
  box.innerHTML = rows.map(([k, l]) => `<div class="row s-${k}"><span>${l}</span><div class="bar"><i data-w="${s.pct(s[k])}"></i></div><b>${s.pct(s[k])}%</b></div>`).join('');
  applyWidths(box);
}
function renderCategories(s) {
  const map = {};
  state.tasks.forEach(t => { const c = t.category || 'General'; map[c] = (map[c] || 0) + 1; });
  const entries = Object.entries(map).sort((a, b) => b[1] - a[1]), box = $('#catBars');
  box.innerHTML = entries.length
    ? entries.map(([c, n]) => `<div class="row s-TOTAL"><span title="${esc(c)}">${esc(c)}</span><div class="bar"><i data-w="${s.pct(n)}"></i></div><b>${n}</b></div>`).join('')
    : '<p class="muted">No categories yet.</p>';
  applyWidths(box);
}
function renderUpcoming() {
  const items = state.tasks.filter(t => t.status !== 'COMPLETED' && t.deadline).sort(SORTERS.deadline).slice(0, 5);
  $('#upcomingList').innerHTML = items.length ? items.map(t => {
    const late = effectiveStatus(t) === 'OVERDUE';
    return `<li class="${late ? 'late' : ''}"><div><b>${esc(t.title)}</b><small>${fmtDate(t.deadline)} · ${t.priority}</small></div><span class="remain">${remaining(t.deadline)}</span></li>`;
  }).join('') : '<li class="none">Nothing due soon.</li>';
}
function renderActivity() {
  $('#activityList').innerHTML = state.activity.length
    ? state.activity.slice(0, 6).map(a => `<li><div><b>${esc(a.message)}</b><small>${esc(a.detail)}</small></div><small>${timeAgo(a.at)}</small></li>`).join('')
    : '<li class="none">No activity yet.</li>';
}
function updateDashboard() {
  const s = computeStats();
  renderStats(s); renderAnalytics(s); renderCategories(s); renderUpcoming(); renderActivity();
  const bell = $('#bellCount'); bell.textContent = s.OVERDUE; bell.hidden = !s.OVERDUE;
  const h = new Date().getHours();
  $('#greeting').textContent = `Good ${h < 12 ? 'morning' : h < 17 ? 'afternoon' : 'evening'}, User`;
}
function refresh() { renderTasks(); updateDashboard(); }

/* ---------- navigation ---------- */
function syncNav() {
  const items = [...document.querySelectorAll('.nav-item')];
  let active = items.find(i => i.dataset.view === state.view && (!i.dataset.filter || i.dataset.filter === state.filter));
  if (!active && state.view === 'tasks') active = items.find(i => i.dataset.filter === 'all');
  items.forEach(i => i.classList.toggle('active', i === active));
}
function setView(view, filter) {
  state.view = view;
  if (filter !== undefined) { state.filter = filter; $('#filterSelect').value = filter; }
  document.querySelectorAll('[data-views]').forEach(el => { el.hidden = !el.dataset.views.split(' ').includes(view); });
  syncNav(); closeMenu(); window.scrollTo(0, 0); renderTasks();
}
const openMenu = () => { $('#sidebar').classList.add('open'); $('#scrim').classList.add('show'); };
const closeMenu = () => { $('#sidebar').classList.remove('open'); $('#scrim').classList.remove('show'); };

/* ---------- modal ---------- */
function openModal(task) {
  $('#taskForm').reset(); $('#titleError').textContent = '';
  $('#modalTitle').textContent = task ? 'Edit Task' : 'New Task';
  $('#fId').value = task ? task.id : '';
  if (task) {
    $('#fTitle').value = task.title; $('#fDesc').value = task.description || ''; $('#fCategory').value = task.category || '';
    $('#fPriority').value = task.priority; $('#fDeadline').value = task.deadline || ''; $('#fStatus').value = task.status;
  }
  $('#modal').classList.add('open'); $('#fTitle').focus();
}
const closeModal = () => $('#modal').classList.remove('open');
async function handleSubmit(e) {
  e.preventDefault();
  const title = $('#fTitle').value.trim();
  if (!title) { $('#titleError').textContent = 'Task title is required.'; $('#fTitle').focus(); return; }
  const data = {
    title, description: $('#fDesc').value.trim(), category: $('#fCategory').value.trim() || 'General',
    priority: $('#fPriority').value, deadline: $('#fDeadline').value || null, status: $('#fStatus').value
  };
  const id = Number($('#fId').value);
  const saved = await perform(() => id ? updateTask(id, data) : addTask(data), id ? 'Task updated' : 'Task created');
  if (saved) closeModal();
}
async function handleTaskAction(e) {
  const btn = e.target.closest('[data-act]'); if (!btn) return;
  const id = Number(btn.dataset.id), t = findTask(id); if (!t) return;
  switch (btn.dataset.act) {
    case 'edit': return openModal(t);
    case 'delete':
      if (confirm(`Delete "${t.title}"?`)) await perform(() => deleteTask(id), 'Task deleted');
      return;
    case 'complete':
      return t.status === 'COMPLETED'
        ? perform(() => updateTask(id, { status: 'PENDING' }), 'Task reopened')
        : perform(() => completeTask(id), 'Task completed');
  }
}

/* ---------- theme ---------- */
function readTheme() { try { return localStorage.getItem(THEME_KEY); } catch (e) { return null; } }
function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  $('#themeBtn').textContent = theme === 'dark' ? '☀' : '☾';
  try { localStorage.setItem(THEME_KEY, theme); } catch (e) { /* storage blocked: theme just won't persist */ }
}

/* ---------- backend status (Settings page) ---------- */
async function showBackendInfo() {
  const el = $('#backendInfo');
  try {
    const h = await Api.health();
    el.textContent = `● Connected: storage = ${({ sqlite: 'SQLite database', mysql: 'MySQL database' })[h.storage] || h.storage}`;
    el.className = 'status-line ok';
  } catch (err) {
    el.textContent = '● Not connected to the Python server';
    el.className = 'status-line bad';
  }
}

/* ---------- start-up ---------- */
function bindEvents() {
  $('#addBtn').onclick = () => openModal();
  $('#emptyAdd').onclick = () => openModal();
  $('#cancelBtn').onclick = closeModal; $('#closeX').onclick = closeModal;
  $('#modal').addEventListener('mousedown', e => { if (e.target.id === 'modal') closeModal(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') { closeModal(); closeMenu(); } });
  $('#taskForm').addEventListener('submit', handleSubmit);
  $('#taskList').addEventListener('click', handleTaskAction);
  $('#searchInput').addEventListener('input', e => {
    state.query = e.target.value;
    if (!['dashboard', 'tasks'].includes(state.view)) setView('tasks'); else renderTasks();
  });
  $('#filterSelect').addEventListener('change', e => { state.filter = e.target.value; syncNav(); renderTasks(); });
  $('#sortSelect').addEventListener('change', e => { state.sort = e.target.value; renderTasks(); });
  $('#nav').addEventListener('click', e => {
    const b = e.target.closest('.nav-item'); if (!b) return;
    setView(b.dataset.view, b.dataset.filter || 'all');
    if (b.dataset.view === 'settings') showBackendInfo();
  });
  $('#menuBtn').onclick = openMenu; $('#scrim').onclick = closeMenu;
  $('#themeBtn').onclick = () => applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
  $('#bellBtn').onclick = () => setView('tasks', 'OVERDUE');
  $('#retryBtn').onclick = () => perform(() => Promise.resolve(), 'Connected');
  $('#loadSampleBtn').onclick = () => perform(() => Api.loadSamples(), 'Sample tasks added');
  $('#clearBtn').onclick = () => {
    if (confirm('Delete ALL tasks from the database? This cannot be undone.')) perform(() => Api.deleteAll(), 'All tasks deleted');
  };
}
async function init() {
  applyTheme(readTheme() || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));
  $('#todayDate').textContent = new Date().toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });
  bindEvents();
  setView('dashboard', 'all');                 // shows loading placeholders
  try { await loadTasks(); } catch (err) { handleError(err); }
  state.loaded = true;
  refresh();
}
init();
