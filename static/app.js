// ===== 全局状态 =====
let currentMode = 'driving';
let currentRoute = null;   // 当前单条路线（含 GCJ-02 与 WGS84 两套坐标）
let batchRoutes = [];      // 批量搜索成功的路线对象数组
let planItems = [];        // 今日计划条目
let parsedItems = [];      // 批量解析出的起终点

const MODE_LABEL = { driving: '驾车', walking: '步行', riding: '骑行' };

// ===== 工具函数 =====
function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}
function uid() { return Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4); }
function todayStr() {
  const d = new Date();
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
}
function fmtDistance(m) {
  m = Number(m) || 0;
  return m >= 1000 ? (m / 1000).toFixed(2) + ' 公里' : m + ' 米';
}
function fmtDuration(s) {
  s = Number(s) || 0;
  if (s >= 3600) return Math.floor(s / 3600) + ' 小时 ' + Math.round((s % 3600) / 60) + ' 分钟';
  if (s >= 60) return Math.round(s / 60) + ' 分钟';
  return s + ' 秒';
}
function timeAgo(ts) {
  const diff = (Date.now() - ts * 1000) / 1000;
  if (diff < 60) return '刚刚';
  if (diff < 3600) return Math.floor(diff / 60) + ' 分钟前';
  if (diff < 86400) return Math.floor(diff / 3600) + ' 小时前';
  return new Date(ts * 1000).toLocaleDateString();
}

let toastTimer = null;
function toast(msg, isError = false) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast' + (isError ? ' error' : '');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.add('hidden'), 3200);
}

async function api(path, options = {}) {
  const resp = await fetch(path, options);
  return await resp.json().catch(() => ({ success: false, error: '响应解析失败' }));
}

// ===== 地图 =====
const map = L.map('map', { center: [39.909, 116.397], zoom: 11 });
L.tileLayer('/tiles/{z}/{x}/{y}.png', {
  maxZoom: 18,
  attribution: '&copy; 高德地图'
}).addTo(map);

let routeLayer = null;
const TRAFFIC_COLORS = { 0: '#1677ff', 1: '#00b42a', 2: '#f7ba1e', 3: '#ff7d00', 4: '#ff4d4f' };
function drawRoute(route) {
  if (routeLayer) { map.removeLayer(routeLayer); }
  routeLayer = L.layerGroup();
  const traffic = route.traffic_gcj;
  const boundsPts = (route.polyline_gcj || []).map(p => [p[1], p[0]]); // [lat, lng]
  if (route.mode === 'transit' && route.segments) {
    route.segments.forEach(s => {
      const pts = (s.polyline_gcj || []).map(p => [p[1], p[0]]);
      if (pts.length >= 2) {
        const color = (s.type === '步行') ? '#86909c' : '#1677ff';
        L.polyline(pts, { color, weight: 4, opacity: 0.9 }).addTo(routeLayer);
      }
    });
  } else if (traffic && traffic.length) {
    traffic.forEach(t => {
      const pts = (t.polyline_gcj || []).map(p => [p[1], p[0]]);
      L.polyline(pts, { color: TRAFFIC_COLORS[t.status] || '#1677ff', weight: 5, opacity: 0.9 }).addTo(routeLayer);
    });
  } else {
    L.polyline(boundsPts, { color: '#1677ff', weight: 5, opacity: 0.9 }).addTo(routeLayer);
  }
  const o = route.origin, d = route.destination;
  L.circleMarker([o.lat, o.lng], { radius: 8, color: '#fff', weight: 2, fillColor: '#00b42a', fillOpacity: 1 })
    .bindPopup('起点：' + esc(o.name)).addTo(routeLayer);
  L.circleMarker([d.lat, d.lng], { radius: 8, color: '#fff', weight: 2, fillColor: '#ff4d4f', fillOpacity: 1 })
    .bindPopup('终点：' + esc(d.name)).addTo(routeLayer);
  routeLayer.addTo(map);
  if (boundsPts.length >= 2) {
    map.fitBounds(L.latLngBounds(boundsPts), { padding: [40, 40] });
  } else {
    map.setView([(o.lat + d.lat) / 2, (o.lng + d.lng) / 2], 12);
  }
}

