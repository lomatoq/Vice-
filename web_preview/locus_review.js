const state = {
  all: [], rows: [], index: 0, targets: {}, counts: {}, mask: null,
  drawMode: 'paint', drawing: false, renderPending: false,
  maskDirty: false, reviewDirty: false, imageLoadToken: 0, preload: null,
  proposalInstances: [], activeProposalInstance: -1, rootDraft: null
};
const $ = id => document.getElementById(id);

function current() { return state.rows[state.index]; }
function reviewStatus(row) { return row.review?.status || 'pending_review'; }
function proposalFamilies(row) {
  const values = new Set();
  if (row.review?.proposal_family) values.add(row.review.proposal_family);
  for (const instance of (row.review?.proposal_instances || [])) {
    if (instance.proposal_family) values.add(instance.proposal_family);
  }
  return values;
}
function markUnsaved(message = 'ёсць незахаваныя змены') {
  state.reviewDirty = true;
  $('message').textContent = message;
  $('message').className = '';
}
function applyFilters() {
  const semanticClass = $('classFilter').value;
  const status = $('statusFilter').value;
  const proposal = $('proposalFilter').value;
  state.rows = state.all.filter(row =>
    (!semanticClass || row.semantic_class === semanticClass)
    && (!status || reviewStatus(row) === status)
    && (!proposal
      || (proposal === 'missing' && proposalFamilies(row).size === 0)
      || proposalFamilies(row).has(proposal))
  );
  const requestedId = new URLSearchParams(location.search).get('id');
  const resumeId = requestedId || localStorage.getItem('pcdc-last-locus-id');
  const resumeIndex = state.rows.findIndex(row => row.id === resumeId);
  state.index = resumeIndex >= 0 ? resumeIndex : 0;
  show();
}
function parseRoi(value) {
  const parts = value.split(/[,\s]+/).filter(Boolean).map(Number);
  if (parts.length !== 4 || parts.some(v => !Number.isInteger(v))) throw new Error('ROI: патрэбны 4 цэлыя лікі');
  return parts;
}
function numberValue(id) {
  if ($(id).value === '') throw new Error(`${id}: поле абавязковае`);
  const value = Number($(id).value);
  if (!Number.isInteger(value) || value < 0) throw new Error(`${id}: патрэбны цэлы лік ≥ 0`);
  return value;
}
function updateStats() {
  const c = state.counts;
  const typed = state.all.filter(row => proposalFamilies(row).size > 0).length;
  const instances = state.all.reduce(
    (count, row) => count + (row.review?.proposal_instances || []).length, 0
  );
  $('stats').textContent = `complete ${c.complete || 0}/300 · typed loci ${typed}/300 · query instances ${instances} · GT ${c.ground_truth_derived || 0} · human ${c.evidence_reviewed || 0} · pending ${c.pending_review || 0}`;
}
function setZoom(value) {
  const row = current();
  if (!row) return;
  const zoom = Number(value);
  $('zoom').value = String(zoom);
  $('imageStage').style.width = `${row.image.width * zoom}px`;
  $('imageStage').style.height = `${row.image.height * zoom}px`;
}
function fitZoom() {
  const row = current(), viewport = $('viewport');
  if (!row || !viewport) return;
  const scale = Math.min(
    (viewport.clientWidth - 56) / row.image.width,
    (viewport.clientHeight - 56) / row.image.height
  );
  setZoom(Math.max(0.1, Math.min(12, Math.floor(scale * 10) / 10)));
}
function decodeRle(runs, size) {
  const mask = new Uint8Array(size);
  for (const [start, length] of (runs || [])) mask.fill(1, start, start + length);
  return mask;
}
function encodeRle(mask) {
  const runs = [];
  for (let index = 0; index < mask.length;) {
    if (!mask[index]) { index++; continue; }
    const start = index; while (index < mask.length && mask[index]) index++;
    runs.push([start, index - start]);
  }
  return runs;
}
const RELATION_PRESETS = {
  text_group: {
    positive: ['same_group', 'text_membership'],
    observable: ['same_group', 'text_membership']
  },
  repeat: {
    positive: ['same_group', 'repeat'],
    observable: ['same_group', 'repeat', 'mirror']
  },
  mirror: {
    positive: ['same_group', 'mirror'],
    observable: ['same_group', 'repeat', 'mirror']
  },
  layer_order: {
    positive: ['same_group', 'front_of', 'behind'],
    observable: ['same_group', 'front_of', 'behind']
  },
  appearance: {
    positive: ['same_appearance'], observable: ['same_appearance']
  },
  stroke: {
    positive: ['same_group', 'stroke_membership'],
    observable: ['same_group', 'stroke_membership']
  }
};
function relationContract(family) {
  const preset = RELATION_PRESETS[$('relationEvidence').value];
  return preset ? {
    schema: 'query-relations/v1', family,
    positive: [...preset.positive], observable: [...preset.observable]
  } : null;
}
function relationPreset(contract) {
  if (!contract) return '';
  const encoded = JSON.stringify({
    positive: contract.positive || [], observable: contract.observable || []
  });
  return Object.entries(RELATION_PRESETS).find(([, value]) =>
    JSON.stringify(value) === encoded
  )?.[0] || '';
}
function captureEditor() {
  return {
    reviewer: $('reviewer').value.trim() || 'local-human',
    roi_xyxy: parseRoi($('roi').value),
    components: numberValue('components'), holes: numberValue('holes'),
    acceptable_support: $('support').value.trim(),
    macro_family: $('macro').value,
    proposal_family: $('proposalFamily').value,
    support_rle: encodeRle(state.mask || new Uint8Array()),
    text_line_membership: $('textLine').value,
    layer_relation: $('layer').value,
    status: $('status').value,
    preferred_candidate: $('preference').value.trim(),
    notes: $('notes').value.trim()
  };
}
function instanceFromEditor(id) {
  const draft = captureEditor();
  if (!draft.proposal_family) throw new Error('Абяры ProposalNet family для instance');
  if (!draft.support_rle.length || draft.components < 1) {
    throw new Error('Proposal instance патрабуе бачную непустую маску');
  }
  return {
    id, status: draft.status, roi_xyxy: draft.roi_xyxy,
    support_rle: draft.support_rle, components: draft.components,
    holes: draft.holes, proposal_family: draft.proposal_family,
    text_line_membership: draft.text_line_membership,
    layer_relation: draft.layer_relation,
    relation_contract: relationContract(draft.proposal_family),
    notes: draft.notes
  };
}
function applyEditor(draft) {
  const row = current(); if (!row || !draft) return;
  const root = state.rootDraft || {};
  const value = {...root, ...draft};
  $('roi').value = (value.roi_xyxy || [0,0,row.image.width,row.image.height]).join(',');
  $('components').value = value.components ?? '';
  $('holes').value = value.holes ?? '';
  $('support').value = value.acceptable_support || '';
  $('macro').value = value.macro_family || row.machine_suggestion.macro_family;
  $('proposalFamily').value = value.proposal_family || '';
  $('textLine').value = value.text_line_membership || 'not_applicable';
  $('layer').value = value.layer_relation || 'none';
  $('status').value = value.status || 'evidence_reviewed';
  $('preference').value = value.preferred_candidate || '';
  $('notes').value = value.notes || '';
  $('reviewer').value = value.reviewer || 'local-human';
  $('relationEvidence').value = relationPreset(value.relation_contract);
  state.mask = decodeRle(value.support_rle || [], row.image.width * row.image.height);
  renderMask();
  syncMaskFields();
}
function refreshProposalInstances() {
  const select = $('proposalInstance');
  select.textContent = '';
  const root = document.createElement('option');
  root.value = '-1'; root.textContent = 'root review'; select.append(root);
  state.proposalInstances.forEach((instance, index) => {
    const option = document.createElement('option');
    option.value = String(index);
    option.textContent = `${index + 1}. ${instance.proposal_family} · ${instance.id}`;
    select.append(option);
  });
  select.value = String(state.activeProposalInstance);
  $('updateProposalInstance').disabled = state.activeProposalInstance < 0;
  $('deleteProposalInstance').disabled = state.activeProposalInstance < 0;
}
function persistActiveEditor() {
  if (state.activeProposalInstance < 0) {
    state.rootDraft = captureEditor();
    return;
  }
  const previous = state.proposalInstances[state.activeProposalInstance];
  state.proposalInstances[state.activeProposalInstance] =
    instanceFromEditor(previous.id);
}
function selectProposalInstance(index) {
  if (!state.rootDraft) return;
  persistActiveEditor();
  state.activeProposalInstance = index;
  applyEditor(index < 0 ? state.rootDraft : state.proposalInstances[index]);
  refreshProposalInstances();
}
function addProposalInstance() {
  try {
    persistActiveEditor();
    const family = $('proposalFamily').value;
    let suffix = state.proposalInstances.length + 1;
    let id = `${family || 'query'}-${suffix}`;
    const used = new Set(state.proposalInstances.map(row => row.id));
    while (used.has(id)) id = `${family || 'query'}-${++suffix}`;
    const instance = instanceFromEditor(id);
    state.proposalInstances.push(instance);
    state.activeProposalInstance = state.proposalInstances.length - 1;
    refreshProposalInstances();
    markUnsaved(`instance ${id} дададзены · захавай locus`);
  } catch (error) { $('message').textContent = error.message; }
}
function updateProposalInstance() {
  try {
    if (state.activeProposalInstance < 0) throw new Error('Спачатку абяры instance');
    persistActiveEditor();
    refreshProposalInstances();
    markUnsaved('Proposal instance абноўлены · захавай locus');
  } catch (error) { $('message').textContent = error.message; }
}
function deleteProposalInstance() {
  if (state.activeProposalInstance < 0) return;
  const deleted = state.proposalInstances.splice(state.activeProposalInstance, 1)[0];
  state.activeProposalInstance = -1;
  applyEditor(state.rootDraft);
  refreshProposalInstances();
  markUnsaved(`instance ${deleted.id} выдалены · захавай locus`);
}
function renderMask() {
  const row = current(), canvas = $('supportCanvas'); if (!row || !state.mask) return;
  const context = canvas.getContext('2d'), image = context.createImageData(row.image.width, row.image.height);
  for (let i = 0; i < state.mask.length; i++) if (state.mask[i]) { const p=i*4; image.data[p]=255; image.data[p+1]=0; image.data[p+2]=190; image.data[p+3]=110; }
  context.putImageData(image,0,0);
}
function scheduleMaskRender() {
  if (state.renderPending) return;
  state.renderPending = true;
  requestAnimationFrame(() => {
    state.renderPending = false;
    renderMask();
  });
}
function maskStats(mask, width, height) {
  const size = width * height;
  let area = 0, minX = width, minY = height, maxX = -1, maxY = -1;
  for (let index = 0; index < size; index++) {
    if (!mask[index]) continue;
    area++;
    const x = index % width, y = Math.floor(index / width);
    if (x < minX) minX = x; if (x > maxX) maxX = x;
    if (y < minY) minY = y; if (y > maxY) maxY = y;
  }
  const queue = new Int32Array(size);
  const foregroundSeen = new Uint8Array(size);
  let components = 0;
  for (let seed = 0; seed < size; seed++) {
    if (!mask[seed] || foregroundSeen[seed]) continue;
    components++;
    let head = 0, tail = 0; queue[tail++] = seed; foregroundSeen[seed] = 1;
    while (head < tail) {
      const index = queue[head++], x = index % width, y = Math.floor(index / width);
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
        if ((!dx && !dy) || x + dx < 0 || x + dx >= width || y + dy < 0 || y + dy >= height) continue;
        const next = (y + dy) * width + x + dx;
        if (mask[next] && !foregroundSeen[next]) { foregroundSeen[next] = 1; queue[tail++] = next; }
      }
    }
  }
  const backgroundSeen = new Uint8Array(size);
  const neighbours4 = [[-1,0],[1,0],[0,-1],[0,1]];
  let holes = 0;
  for (let seed = 0; seed < size; seed++) {
    if (mask[seed] || backgroundSeen[seed]) continue;
    let head = 0, tail = 0, touchesBorder = false;
    queue[tail++] = seed; backgroundSeen[seed] = 1;
    while (head < tail) {
      const index = queue[head++], x = index % width, y = Math.floor(index / width);
      if (x === 0 || y === 0 || x === width - 1 || y === height - 1) touchesBorder = true;
      for (const [dx, dy] of neighbours4) {
        const nx = x + dx, ny = y + dy;
        if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue;
        const next = ny * width + nx;
        if (!mask[next] && !backgroundSeen[next]) { backgroundSeen[next] = 1; queue[tail++] = next; }
      }
    }
    if (!touchesBorder) holes++;
  }
  return {
    area, components, holes,
    roi: area ? [minX, minY, maxX + 1, maxY + 1] : [0, 0, width, height]
  };
}
function syncMaskFields() {
  const row = current();
  if (!row || !state.mask) return;
  const stats = maskStats(state.mask, row.image.width, row.image.height);
  $('roi').value = stats.roi.join(',');
  $('components').value = String(stats.components);
  $('holes').value = String(stats.holes);
  $('maskInfo').textContent = `support ${stats.area}px · ${stats.components} components · ${stats.holes} holes`;
  state.maskDirty = false;
}
function otsuThreshold(histogram, total) {
  let sum = 0;
  for (let value = 0; value < 256; value++) sum += value * histogram[value];
  let backgroundWeight = 0, backgroundSum = 0, best = 16, bestVariance = -1;
  for (let value = 0; value < 256; value++) {
    backgroundWeight += histogram[value];
    if (!backgroundWeight) continue;
    const foregroundWeight = total - backgroundWeight;
    if (!foregroundWeight) break;
    backgroundSum += value * histogram[value];
    const meanBackground = backgroundSum / backgroundWeight;
    const meanForeground = (sum - backgroundSum) / foregroundWeight;
    const variance = backgroundWeight * foregroundWeight * (meanBackground - meanForeground) ** 2;
    if (variance > bestVariance) { bestVariance = variance; best = value; }
  }
  return Math.max(4, Math.min(96, best));
}
function autoMask(userTriggered = true) {
  const row=current(), canvas=document.createElement('canvas'); canvas.width=row.image.width; canvas.height=row.image.height;
  const context=canvas.getContext('2d'); context.drawImage($('source'),0,0); const pixels=context.getImageData(0,0,canvas.width,canvas.height).data;
  const colourCounts=new Uint32Array(4096), colourR=new Float64Array(4096), colourG=new Float64Array(4096), colourB=new Float64Array(4096);
  let alphaMin=255, alphaMax=0, dominantKey=0;
  for(let i=0;i<canvas.width*canvas.height;i++){
    const p=i*4,alpha=pixels[p+3];alphaMin=Math.min(alphaMin,alpha);alphaMax=Math.max(alphaMax,alpha);
    if(alpha<=16)continue;
    const key=(pixels[p]>>4)*256+(pixels[p+1]>>4)*16+(pixels[p+2]>>4);
    colourCounts[key]++;colourR[key]+=pixels[p];colourG[key]+=pixels[p+1];colourB[key]+=pixels[p+2];
    if(colourCounts[key]>colourCounts[dominantKey])dominantKey=key;
  }
  const dominantCount=Math.max(1,colourCounts[dominantKey]);
  const bg=[colourR[dominantKey]/dominantCount,colourG[dominantKey]/dominantCount,colourB[dominantKey]/dominantCount];
  const distances=new Uint8Array(canvas.width*canvas.height), histogram=new Uint32Array(256);
  for(let i=0;i<distances.length;i++){
    const p=i*4,d=Math.max(Math.abs(pixels[p]-bg[0]),Math.abs(pixels[p+1]-bg[1]),Math.abs(pixels[p+2]-bg[2]));
    distances[i]=d;histogram[d]++;
  }
  const threshold=otsuThreshold(histogram,distances.length), useAlpha=alphaMax-alphaMin>8;
  state.mask=new Uint8Array(canvas.width*canvas.height);
  for(let i=0;i<state.mask.length;i++){
    const alpha=pixels[i*4+3];
    state.mask[i]=(alpha>16&&(useAlpha||distances[i]>threshold))?1:0;
  }
  renderMask(); syncMaskFields();
  if (userTriggered) markUnsaved('аўтамаска зменена · правер і захавай');
}
function invertMask() {
  if (!state.mask) return;
  for (let index = 0; index < state.mask.length; index++) state.mask[index] = state.mask[index] ? 0 : 1;
  renderMask();
  syncMaskFields();
  markUnsaved('маска інвертаваная · правер і захавай');
}
function clearMask() {
  if (!state.mask) return;
  state.mask.fill(0);
  renderMask();
  syncMaskFields();
  markUnsaved('маска ачышчаная · правер і захавай');
}
function paintAt(event) {
  if (!state.drawing || !state.mask) return; const row=current(), rect=$('supportCanvas').getBoundingClientRect();
  const cx=(event.clientX-rect.left)*row.image.width/rect.width, cy=(event.clientY-rect.top)*row.image.height/rect.height, radius=Math.max(0.5,Number($('brush').value)/2);
  const x0=Math.max(0,Math.floor(cx-radius)),x1=Math.min(row.image.width-1,Math.ceil(cx+radius)),y0=Math.max(0,Math.floor(cy-radius)),y1=Math.min(row.image.height-1,Math.ceil(cy+radius));
  const centreX=Math.max(0,Math.min(row.image.width-1,Math.floor(cx))), centreY=Math.max(0,Math.min(row.image.height-1,Math.floor(cy)));
  const nextValue=state.drawMode==='paint'?1:0;
  let changed=false;
  for(let y=y0;y<=y1;y++)for(let x=x0;x<=x1;x++){
    const inside=(x+0.5-cx)**2+(y+0.5-cy)**2<=radius**2 || (x===centreX&&y===centreY);
    const index=y*row.image.width+x;
    if(inside&&state.mask[index]!==nextValue){state.mask[index]=nextValue;changed=true;}
  }
  if(!changed)return;
  state.maskDirty = true; markUnsaved('маска адрэдагаваная · захавай змены'); scheduleMaskRender();
}
function preloadNext() {
  const next = state.rows[state.index + 1];
  if (!next) { state.preload = null; return; }
  state.preload = new Image();
  state.preload.src = `${next.source_url}?v=${next.source.sha256.slice(0, 12)}`;
}
function show() {
  const row = current();
  if (!row) {
    $('meta').textContent = 'Няма loci для гэтага фільтра';
    $('source').removeAttribute('src');
    return;
  }
  localStorage.setItem('pcdc-last-locus-id', row.id);
  $('position').textContent = `${state.index + 1} / ${state.rows.length}`;
  const loadToken = ++state.imageLoadToken;
  state.mask = null; state.maskDirty = false; state.reviewDirty = false; $('maskInfo').textContent = 'loading support…';
  state.proposalInstances = structuredClone(row.review?.proposal_instances || []);
  state.activeProposalInstance = -1;
  state.rootDraft = null;
  refreshProposalInstances();
  $('source').onload = () => {
    if (loadToken !== state.imageLoadToken || current()?.id !== row.id) return;
    const canvas=$('supportCanvas'); canvas.width=row.image.width;canvas.height=row.image.height;
    if(row.review?.support_rle){
      state.mask=decodeRle(row.review.support_rle,row.image.width*row.image.height);renderMask();
      const area = row.review.support_area || state.mask.reduce((a,b)=>a+b,0);
      $('maskInfo').textContent = `support ${area}px · ${row.review.components} components · ${row.review.holes} holes`;
    }else autoMask(false);
    state.rootDraft = captureEditor();
    refreshProposalInstances();
    preloadNext();
  };
  $('source').src = `${row.source_url}?v=${row.source.sha256.slice(0, 12)}`;
  $('meta').textContent = `${row.id} · ${row.semantic_class} · ${row.image.width}×${row.image.height} · ${row.source.origin}/${row.source.category}`;
  const review = row.review || {};
  const suggestion = row.machine_suggestion;
  $('roi').value = (review.roi_xyxy || suggestion.roi_xyxy).join(',');
  $('components').value = review.components ?? '';
  $('holes').value = review.holes ?? '';
  $('support').value = review.acceptable_support || '';
  $('macro').value = review.macro_family || suggestion.macro_family;
  $('proposalFamily').value = review.proposal_family || '';
  $('relationEvidence').value = '';
  $('textLine').value = review.text_line_membership || (suggestion.text_line_membership === 'yes' ? 'yes' : 'not_applicable');
  $('layer').value = review.layer_relation || 'none';
  $('status').value = review.status || 'evidence_reviewed';
  $('preference').value = review.preferred_candidate || '';
  $('notes').value = review.notes || '';
  $('reviewer').value = review.reviewer || localStorage.getItem('pcdc-reviewer') || 'local-human';
  $('message').textContent = review.status ? `захавана: ${review.status}` : 'pending human review';
  $('message').className = review.status === 'complete' ? 'complete' : '';
  const viewport = $('viewport');
  if (row.image.width > viewport.clientWidth || row.image.height > viewport.clientHeight) {
    setTimeout(fitZoom, 0);
  } else {
    setZoom(Number($('zoom').value) < 1 ? 4 : $('zoom').value);
  }
  $('prev').disabled = state.index === 0;
  $('next').disabled = state.index >= state.rows.length - 1;
}
function move(delta) {
  state.index = Math.max(0, Math.min(state.rows.length - 1, state.index + delta));
  show();
}
async function load() {
  const response = await fetch('/api/locus-corpus');
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || 'Failed to load corpus');
  state.all = payload.loci;
  state.rows = payload.loci;
  state.targets = payload.targets;
  state.counts = payload.review_counts;
  for (const [name, count] of Object.entries(payload.targets)) {
    const option = document.createElement('option'); option.value = name; option.textContent = `${name} (${count})`; $('classFilter').append(option);
  }
  updateStats(); applyFilters();
}
async function save() {
  const row = current();
  if (!row) return;
  $('message').textContent = 'захоўваю…';
  try {
    if (state.maskDirty) syncMaskFields();
    const reviewer = $('reviewer').value.trim() || 'local-human';
    localStorage.setItem('pcdc-reviewer', reviewer);
    persistActiveEditor();
    const review = {...state.rootDraft, reviewer};
    if (state.proposalInstances.length) {
      review.proposal_instances = state.proposalInstances;
    }
    const response = await fetch('/api/locus-review', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id:row.id, review}) });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || 'Save failed');
    row.review = payload.review;
    state.reviewDirty = false;
    state.counts = payload.review_counts;
    updateStats();
    $('message').textContent = 'захавана'; $('message').className = 'complete';
    setTimeout(() => {
      const statusFilter = $('statusFilter').value;
      const proposalFilter = $('proposalFilter').value;
      const leavesStatus = statusFilter && reviewStatus(row) !== statusFilter;
      const leavesProposal = proposalFilter && (
        (proposalFilter === 'missing' && proposalFamilies(row).size > 0)
        || (proposalFilter !== 'missing'
          && !proposalFamilies(row).has(proposalFilter))
      );
      if (leavesStatus || leavesProposal) {
        state.rows.splice(state.index, 1);
        state.index = Math.min(state.index, Math.max(0, state.rows.length - 1));
        show();
      } else move(1);
    }, 180);
  } catch (error) { $('message').textContent = error.message; $('message').className = ''; }
}

