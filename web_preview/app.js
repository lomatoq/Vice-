const state = { files: [], zoom: 1, views: new Set(), jobs: new Map(), running: false };
const $ = selector => document.querySelector(selector);
const drop = $('#dropzone'), input = $('#fileInput'), extractor = $('#extractorSelect');
const smoothing = $('#smoothingSelect'), button = $('#processButton');
const previewButton = $('#previewButton');
const results = $('#results'), empty = $('#empty'), queue = $('#queue');

function addFiles(files) {
  state.files = [...files].filter(file => file.type.startsWith('image/'));
  const disabled = !state.files.length || state.running;
  button.disabled = disabled;
  previewButton.disabled = disabled;
  queue.hidden = !state.files.length && !state.jobs.size;
  if (!state.running) renderSelection();
}

function renderSelection() {
  queue.replaceChildren();
  if (!state.files.length) return;
  const row = document.createElement('div');
  row.className = 'selection-row';
  row.textContent = `${state.files.length} файл(аў): ${state.files.map(file => file.name).join(', ')}`;
  queue.append(row);
}

input.onchange = () => addFiles(input.files);
for (const event of ['dragenter', 'dragover']) drop.addEventListener(event, e => {
  e.preventDefault(); drop.classList.add('drag');
});
for (const event of ['dragleave', 'drop']) drop.addEventListener(event, e => {
  e.preventDefault(); drop.classList.remove('drag');
});
drop.addEventListener('drop', e => addFiles(e.dataTransfer.files));

const dataUrl = file => new Promise((resolve, reject) => {
  const reader = new FileReader();
  reader.onload = () => resolve(reader.result);
  reader.onerror = reject;
  reader.readAsDataURL(file);
});

function makeJobRow(file, runLabel) {
  const row = document.createElement('div');
  row.className = 'job-row';
  row.innerHTML = `<div class="job-copy"><strong></strong><span></span></div>
    <progress max="1" value="0"></progress><button type="button">Скасаваць</button>`;
  row.querySelector('strong').textContent = `${runLabel} · ${file.name}`;
  row.querySelector('span').textContent = 'Загрузка…';
  queue.append(row);
  return row;
}

function updateJobRow(row, job) {
  const labels = {
    queued: 'У чарзе — працуе адзін ізаляваны worker',
    running: `Вектарызацыя · ${job.elapsed_seconds || 0} с`,
    publishing: 'Атамарна публікую SVG…',
    completed: `Гатова · ${job.elapsed_seconds || 0} с`,
    failed: job.error || 'Worker завяршыўся з памылкай',
    cancelled: 'Скасавана',
  };
  row.dataset.status = job.status;
  row.querySelector('span').textContent = labels[job.status] || job.status;
  row.querySelector('progress').value = Number(job.progress || 0);
  row.querySelector('button').disabled = ['completed', 'failed', 'cancelled'].includes(job.status);
}

async function submitFile(file, smoothingValue, runLabel, routeValue, extractorValue) {
  const original = await dataUrl(file);
  const row = makeJobRow(file, runLabel);
  const response = await fetch('/api/process', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      filename: file.name, extractor: extractorValue,
      smoothing: smoothingValue, route: routeValue, data: original,
    }),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || !payload.job) throw new Error(payload.error || `HTTP ${response.status}`);
  const jobId = payload.job.id;
  state.jobs.set(jobId, { file, original, runLabel, row });
  row.querySelector('button').onclick = async () => {
    row.querySelector('button').disabled = true;
    try {
      const cancel = await fetch(`/api/jobs/${jobId}`, { method: 'DELETE' });
      const body = await cancel.json();
      if (body.job) updateJobRow(row, body.job);
    } catch (error) {
      row.querySelector('span').textContent = `Не ўдалося скасаваць: ${error.message}`;
    }
  };
  updateJobRow(row, payload.job);
  return waitForJob(jobId);
}

async function waitForJob(jobId) {
  const local = state.jobs.get(jobId);
  let networkMisses = 0;
  while (true) {
    try {
      const response = await fetch(`/api/jobs/${jobId}`, { cache: 'no-store' });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || !payload.job) throw new Error(payload.error || `HTTP ${response.status}`);
      networkMisses = 0;
      updateJobRow(local.row, payload.job);
      if (payload.job.status === 'completed') {
        addResult(local.file.name, local.original, payload.job, local.runLabel);
        return;
      }
      if (payload.job.status === 'failed') throw new Error(payload.job.error || 'Worker failed');
      if (payload.job.status === 'cancelled') return;
    } catch (error) {
      networkMisses += 1;
      if (networkMisses >= 6) throw error;
      local.row.querySelector('span').textContent = `Сувязь аднаўляецца (${networkMisses}/6)…`;
    }
    await new Promise(resolve => setTimeout(resolve, 700));
  }
}