// ===== 页签 =====
function switchTab(name) {
  document.querySelectorAll('.tab').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  document.querySelectorAll('.panel').forEach(p => p.classList.toggle('active', p.id === 'panel-' + name));
  if (name === 'search') setTimeout(() => map.invalidateSize(), 0);
}
document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});

// ===== 单条路线搜索 =====
document.getElementById('modeGroup').addEventListener('click', e => {
  const b = e.target.closest('.mode-btn');
  if (!b) return;
  document.querySelectorAll('.mode-btn').forEach(x => x.classList.remove('active'));
  b.classList.add('active');
  currentMode = b.dataset.mode;
  const isDriving = currentMode === 'driving';
  document.getElementById('strategyWrap').style.display = isDriving ? '' : 'none';
  document.getElementById('waypointsWrap').style.display = isDriving ? '' : 'none';
});

function addWaypointInput(value) {
  const list = document.getElementById('waypointsList');
  const input = document.createElement('input');
  input.type = 'text';
  input.className = 'waypoint-input';
  input.placeholder = '途经点（地址或经纬度）';
  if (value) input.value = value;
  list.appendChild(input);
}
function collectWaypoints() {
  return [...document.querySelectorAll('.waypoint-input')].map(i => i.value.trim()).filter(Boolean);
}
document.getElementById('addWaypointBtn').onclick = () => addWaypointInput('');

document.getElementById('searchBtn').addEventListener('click', doSearch);
['originInput', 'destInput'].forEach(id => {
  document.getElementById(id).addEventListener('keydown', e => { if (e.key === 'Enter') doSearch(); });
});

async function doSearch() {
  const origin = document.getElementById('originInput').value.trim();
  const dest = document.getElementById('destInput').value.trim();
  if (!origin || !dest) { toast('请填写起点和终点', true); return; }
  const btn = document.getElementById('searchBtn');
  btn.disabled = true; btn.textContent = '搜索中…';
  try {
    const data = await api('/api/search', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ origin, destination: dest, mode: currentMode,
        strategy: document.getElementById('strategySelect').value,
        waypoints: collectWaypoints() })
    });
    if (!data.success) { toast(data.error || '搜索失败', true); return; }
    currentRoute = data.route;
    renderResult(data.route);
    loadHistory();
    toast('搜索成功');
  } catch (e) {
    toast('请求失败：' + e.message, true);
  } finally {
    btn.disabled = false; btn.textContent = '🔍 搜索';
  }
}

function renderResult(route) {
  document.getElementById('distanceSpan').textContent = fmtDistance(route.distance_m);
  document.getElementById('durationSpan').textContent = fmtDuration(route.duration_s);
  document.getElementById('modeSpan').textContent = route.mode_label;
  drawRoute(route);
  const thead = document.querySelector('#stepsTable thead');
  const tbody = document.querySelector('#stepsTable tbody');
  tbody.innerHTML = '';
  if (route.mode === 'transit') {
    thead.innerHTML = '<tr><th>类型</th><th>线路</th><th>上车站/起点</th><th>下车站/终点</th><th>距离</th><th>耗时</th></tr>';
    (route.segments || []).forEach(s => {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${esc(s.type)}</td><td>${esc(s.name)}</td><td>${esc(s.start)}</td>` +
        `<td>${esc(s.end)}</td><td>${fmtDistance(s.distance_m)}</td><td>${fmtDuration(s.duration_s)}</td>`;
      tbody.appendChild(tr);
    });
    if (route.cost !== undefined && route.cost !== '') {
      document.getElementById('modeSpan').textContent = route.mode_label + ' · 约 ' + route.cost + ' 元';
    }
  } else {
    thead.innerHTML = '<tr><th>序号</th><th>导航指令</th><th>道路</th><th>动作</th><th>距离</th><th>耗时</th></tr>';
    route.steps.forEach(s => {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${s.index}</td><td>${esc(s.instruction)}</td><td>${esc(s.road)}</td>` +
        `<td>${esc(s.action)}</td><td>${fmtDistance(s.distance_m)}</td><td>${fmtDuration(s.duration_s)}</td>`;
      tbody.appendChild(tr);
    });
  }
  document.getElementById('resultPanel').classList.remove('hidden');
}