$('prev').onclick = () => move(-1); $('next').onclick = () => move(1); $('skip').onclick = () => move(1); $('save').onclick = save;
$('zoom').oninput = event => setZoom(event.target.value); $('native').onclick = () => setZoom(1); $('fit').onclick = fitZoom;
$('paint').onclick=()=>{state.drawMode='paint';$('paint').className='primary';$('erase').className='';}; $('erase').onclick=()=>{state.drawMode='erase';$('erase').className='primary';$('paint').className='';};
$('autoMask').onclick=()=>autoMask(true); $('invertMask').onclick=invertMask; $('clearMask').onclick=clearMask;
$('proposalInstance').onchange = event => selectProposalInstance(Number(event.target.value));
$('addProposalInstance').onclick = addProposalInstance;
$('updateProposalInstance').onclick = updateProposalInstance;
$('deleteProposalInstance').onclick = deleteProposalInstance;
const maskCanvas=$('supportCanvas'); maskCanvas.onpointerdown=e=>{state.drawing=true;maskCanvas.setPointerCapture(e.pointerId);paintAt(e);}; maskCanvas.onpointermove=paintAt; maskCanvas.onpointerup=()=>{state.drawing=false;if(state.maskDirty)syncMaskFields();}; maskCanvas.onpointercancel=()=>{state.drawing=false;if(state.maskDirty)syncMaskFields();};
$('classFilter').onchange = applyFilters;
$('statusFilter').onchange = applyFilters;
$('proposalFilter').onchange = applyFilters;
$('editReviewed').onclick = () => { $('statusFilter').value = 'evidence_reviewed'; applyFilters(); };
for (const field of document.querySelectorAll('aside input, aside textarea, aside select')) {
  field.addEventListener('change', () => markUnsaved('палі адрэдагаваныя · захавай змены'));
}
window.addEventListener('beforeunload', event => {
  if (!state.reviewDirty) return;
  event.preventDefault();
  event.returnValue = '';
});
document.addEventListener('keydown', event => {
  if (event.ctrlKey && event.key === 'Enter') { event.preventDefault(); save(); return; }
  if (event.ctrlKey || event.metaKey || event.altKey) return;
  const target = event.target;
  const typing = target.tagName === 'TEXTAREA'
    || target.tagName === 'SELECT'
    || (target.tagName === 'INPUT' && target.type !== 'range');
  if (typing) return;
  const physicalShortcut = {KeyA:'a', KeyB:'b', KeyE:'e', KeyI:'i'}[event.code];
  const key = physicalShortcut || event.key.toLowerCase();
  if (key === 'a') autoMask(true);
  else if (key === 'i') invertMask();
  else if (key === 'b') $('paint').click();
  else if (key === 'e') $('erase').click();
  else if (key === 'arrowleft') move(-1);
  else if (key === 'arrowright' || key === ' ') { event.preventDefault(); move(1); }
  else return;
  event.preventDefault();
});
load().catch(error => { $('message').textContent = error.message; });