async function runFiles(smoothingValue, runLabel, activeButton, routeValue, extractorValue) {
  state.running = true;
  button.disabled = true; previewButton.disabled = true;
  const oldLabel = activeButton.textContent;
  activeButton.textContent = runLabel === 'Best' ? 'Ствараю Best SVG…' : 'Ствараю хуткі draft…';
  empty.hidden = true;
  queue.hidden = false;
  queue.replaceChildren();
  const promises = state.files.map(async file => {
    try {
      await submitFile(file, smoothingValue, runLabel, routeValue, extractorValue);
    } catch (error) {
      const job = [...state.jobs.values()].find(item => item.file === file);
      if (job) {
        job.row.dataset.status = 'failed';
        job.row.querySelector('span').textContent = error.message;
      } else {
        const row = makeJobRow(file, runLabel);
        row.dataset.status = 'failed';
        row.querySelector('span').textContent = error.message;
        row.querySelector('button').disabled = true;
      }
    }
  });
  await Promise.all(promises);
  state.running = false;
  button.disabled = !state.files.length;
  previewButton.disabled = !state.files.length;
  activeButton.textContent = oldLabel;
}

button.onclick = () => runFiles(smoothing.value, 'Best', button, 'auto', extractor.value);
previewButton.onclick = () => runFiles('cad', 'Fast draft', previewButton, 'preview', 'palette');

function addResult(name, original, payload, runLabel) {
  const fragment = $('#resultTemplate').content.cloneNode(true);
  const card = fragment.querySelector('.result-card'), report = payload.report || {};
  card.querySelector('h2').textContent = name;
  const wall = report.resource?.wall_seconds;
  card.querySelector('.meta').textContent = [
    runLabel, report.extractor_used, report.analysis_scale ? `${report.analysis_scale}×` : null,
    Number.isFinite(report.regions) ? `${report.regions} рэгіёнаў` : null,
    Number.isFinite(report.rendered_primitive_count) ? `${report.rendered_primitive_count} прымітываў` : null,
    Number.isFinite(wall) ? `${wall.toFixed(1)} с` : null,
  ].filter(Boolean).join(' · ');
  const status = card.querySelector('.status');
  if (report.abstained) {
    status.textContent = `трэба праверыць · ${(report.abstain_reasons || []).join(', ')}`;
    status.classList.add('warning');
  }
  card.querySelector('[data-view="original"]').src = original;
  for (const key of ['contour', 'primitiveMap', 'rebuilt', 'corners']) {
    const img = card.querySelector(`[data-view="${key}"]`);
    if (!img) continue;
    if (payload.assets?.[key]) {
      img.src = `${payload.assets[key]}?t=${Date.now()}`;
      img.onerror = () => {
        status.textContent = `не загрузіўся asset: ${key}`;
        status.classList.add('warning');
      };
    } else img.closest('figure').style.display = 'none';
  }
  const download = card.querySelector('[data-download="svg"]');
  download.href = payload.assets.rebuilt;
  download.download = `${name.replace(/\.[^.]+$/, '')}.svg`;
  const actual = Object.entries(report.actual || {});
  const templates = Object.entries(report.templates || {});
  card.querySelector('.counts').innerHTML = actual.map(([key, value]) =>
    `<span><b>${key}</b> ${value}</span>`).join('') + templates.map(([key, value]) =>
    `<span>${key} <b>${value}</b></span>`).join('');
  results.prepend(card);
  card.querySelectorAll('.viewport').forEach(setupViewport);
  applyZoom();
}

function setupViewport(view) {
  const img = view.querySelector('img');
  const item = { el: view, img, x: 0, y: 0, drag: false, lastX: 0, lastY: 0 };
  state.views.add(item);
  img.onload = () => position(item);
  view.onpointerdown = e => {
    item.drag = true; item.lastX = e.clientX; item.lastY = e.clientY;
    view.setPointerCapture(e.pointerId);
  };
  view.onpointermove = e => {
    if (!item.drag) return;
    item.x += e.clientX - item.lastX; item.y += e.clientY - item.lastY;
    item.lastX = e.clientX; item.lastY = e.clientY; position(item);
  };
  view.onpointerup = () => { item.drag = false; };
  view.onwheel = e => {
    e.preventDefault(); setZoom(state.zoom * (e.deltaY < 0 ? 1.12 : 0.89));
  };
  view.ondblclick = () => { item.x = 0; item.y = 0; setZoom(1); };
}

function position(item) {
  item.img.style.transform = `translate(calc(-50% + ${item.x}px), calc(-50% + ${item.y}px)) scale(${state.zoom})`;
}
function setZoom(value) {
  state.zoom = Math.max(.25, Math.min(8, value));
  $('#zoomSlider').value = Math.round(state.zoom * 100);
  $('#resetView').textContent = `${Math.round(state.zoom * 100)}%`;
  applyZoom();
}
function applyZoom() { state.views.forEach(position); }
$('#zoomSlider').oninput = e => setZoom(+e.target.value / 100);
$('#zoomIn').onclick = () => setZoom(state.zoom * 1.25);
$('#zoomOut').onclick = () => setZoom(state.zoom * .8);
$('#resetView').onclick = () => {
  state.views.forEach(item => { item.x = 0; item.y = 0; }); setZoom(1);
};