// ===== 导出 =====
async function doExport(kind, route, routes) {
  try {
    const data = await api('/api/export', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind, route, routes })
    });
    if (!data.success) { toast(data.error || '导出失败', true); return; }
    triggerDownload(data.url, data.filename);
    toast('已导出：' + data.filename);
  } catch (e) { toast('导出失败：' + e.message, true); }
}
function triggerDownload(url, filename) {
  const a = document.createElement('a');
  a.href = url;
  a.download = filename || '';
  document.body.appendChild(a);
  a.click();
  a.remove();
}

document.getElementById('exportCsvBtn').onclick = () => currentRoute && doExport('route_csv', currentRoute);
document.getElementById('exportGeojsonBtn').onclick = () => currentRoute && doExport('route_geojson', currentRoute);
document.getElementById('addToPlanBtn').onclick = () => {
  if (!currentRoute) return;
  const def = currentRoute.origin.name + ' → ' + currentRoute.destination.name;
  const name = prompt('给这条路线起个备注名（可留空）', def);
  if (name === null) return;
  const copy = JSON.parse(JSON.stringify(currentRoute));
  copy.name = name.trim();
  planItems.push({ id: uid(), name: name.trim(), ts: Date.now(), route: copy });
  savePlan(); renderPlan();
  toast('已加入今日计划');
};

// ===== 搜索历史 =====
async function loadHistory() {
  const data = await api('/api/history');
  if (!data.success) return;
  const ul = document.getElementById('historyList');
  ul.innerHTML = '';
  if (!data.history || !data.history.length) { ul.innerHTML = '<li class="muted">暂无历史记录</li>'; return; }
  data.history.forEach(h => {
    const li = document.createElement('li');
    li.innerHTML = `<div>${esc(h.origin_text)} → ${esc(h.dest_text)}</div>` +
      `<div class="h-meta">${esc(h.mode_label)} · ${fmtDistance(h.distance_m)} · ${timeAgo(h.ts)}</div>`;
    li.addEventListener('click', () => {
      currentRoute = h.route;
      document.getElementById('originInput').value = h.origin_text;
      document.getElementById('destInput').value = h.dest_text;
      switchTab('search');
      renderResult(h.route);
    });
    ul.appendChild(li);
  });
}
document.getElementById('clearHistoryBtn').onclick = async () => {
  if (!confirm('清空全部搜索历史？')) return;
  await api('/api/history/clear', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
  loadHistory();
};

// ===== 坐标转换 =====
document.getElementById('convBtn').onclick = async () => {
  const lng = parseFloat(document.getElementById('convLng').value);
  const lat = parseFloat(document.getElementById('convLat').value);
  if (isNaN(lng) || isNaN(lat)) { toast('请输入有效经纬度', true); return; }
  const direction = document.getElementById('convDir').value;
  const data = await api('/api/convert', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lng, lat, direction })
  });
  if (!data.success) { toast(data.error || '转换失败', true); return; }
  const r = document.getElementById('convResult');
  r.classList.remove('hidden');
  r.innerHTML = `<div>${esc(data.label)}</div>` +
    `<div>输入：lng <b>${data.input.lng}</b>，lat <b>${data.input.lat}</b></div>` +
    `<div>输出：lng <b>${data.output.lng}</b>，lat <b>${data.output.lat}</b></div>`;
};

// ===== 定位 + 轨迹录制 =====
document.getElementById('locateBtn').onclick = () => {
  if (!navigator.geolocation) { toast('当前浏览器不支持定位', true); return; }
  navigator.geolocation.getCurrentPosition(
    pos => {
      const lng = pos.coords.longitude.toFixed(6);
      const lat = pos.coords.latitude.toFixed(6);
      document.getElementById('originInput').value = lng + ',' + lat;
      toast('已定位并填入起点');
    },
    err => toast('定位失败：' + err.message, true),
    { enableHighAccuracy: true, timeout: 10000 }
  );
};

let trackPoints = [];   // [[lng, lat], ...] WGS84
let trackTimer = null;

document.getElementById('startRecordBtn').onclick = () => {
  if (!navigator.geolocation) { toast('当前浏览器不支持定位', true); return; }
  trackPoints = [];
  document.getElementById('startRecordBtn').disabled = true;
  document.getElementById('stopRecordBtn').disabled = false;
  document.getElementById('recordCount').textContent = '0';
  toast('开始录制');
  function tick() {
    navigator.geolocation.getCurrentPosition(
      pos => {
        const lng = +pos.coords.longitude.toFixed(6);
        const lat = +pos.coords.latitude.toFixed(6);
        const last = trackPoints[trackPoints.length - 1];
        if (!last || last[0] !== lng || last[1] !== lat) {
          trackPoints.push([lng, lat]);
          document.getElementById('recordCount').textContent = trackPoints.length;
        }
      },
      () => {},   // 忽略单次失败
      { enableHighAccuracy: true, timeout: 10000 }
    );
  }
  tick();
  trackTimer = setInterval(tick, 5000);
};

document.getElementById('stopRecordBtn').onclick = () => {
  clearInterval(trackTimer);
  trackTimer = null;
  document.getElementById('startRecordBtn').disabled = false;
  document.getElementById('stopRecordBtn').disabled = true;
  toast('已停止，共 ' + trackPoints.length + ' 个点');
};

async function exportTrack(kind) {
  if (!trackPoints.length) { toast('暂无轨迹点', true); return; }
  try {
    const data = await api('/api/export', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind, points: trackPoints })
    });
    if (data.success) { triggerDownload(data.url, data.filename); toast('已导出：' + data.filename); }
    else toast(data.error || '导出失败', true);
  } catch (e) { toast('导出失败：' + e.message, true); }
}
document.getElementById('exportTrackGeojsonBtn').onclick = () => exportTrack('trajectory_geojson');
document.getElementById('exportTrackCsvBtn').onclick = () => exportTrack('trajectory_csv');

// ===== 批量导入 =====
document.getElementById('parseBtn').onclick = async () => {
  const file = document.getElementById('fileInput').files[0];
  if (!file) { toast('请先选择 Excel/CSV 文件', true); return; }
  const buf = await file.arrayBuffer();
  try {
    const data = await api('/api/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/octet-stream', 'X-Filename': encodeURIComponent(file.name) },
      body: buf
    });
    if (!data.success) { toast(data.error || '解析失败', true); return; }
    parsedItems = data.items;
    batchRoutes = [];
    renderBatchPreview(data.items);
    document.getElementById('batchSearchBtn').disabled = data.items.length === 0;
    document.getElementById('batchStatus').textContent = '已解析 ' + data.items.length + ' 条，可点击“搜索全部”';
    document.getElementById('batchResult').classList.add('hidden');
  } catch (e) { toast('解析失败：' + e.message, true); }
};

function renderBatchPreview(items) {
  document.getElementById('batchPreview').classList.remove('hidden');
  const tbl = document.getElementById('batchPreviewTable');
  let html = '<thead><tr><th>#</th><th>起点</th><th>终点</th><th>出行方式</th><th>备注</th></tr></thead><tbody>';
  items.forEach((it, i) => {
    html += `<tr><td>${i + 1}</td><td>${esc(it.origin)}</td><td>${esc(it.destination)}</td>` +
      `<td>${esc(MODE_LABEL[it.mode] || '默认')}</td><td>${esc(it.name)}</td></tr>`;
  });
  tbl.innerHTML = html + '</tbody>';
}

document.getElementById('batchSearchBtn').onclick = async () => {
  if (!parsedItems.length) return;
  const btn = document.getElementById('batchSearchBtn');
  const status = document.getElementById('batchStatus');
  btn.disabled = true; btn.textContent = '搜索中…';
  status.textContent = '正在搜索 ' + parsedItems.length + ' 条路线，请稍候…';
  try {
    const data = await api('/api/batch', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ items: parsedItems, default_mode: document.getElementById('batchDefaultMode').value,
        strategy: document.getElementById('batchStrategy').value })
    });
    if (!data.success) { toast(data.error || '搜索失败', true); return; }
    batchRoutes = data.results.filter(r => r.ok).map(r => r.route);
    renderBatchResult(data.results);
    status.textContent = '完成：成功 ' + data.ok_count + ' / 共 ' + data.total + ' 条';
    toast('搜索完成：成功 ' + data.ok_count + ' 条');
  } catch (e) {
    toast('请求失败：' + e.message, true);
  } finally {
    btn.disabled = false; btn.textContent = '② 搜索全部路线';
  }
};

function renderBatchResult(results) {
  document.getElementById('batchResult').classList.remove('hidden');
  const tbl = document.getElementById('batchResultTable');
  let html = '<thead><tr><th>#</th><th>备注</th><th>起点</th><th>终点</th><th>方式</th><th>距离</th><th>耗时</th><th>状态</th></tr></thead><tbody>';
  results.forEach((r, i) => {
    if (r.ok) {
      const rt = r.route;
      html += `<tr><td>${i + 1}</td><td>${esc(r.name)}</td><td>${esc(rt.origin.name)}</td>` +
        `<td>${esc(rt.destination.name)}</td><td>${esc(rt.mode_label)}</td>` +
        `<td>${fmtDistance(rt.distance_m)}</td><td>${fmtDuration(rt.duration_s)}</td><td>✅</td></tr>`;
    } else {
      html += `<tr><td>${i + 1}</td><td>${esc(r.name)}</td><td>${esc(r.origin)}</td><td>${esc(r.destination)}</td>` +
        `<td>-</td><td>-</td><td>-</td><td style="color:#ff4d4f">失败：${esc(r.error)}</td></tr>`;
    }
  });
  tbl.innerHTML = html + '</tbody>';
}

document.getElementById('exportStatsBtn').onclick = () => batchRoutes.length && doExport('stats_csv', null, batchRoutes);
document.getElementById('exportBatchGeojsonBtn').onclick = () => batchRoutes.length && doExport('batch_geojson', null, batchRoutes);
document.getElementById('exportBatchCsvBtn').onclick = () => batchRoutes.length && doExport('batch_csv', null, batchRoutes);

// ===== 今日计划 =====
async function loadPlan() {
  const data = await api('/api/plan');
  if (data.success && data.plan) planItems = data.plan.items || [];
  renderPlan();
}
async function savePlan() {
  await api('/api/plan', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ plan: { date: todayStr(), items: planItems } })
  });
}
function renderPlan() {
  document.getElementById('planDate').textContent = todayStr();
  document.getElementById('planCount').textContent = planItems.length;
  const km = planItems.reduce((s, it) => s + (it.route.distance_m || 0), 0) / 1000;
  document.getElementById('planTotalKm').textContent = km.toFixed(2);
  const badge = document.getElementById('planBadge');
  badge.textContent = planItems.length;
  badge.classList.toggle('hidden', planItems.length === 0);
  const tbody = document.querySelector('#planTable tbody');
  tbody.innerHTML = '';
  planItems.forEach((it, idx) => {
    const r = it.route;
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${esc(it.name) || '<span class="muted">-</span>'}</td>` +
      `<td>${esc(r.origin.name)}</td><td>${esc(r.destination.name)}</td><td>${esc(r.mode_label)}</td>` +
      `<td>${fmtDistance(r.distance_m)}</td><td>${fmtDuration(r.duration_s)}</td>` +
      `<td class="plan-op"><button data-act="view" data-idx="${idx}">查看</button>` +
      `<button data-act="up" data-idx="${idx}">↑</button><button data-act="down" data-idx="${idx}">↓</button>` +
      `<button data-act="del" data-idx="${idx}">删除</button></td>`;
    tbody.appendChild(tr);
  });
}
document.getElementById('planTable').addEventListener('click', e => {
  const b = e.target.closest('button[data-act]');
  if (!b) return;
  const idx = parseInt(b.dataset.idx, 10);
  const act = b.dataset.act;
  if (act === 'view') {
    currentRoute = planItems[idx].route;
    switchTab('search');
    renderResult(currentRoute);
  } else if (act === 'up' && idx > 0) {
    [planItems[idx - 1], planItems[idx]] = [planItems[idx], planItems[idx - 1]];
    savePlan(); renderPlan();
  } else if (act === 'down' && idx < planItems.length - 1) {
    [planItems[idx + 1], planItems[idx]] = [planItems[idx], planItems[idx + 1]];
    savePlan(); renderPlan();
  } else if (act === 'del') {
    planItems.splice(idx, 1);
    savePlan(); renderPlan();
  }
});
document.getElementById('planExportStatsBtn').onclick = () => planItems.length && doExport('stats_csv', null, planItems.map(i => i.route));
document.getElementById('planExportGeojsonBtn').onclick = () => planItems.length && doExport('batch_geojson', null, planItems.map(i => i.route));
document.getElementById('planExportCsvBtn').onclick = () => planItems.length && doExport('batch_csv', null, planItems.map(i => i.route));
document.getElementById('clearPlanBtn').onclick = () => {
  if (!confirm('确定清空今日计划？')) return;
  planItems = []; savePlan(); renderPlan();
};
document.getElementById('planSaveBtn').onclick = async () => {
  await savePlan();
  toast('今日计划已保存');
};

// ===== 设置 =====
async function loadConfig() {
  const data = await api('/api/config');
  if (data.success) document.getElementById('keyInput').value = data.key || '';
  document.getElementById('keyStatus').textContent = (data.key) ? '已保存 Key ✓' : '尚未填写 Key，请先配置。';
}
document.getElementById('saveKeyBtn').onclick = async () => {
  const key = document.getElementById('keyInput').value.trim();
  const data = await api('/api/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ key }) });
  if (data.success) { document.getElementById('keyStatus').textContent = '已保存 Key ✓'; toast('Key 已保存'); }
};

document.getElementById('backupBtn').onclick = () => { window.location = '/api/backup'; };
document.getElementById('restoreBtn').onclick = async () => {
  const file = document.getElementById('restoreFile').files[0];
  if (!file) { toast('请先选择备份 zip 文件', true); return; }
  if (!confirm('恢复将覆盖当前数据（会先自动备份到 backups/）。确定继续？')) return;
  const buf = await file.arrayBuffer();
  try {
    const data = await api('/api/restore', { method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: buf });
    if (data.success) {
      document.getElementById('restoreStatus').textContent = '已恢复，数据已更新';
      toast('恢复成功');
      loadConfig(); loadHistory(); loadPlan();
    } else {
      toast(data.error || '恢复失败', true);
    }
  } catch (e) { toast('恢复失败：' + e.message, true); }
};

// ===== 初始化 =====
loadConfig();
loadHistory();
loadPlan();
