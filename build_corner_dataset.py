"""Build a reviewable, multi-resolution SVG corner dataset.

Example pilot:
    python build_corner_dataset.py --files 80 --preview-files 80

The compact NPZ shards are ready for the 1-D boundary CNN.  The web review is
served by the existing preview server at http://localhost:8877/corner-dataset/.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import html
import json
from pathlib import Path
import random
import shutil

import numpy as np

from svg_corner_gt import (
    LABEL_OCCLUSION,
    LABEL_STRUCTURAL,
    UnsupportedSvg,
    EVENT_SHORT_SPAN,
    frame_loop_examples,
    infer_corner_events,
    render_frame_base,
    visible_svg_regions,
)


ROOT = Path(__file__).resolve().parent
DEFAULT_ROOTS = [
    Path(r"C:/Users/nirrt/Toolset/v-ize train/dataset/icons/local"),
    Path(r"C:/Users/nirrt/Toolset/v-ice pictures/ground truth"),
    Path(r"C:/Users/nirrt/Toolset/v-ize train/dataset/icons/iconify"),
]
DEFAULT_OUT = ROOT / "datasets" / "corner_gt_v4_svg_events"
DEFAULT_PREVIEW = ROOT / "web_preview" / "corner-dataset-v4-svg"


class ShardWriter:
    def __init__(self, root: Path, loops_per_shard: int = 1800):
        self.root = root
        self.loops_per_shard = loops_per_shard
        self.shards: list[dict] = []
        self.clear()

    def clear(self) -> None:
        self.points: list[np.ndarray] = []
        self.labels: list[np.ndarray] = []
        self.event_ids: list[np.ndarray] = []
        self.event_kinds: list[np.ndarray] = []
        self.file_index: list[int] = []
        self.resolution: list[int] = []
        self.region_index: list[int] = []
        self.loop_index: list[int] = []

    def add(self, points: np.ndarray, labels: np.ndarray, file_index: int,
            resolution: int, region_index: int, loop_index: int,
            event_ids: np.ndarray | None = None,
            event_kinds: np.ndarray | None = None) -> None:
        if event_ids is None or event_kinds is None:
            event_ids, event_kinds = infer_corner_events(points, labels)
        self.points.append(points.astype(np.float32))
        self.labels.append(labels.astype(np.uint8))
        self.event_ids.append(event_ids.astype(np.int32))
        self.event_kinds.append(event_kinds.astype(np.uint8))
        self.file_index.append(file_index)
        self.resolution.append(resolution)
        self.region_index.append(region_index)
        self.loop_index.append(loop_index)
        if len(self.points) >= self.loops_per_shard:
            self.flush()

    def flush(self) -> None:
        if not self.points:
            return
        lengths = np.asarray([len(points) for points in self.points], dtype=np.int64)
        offsets = np.concatenate(([0], np.cumsum(lengths)))
        points = np.concatenate(self.points, axis=0)
        labels = np.concatenate(self.labels, axis=0)
        event_ids = np.concatenate(self.event_ids, axis=0)
        event_kinds = np.concatenate(self.event_kinds, axis=0)
        name = f"shard_{len(self.shards):04d}.npz"
        np.savez_compressed(
            self.root / name,
            points=points,
            labels=labels,
            event_ids=event_ids,
            event_kinds=event_kinds,
            offsets=offsets,
            file_index=np.asarray(self.file_index, dtype=np.uint32),
            resolution=np.asarray(self.resolution, dtype=np.uint16),
            region_index=np.asarray(self.region_index, dtype=np.uint16),
            loop_index=np.asarray(self.loop_index, dtype=np.uint16),
        )
        event_count = sum(len(set(ids[ids >= 0].tolist())) for ids in self.event_ids)
        short_spans = sum(len(set(ids[kinds == EVENT_SHORT_SPAN].tolist()))
                          for ids, kinds in zip(self.event_ids, self.event_kinds))
        self.shards.append({
            "file": name,
            "loops": len(lengths),
            "vertices": int(len(points)),
            "corners": int(np.count_nonzero(labels)),
            "events": int(event_count),
            "short_spans": int(short_spans),
        })
        self.clear()


def _split(path: Path) -> str:
    # Generated corpora may provide an explicit file-level split directory.
    # Respect it so all raster resolutions of one analytic primitive stay in
    # the same partition and a rebuild is independent of the absolute root.
    for part in reversed(path.parts[:-1]):
        lowered = part.lower()
        if lowered in {"train", "val", "test"}:
            return lowered
    value = int(hashlib.sha1(str(path).lower().encode("utf-8")).hexdigest()[:8], 16) % 100
    return "train" if value < 80 else "val" if value < 90 else "test"


def _safe_stem(path: Path, index: int) -> str:
    clean = "".join(char if char.isalnum() or char in "-_" else "_" for char in path.stem)
    return f"{index:05d}_{clean[:70]}"


def _write_review(preview: Path, entries: list[dict], summary: dict, dataset_name: str) -> None:
    (preview / "manifest.json").write_text(
        json.dumps({"dataset": dataset_name, "summary": summary, "entries": entries},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    page = r'''<!doctype html>
<html lang="be"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Corner GT review</title><style>
:root{color-scheme:dark;font-family:Inter,Segoe UI,sans-serif;background:#11151b;color:#e8edf5}
body{margin:0}.top{position:sticky;top:0;z-index:4;background:#11151bf2;border-bottom:1px solid #303744;padding:12px 18px}
.top h1{font-size:17px;margin:0 0 8px}.bar{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
button,select{background:#202733;color:#e8edf5;border:1px solid #3d4858;border-radius:7px;padding:7px 10px}button.active{border-color:#4d9cff;background:#18365c}button:disabled{opacity:.35;cursor:not-allowed}
.legend{margin-left:auto;font-size:12px;color:#aeb8c7}.s{color:#ff4545}.o{color:#ff2bda}
#grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(440px,1fr));gap:12px;padding:12px}
.card{background:#181e27;border:1px solid #303946;border-radius:10px;padding:10px}.card.rejected{opacity:.38}.card.approved{border-color:#2f9b65}
.card.expanded{position:fixed;inset:8px;z-index:20;overflow:auto;opacity:1!important;box-shadow:0 0 0 100vmax #000c;padding:18px}.card.expanded .views{display:flex;flex-wrap:wrap;align-items:flex-start;overflow:visible}.card.expanded .view{min-width:0}.card.expanded .view canvas{max-height:none}.card.expanded .head{position:sticky;top:-18px;background:#181e27;padding:10px 0;z-index:2}.zoom{display:none;align-items:center;gap:4px}.card.expanded .zoom{display:flex}.zoom button{font-size:17px;line-height:1;padding:5px 10px}.zoom input{width:150px}.zoom output{min-width:48px;text-align:center;font-size:12px;color:#c6d1df}
.head{display:flex;gap:8px;align-items:center}.head b{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.meta{font-size:11px;color:#9da8b8;margin-left:auto}
.views{display:flex;gap:7px;overflow-x:auto;margin:9px 0}.view{min-width:145px}.view canvas{width:145px;height:auto;max-height:145px;background:#0d1015;image-rendering:pixelated;border-radius:5px;cursor:crosshair}.view span{font-size:10px;color:#9da8b8;display:block}.viewfoot{display:flex;align-items:center;justify-content:space-between;gap:5px}.viewfoot button{font-size:10px;padding:3px 7px}
.actions{display:flex;gap:7px}.actions button[data-v=approve]{color:#77dfa6}.actions button[data-v=reject]{color:#ff8b8b}.inspecttools{display:flex;gap:7px;flex-wrap:wrap;margin:0 0 10px}.inspecttools button{padding:5px 8px;font-size:11px}
.toolhint{display:inline-block;min-width:260px;padding:5px 8px;border-radius:6px;background:#152333;color:#a9d5ff;font-size:11px}.toolhint.bad{background:#3a2024;color:#ffb3b3}
#modal{display:none;position:fixed;inset:0;z-index:50;background:#000e;align-items:center;justify-content:center;padding:18px}#modal.open{display:flex}.inspector{width:min(1180px,96vw);max-height:95vh;overflow:auto;background:#171e27;border:1px solid #3b4655;border-radius:12px;padding:14px}.inspecthead{display:flex;align-items:center;gap:10px;margin-bottom:10px}.inspecthead b{font-size:14px}.inspecthead span{color:#9eabba;font-size:12px;margin-left:auto}.inspectbody{display:grid;grid-template-columns:minmax(0,1fr) 280px;gap:14px;align-items:start}.annotatedwrap{min-height:540px;max-height:78vh;overflow:auto;background:#0b0e13;border-radius:8px;display:flex;align-items:flex-start;justify-content:flex-start;padding:10px}.annotatedwrap canvas{image-rendering:pixelated;cursor:crosshair;background:#0a0d12}.rawside{background:#0b0e13;border-radius:8px;padding:10px;position:sticky;top:0;min-height:280px}.rawstage{height:190px;display:flex;align-items:center;justify-content:center;border:1px dashed #303b49;border-radius:6px;background:#080b0f}.rawstage canvas{display:block;image-rendering:pixelated}.rawlabel{font-size:11px;color:#e5eaf1;margin-bottom:8px}.rawside p{font-size:11px;color:#adb8c7;line-height:1.45;margin:8px 0 0}@media(max-width:800px){.inspectbody{grid-template-columns:1fr}.rawside{position:static}}
</style></head><body><div class="top"><h1>SVG corner ground truth</h1><div class="bar">
<select id="filter"><option value="all">усе</option><option value="pending">не правераныя</option><option value="paper">paper human</option><option value="svg">SVG extended</option><option value="smooth">без вуглоў</option><option value="occlusion">аклюзіі</option></select>
<button class="tool active" data-tool="1">+ corner (point)</button><button class="tool" data-tool="4">+ edge between corners (1 click)</button><button class="tool" data-tool="3">+ short span (1-2 px only)</button><button class="tool" data-tool="2">+ occlusion</button><button class="tool" data-tool="0">remove event / brush</button>
<button id="undo" disabled title="Ctrl+Z">Undo</button><button id="redo" disabled title="Ctrl+Shift+Z / Ctrl+Y">Redo</button>
<span id="toolhint" class="toolhint">Point corner: click a sharp vertex. Short span works only on a 1-2 px flat corner edge.</span>
<button id="save">Save review</button><button id="export">Export JSON</button><span id="stats"></span><span class="legend">click = selected tool · Shift+click = occlusion · right-click = remove</span>
</div></div><main id="grid"></main><div id="modal"><section class="inspector"><div class="inspecthead"><b id="inspect-title">bitmap</b><span id="inspect-meta"></span><button id="inspect-close">close</button></div><div class="inspecttools"><button class="tool" data-tool="1">+ corner</button><button class="tool" data-tool="3">+ short span</button><button class="tool" data-tool="2">+ occlusion</button><button class="tool" data-tool="0">remove event / brush</button><span class="legend">click or drag on the large bitmap · Ctrl+Z</span></div><div class="inspectbody"><div class="annotatedwrap"><canvas id="mini-canvas"></canvas></div><aside class="rawside"><div class="rawlabel">Raw · actual size</div><div class="rawstage"><canvas id="raw-canvas"></canvas></div><p>Рэдагуй кропкі на вялікім bitmap. Жоўтая кропка пакажа тое самае месца на маленькім raw.</p></aside></div></section></div><script>
let decisions={},corrections={},manualEdges={},storageKeys=null,data,tool=1,pairStart=null;const undoStack=[],redoStack=[];
const grid=document.querySelector('#grid'),filter=document.querySelector('#filter'),stats=document.querySelector('#stats'),toolhint=document.querySelector('#toolhint');
function showHint(message,bad=false){toolhint.textContent=message;toolhint.classList.toggle('bad',bad)}
function storedObject(key){try{const value=JSON.parse(localStorage.getItem(key)||'{}');return value&&typeof value==='object'&&!Array.isArray(value)?value:{}}catch{return{}}}
function loadDatasetStorage(dataset){const namespace=String(dataset);storageKeys={decisions:`cornerGtReview:${namespace}`,corrections:`cornerGtCorrections:${namespace}`,edges:`cornerGtManualEdges:${namespace}`};decisions=storedObject(storageKeys.decisions);corrections=storedObject(storageKeys.corrections);manualEdges=storedObject(storageKeys.edges)}
function persist(){if(!storageKeys)return;localStorage.setItem(storageKeys.decisions,JSON.stringify(decisions));localStorage.setItem(storageKeys.corrections,JSON.stringify(corrections));localStorage.setItem(storageKeys.edges,JSON.stringify(manualEdges))}
function historyButtons(){document.querySelector('#undo').disabled=!undoStack.length;document.querySelector('#redo').disabled=!redoStack.length;document.querySelectorAll('[data-card-undo]').forEach(button=>button.disabled=!undoStack.length);document.querySelectorAll('[data-card-redo]').forEach(button=>button.disabled=!redoStack.length)}
function correctionValue(viewId,key){return Object.prototype.hasOwnProperty.call(corrections[viewId]||{},key)?corrections[viewId][key]:null}
function setCorrection(viewId,key,value){if(value===null){if(corrections[viewId]){delete corrections[viewId][key];if(!Object.keys(corrections[viewId]).length)delete corrections[viewId]}}else(corrections[viewId]??={})[key]=value;persist();document.querySelectorAll('canvas').forEach(canvas=>{if(canvas._view?.id===viewId)drawCanvas(canvas)})}
function refreshEditStats(){if(!data)return;stats.textContent=`${document.querySelectorAll('.card').length}/${data.entries.length} · approved ${Object.values(decisions).filter(x=>x==='approve').length} · edits ${Object.values(corrections).reduce((n,x)=>n+Object.keys(x).length,0)} · edges ${edgeCount()}`}
function commitBatch(viewId,items,group=null){const seen=new Set(),changes=items.filter(x=>!seen.has(x.key)&&seen.add(x.key)).map(({key,value})=>({key,before:correctionValue(viewId,key),after:value})).filter(x=>x.before!==x.after);if(!changes.length)return;changes.forEach(x=>setCorrection(viewId,x.key,x.after));const previous=undoStack[undoStack.length-1];if(group&&previous?.group===group&&previous.viewId===viewId)previous.changes.push(...changes);else undoStack.push({viewId,changes,group});redoStack.length=0;historyButtons();refreshEditStats()}
function commitCorrection(viewId,key,value){commitBatch(viewId,[{key,value}])}
function undo(){const action=undoStack.pop();if(!action)return;[...action.changes].reverse().forEach(x=>setCorrection(action.viewId,x.key,x.before));redoStack.push(action);historyButtons();refreshEditStats()}
function redo(){const action=redoStack.pop();if(!action)return;action.changes.forEach(x=>setCorrection(action.viewId,x.key,x.after));undoStack.push(action);historyButtons();refreshEditStats()}
function labelsFor(view,ann){const labels=new Map();ann.loops.forEach((l,li)=>l.labels.forEach(([vi,v])=>labels.set(`${li}:${vi}`,v)));Object.entries(corrections[view.id]||{}).forEach(([k,v])=>v?labels.set(k,v):labels.delete(k));return labels}
const MIN_ZOOM=1,MAX_ZOOM=800;
function resizeCanvas(canvas,longSide){const ann=canvas._ann;if(!ann)return;const aspect=ann.width/ann.height;let cssW,cssH;if(aspect>=1){cssW=longSide;cssH=longSide/aspect}else{cssH=longSide;cssW=longSide*aspect}const expanded=canvas.closest('.card')?.classList.contains('expanded');const dpr=expanded?Math.min(2,devicePixelRatio||1):1;const backingLong=Math.min(2048,Math.max(192,Math.round(longSide*dpr)));let bw,bh;if(aspect>=1){bw=backingLong;bh=Math.max(1,Math.round(backingLong/aspect))}else{bh=backingLong;bw=Math.max(1,Math.round(backingLong*aspect))}canvas.style.width=`${cssW}px`;canvas.style.height=`${cssH}px`;canvas.parentElement.style.width=`${cssW}px`;if(canvas.width!==bw||canvas.height!==bh){canvas.width=bw;canvas.height=bh}drawCanvas(canvas)}
function traceLoop(ctx,loop,sx,sy){ctx.beginPath();loop.points.forEach((p,i)=>i?ctx.lineTo(p[0]*sx,p[1]*sy):ctx.moveTo(p[0]*sx,p[1]*sy));ctx.closePath()}
function drawCanvas(canvas){const ann=canvas._ann,img=canvas._img,view=canvas._view;if(!ann||!img)return;const ctx=canvas.getContext('2d'),sx=canvas.width/ann.width,sy=canvas.height/ann.height,rect=canvas.getBoundingClientRect(),screenScale=(canvas.width/Math.max(1,rect.width)+canvas.height/Math.max(1,rect.height))/2,shortSide=Math.min(rect.width,rect.height),activeLabels=labelsFor(view,ann);ctx.clearRect(0,0,canvas.width,canvas.height);ctx.imageSmoothingEnabled=false;if(ann.fill_from_loops){ctx.fillStyle='#fafafa';for(const loop of ann.loops){traceLoop(ctx,loop,sx,sy);ctx.fill()}}else ctx.drawImage(img,0,0,canvas.width,canvas.height);const lineCss=Math.min(3.2,Math.max(1.4,shortSide*.016));ctx.strokeStyle='#07101d';ctx.lineWidth=(lineCss+2.2)*screenScale;for(const loop of ann.loops){traceLoop(ctx,loop,sx,sy);ctx.stroke()}ctx.strokeStyle='#43a0ff';ctx.lineWidth=lineCss*screenScale;for(const loop of ann.loops){traceLoop(ctx,loop,sx,sy);ctx.stroke()}ann.loops.forEach((loop,li)=>(loop.events||[]).forEach(event=>{if(event[1]!==2||event[2].length!==2||event[2].some(vi=>activeLabels.get(`${li}:${vi}`)!==1))return;const a=loop.points[event[2][0]],b=loop.points[event[2][1]],drawSpan=(colour,width)=>{ctx.beginPath();ctx.strokeStyle=colour;ctx.lineWidth=width;ctx.moveTo(a[0]*sx,a[1]*sy);ctx.lineTo(b[0]*sx,b[1]*sy);ctx.stroke()};drawSpan('#111722',Math.max(6,6.4*screenScale));drawSpan('#ffe34d',Math.max(3.2,3.4*screenScale))}));const markerCss=Math.min(6,Math.max(2.2,shortSide*.036)),radius=markerCss*screenScale;for(const [key,v] of activeLabels){const [li,vi]=key.split(':').map(Number),p=ann.loops[li]?.points[vi];if(!p)continue;ctx.beginPath();ctx.fillStyle=v===1?'#ff3b3b':'#ff2bda';ctx.strokeStyle='#10151d';ctx.lineWidth=Math.max(1.5,1.5*screenScale);ctx.arc(p[0]*sx,p[1]*sy,radius,0,Math.PI*2);ctx.fill();ctx.stroke()}if(canvas._hoverAnn){const p=canvas._hoverAnn,hoverRadius=Math.min(8,Math.max(4,shortSide*.045))*screenScale;ctx.beginPath();ctx.fillStyle='#ffe600';ctx.strokeStyle='#151515';ctx.lineWidth=Math.max(2,1.5*screenScale);ctx.arc(p[0]*sx,p[1]*sy,hoverRadius,0,Math.PI*2);ctx.fill();ctx.stroke()}}
function zoomStep(value,direction){const step=value<10?1:value<50?5:value<200?10:value<400?25:50;return value+direction*step}function setZoom(card,value){card._zoom=Math.max(MIN_ZOOM,Math.min(MAX_ZOOM,Math.round(value)));applyZoom(card)}function applyZoom(card){const expanded=card.classList.contains('expanded'),percent=card._zoom??100,zoom=percent/100,longSide=expanded?520*zoom:180;card.querySelector('[data-zoom-label]').textContent=`${percent}%`;card.querySelector('[data-zoom-range]').value=percent;card.querySelectorAll('canvas').forEach(canvas=>resizeCanvas(canvas,longSide))}
async function setupCanvas(canvas,view){const [img,ann]=await Promise.all([new Promise((ok,fail)=>{const i=new Image;i.onload=()=>ok(i);i.onerror=fail;i.src=view.image}),fetch(view.annotation).then(r=>r.json())]);canvas._img=img;canvas._ann=ann;canvas._view=view;canvas.dataset.loaded='1';const card=canvas.closest('.card'),zoom=(card?._zoom??100)/100;resizeCanvas(canvas,card?.classList.contains('expanded')?360*zoom:145);function removalKeys(key){const [li,vi]=key.split(':').map(Number),loop=ann.loops[li],active=labelsFor(view,ann),stored=(loop.events||[]).find(event=>event[2].includes(vi));if(stored)return stored[2].map(index=>`${li}:${index}`).filter(k=>active.has(k));if(active.get(key)===1){for(const [other,value] of active){const [oli,ovi]=other.split(':').map(Number);if(value!==1||oli!==li||other===key||correctionValue(view.id,other)!==1)continue;const gap=Math.min((ovi-vi+loop.points.length)%loop.points.length,(vi-ovi+loop.points.length)%loop.points.length);if(gap<=2)return[key,other]}}return[key]}function edit(ev,forced,group=null){ev.preventDefault();const r=canvas.getBoundingClientRect(),x=(ev.clientX-r.left)*ann.width/r.width,y=(ev.clientY-r.top)*ann.height/r.height;const mode=forced??(ev.shiftKey?2:tool);let best=null,bd=1e9;if(mode===0){for(const key of labelsFor(view,ann).keys()){const [li,vi]=key.split(':').map(Number),p=ann.loops[li]?.points[vi];if(!p)continue;const d=Math.hypot(p[0]-x,p[1]-y);if(d<bd){bd=d;best=key}}}else if(mode===3){ann.loops.forEach((l,li)=>{const n=l.points.length;for(let a=0;a<n;a++)for(const gap of [1,2]){const b=(a+gap)%n,pa=l.points[a],pb=l.points[b];let arc=0;for(let k=0;k<gap;k++){const q=l.points[(a+k)%n],z=l.points[(a+k+1)%n];arc+=Math.hypot(z[0]-q[0],z[1]-q[1])}const chord=Math.hypot(pb[0]-pa[0],pb[1]-pa[1]);if(arc>2.1||chord<.8||chord/Math.max(arc,1e-9)<.985)continue;const d=Math.hypot((pa[0]+pb[0])/2-x,(pa[1]+pb[1])/2-y);if(d<bd){bd=d;best=[`${li}:${a}`,`${li}:${b}`]}}})}else ann.loops.forEach((l,li)=>l.points.forEach((p,vi)=>{const d=Math.hypot(p[0]-x,p[1]-y);if(d<bd){bd=d;best=`${li}:${vi}`}}));const hit=14*((ann.width/r.width+ann.height/r.height)/2);if(!best||bd>hit)return;if(mode===0)commitBatch(view.id,removalKeys(best).map(key=>({key,value:0})),group);else if(mode===3)commitBatch(view.id,best.map(key=>({key,value:1})));else commitCorrection(view.id,best,mode)}let brushing=false,brushGroup=null;canvas.onpointerdown=e=>{if(e.button!==0&&e.button!==2)return;const mode=e.button===2?0:(e.shiftKey?2:tool);if(mode===0){brushing=true;brushGroup=`${view.id}:${e.pointerId}:${Date.now()}`;canvas.setPointerCapture?.(e.pointerId);edit(e,0,brushGroup)}else edit(e,mode)};canvas.onpointermove=e=>{if(brushing)edit(e,0,brushGroup)};const finishBrush=e=>{if(!brushing)return;brushing=false;brushGroup=null;try{canvas.releasePointerCapture?.(e.pointerId)}catch{}};canvas.onpointerup=finishBrush;canvas.onpointercancel=finishBrush;canvas.oncontextmenu=e=>e.preventDefault()}
function bindInspectorEditing(canvas,view,ann){
function removalKeys(key){const [li,vi]=key.split(':').map(Number),loop=ann.loops[li],active=labelsFor(view,ann),stored=(loop.events||[]).find(event=>event[2].includes(vi));if(stored)return stored[2].map(index=>`${li}:${index}`).filter(k=>active.has(k));if(active.get(key)===1){for(const [other,value] of active){const [oli,ovi]=other.split(':').map(Number);if(value!==1||oli!==li||other===key||correctionValue(view.id,other)!==1)continue;const gap=Math.min((ovi-vi+loop.points.length)%loop.points.length,(vi-ovi+loop.points.length)%loop.points.length);if(gap<=2)return[key,other]}}return[key]}
function edit(ev,forced,group=null){ev.preventDefault();const r=canvas.getBoundingClientRect(),x=(ev.clientX-r.left)*ann.width/r.width,y=(ev.clientY-r.top)*ann.height/r.height,mode=forced??(ev.shiftKey?2:tool);let best=null,bd=1e9;if(mode===0){for(const key of labelsFor(view,ann).keys()){const [li,vi]=key.split(':').map(Number),p=ann.loops[li]?.points[vi];if(!p)continue;const d=Math.hypot(p[0]-x,p[1]-y);if(d<bd){bd=d;best=key}}}else if(mode===3){ann.loops.forEach((l,li)=>{const n=l.points.length;for(let a=0;a<n;a++)for(const gap of[1,2]){const b=(a+gap)%n,pa=l.points[a],pb=l.points[b];let arc=0;for(let k=0;k<gap;k++){const q=l.points[(a+k)%n],z=l.points[(a+k+1)%n];arc+=Math.hypot(z[0]-q[0],z[1]-q[1])}const chord=Math.hypot(pb[0]-pa[0],pb[1]-pa[1]);if(arc>2.1||chord<.8||chord/Math.max(arc,1e-9)<.985)continue;const d=Math.hypot((pa[0]+pb[0])/2-x,(pa[1]+pb[1])/2-y);if(d<bd){bd=d;best=[`${li}:${a}`,`${li}:${b}`]}}})}else ann.loops.forEach((l,li)=>l.points.forEach((p,vi)=>{const d=Math.hypot(p[0]-x,p[1]-y);if(d<bd){bd=d;best=`${li}:${vi}`}}));const hit=14*((ann.width/r.width+ann.height/r.height)/2);if(!best||bd>hit)return;if(mode===0)commitBatch(view.id,removalKeys(best).map(key=>({key,value:0})),group);else if(mode===3)commitBatch(view.id,best.map(key=>({key,value:1})));else commitCorrection(view.id,best,mode)}
let brushing=false,brushGroup=null;canvas.onpointerdown=e=>{if(e.button!==0&&e.button!==2)return;const mode=e.button===2?0:(e.shiftKey?2:tool);if(mode===0){brushing=true;brushGroup=`${view.id}:inspector:${e.pointerId}:${Date.now()}`;canvas.setPointerCapture?.(e.pointerId);edit(e,0,brushGroup)}else edit(e,mode)};canvas.onpointermove=e=>{if(brushing)edit(e,0,brushGroup)};const finish=e=>{if(!brushing)return;brushing=false;brushGroup=null;try{canvas.releasePointerCapture?.(e.pointerId)}catch{}};canvas.onpointerup=finish;canvas.onpointercancel=finish;canvas.oncontextmenu=e=>e.preventDefault()}
function ensureCanvas(canvas,view=canvas._pendingView){if(!view||canvas._ann)return Promise.resolve(canvas);if(canvas._loadPromise)return canvas._loadPromise;canvas._loadPromise=setupCanvas(canvas,view).then(()=>canvas).catch(error=>{canvas._loadError=true;canvas.dataset.loadError='1';console.warn('canvas load failed',view.id,error);return canvas});return canvas._loadPromise}
const modal=document.querySelector('#modal'),rawCanvas=document.querySelector('#raw-canvas'),miniCanvas=document.querySelector('#mini-canvas');let inspectSource=null,inspectView=null;
function clearInspectorHover(){rawCanvas._hoverAnn=null;if(inspectSource&&inspectView)drawRaw(inspectSource,inspectView)}
function closeInspector(){clearInspectorHover();inspectSource=null;inspectView=null;modal.classList.remove('open')}
function drawRaw(source,view){const ann=source._ann,img=source._img,size=Math.max(1,Number(view.res)||Math.max(ann.width,ann.height)),w=size,h=size,scale=Math.min(w/ann.width,h/ann.height),drawW=ann.width*scale,drawH=ann.height*scale,ox=(w-drawW)/2,oy=(h-drawH)/2;rawCanvas.width=w;rawCanvas.height=h;const ctx=rawCanvas.getContext('2d');ctx.clearRect(0,0,w,h);ctx.imageSmoothingEnabled=false;if(ann.fill_from_loops){ctx.save();ctx.translate(ox,oy);ctx.fillStyle='#fafafa';for(const loop of ann.loops){traceLoop(ctx,loop,scale,scale);ctx.fill()}ctx.restore()}else ctx.drawImage(img,ox,oy,drawW,drawH);if(rawCanvas._hoverAnn){const p=rawCanvas._hoverAnn,radius=Math.max(1,Math.min(2,size/24));ctx.beginPath();ctx.fillStyle='#ffe600';ctx.strokeStyle='#151515';ctx.lineWidth=Math.max(.5,size/128);ctx.arc(ox+p[0]*scale,oy+p[1]*scale,radius,0,Math.PI*2);ctx.fill();ctx.stroke()}rawCanvas.style.width=`${w}px`;rawCanvas.style.height=`${h}px`;document.querySelector('#inspect-meta').textContent=`raw ${w}×${h} actual pixels · annotated bitmap 720px`}
function openInspector(source,name,view){closeInspector();inspectSource=source;inspectView=view;miniCanvas._ann=source._ann;miniCanvas._img=source._img;miniCanvas._view=source._view;miniCanvas._hoverAnn=null;document.querySelector('#inspect-title').textContent=`${name} · ${view.res}px · annotated bitmap`;modal.classList.add('open');resizeCanvas(miniCanvas,720);bindInspectorEditing(miniCanvas,view,source._ann);drawRaw(source,view);miniCanvas.onmousemove=ev=>{const r=miniCanvas.getBoundingClientRect(),ann=source._ann;rawCanvas._hoverAnn=[(ev.clientX-r.left)*ann.width/r.width,(ev.clientY-r.top)*ann.height/r.height];drawRaw(source,view)};miniCanvas.onmouseleave=clearInspectorHover}
document.querySelector('#inspect-close').onclick=closeInspector;modal.onclick=ev=>{if(ev.target===modal)closeInspector()};
let loadScheduled=false;function loadVisibleNow(){document.querySelectorAll('canvas').forEach(canvas=>{const r=canvas.getBoundingClientRect();if(r.bottom>-500&&r.top<innerHeight+500)ensureCanvas(canvas)})}function scheduleVisibleLoad(){if(loadScheduled)return;loadScheduled=true;requestAnimationFrame(()=>{loadScheduled=false;loadVisibleNow()})}addEventListener('scroll',scheduleVisibleLoad,{passive:true});
function render(){grid.innerHTML='';let shown=0;for(const e of data.entries){const s=decisions[e.id]||'pending',f=filter.value;if(f==='pending'&&s!=='pending'||f==='paper'&&e.source_layer!=='paper-human'||f==='svg'&&e.source_layer!=='svg-extended'||f==='smooth'&&!e.zero_corner||f==='occlusion'&&!e.occlusion)continue;shown++;const c=document.createElement('section');c.className='card '+(s==='approve'?'approved':s==='reject'?'rejected':'');c.dataset.entryId=e.id;c._zoom=100;const source=e.source?`<a href="${e.source}" target=_blank><button>source</button></a>`:'';const layer=e.source_layer?` · ${e.source_layer}`:'';const events=e.events??e.structural+e.occlusion;c.innerHTML=`<div class=head><b>${e.name}</b><span class=meta>${events} events · ${e.structural} labels · ${e.loops} loops${layer} · ${s}</span><div class=zoom><button data-card-undo disabled title="Undo · Ctrl+Z">↶</button><button data-card-redo disabled title="Redo · Ctrl+Shift+Z">↷</button><button data-zoom-out title="Zoom out">−</button><input data-zoom-range type=range min=1 max=800 value=100 title="Zoom 1%–800%"><output data-zoom-label>100%</output><button data-zoom-in title="Zoom in">+</button></div><button data-expand>fullscreen</button></div><div class=views>${e.views.map((v,i)=>`<div class=view><canvas data-i="${i}"></canvas><div class=viewfoot><span>${v.res}px · ${v.events??v.corners} events · ${v.corners} labels</span><span><button data-clear-i="${i}" title="Clear labels in this size; Ctrl+Z restores them">clear</button> <button data-raw-i="${i}" title="Open raw without points">raw</button></span></div></div>`).join('')}</div><div class=actions><button data-v=approve>approve</button><button data-v=reject>reject</button><button data-v=pending>reset</button>${source}</div>`;const toggle=()=>{c.classList.toggle('expanded');if(c.classList.contains('expanded'))c.querySelectorAll('canvas').forEach(canvas=>ensureCanvas(canvas));requestAnimationFrame(()=>applyZoom(c))};c.querySelector('[data-expand]').onclick=ev=>{ev.stopPropagation();toggle()};c.querySelector('[data-card-undo]').onclick=ev=>{ev.stopPropagation();undo()};c.querySelector('[data-card-redo]').onclick=ev=>{ev.stopPropagation();redo()};c.querySelector('[data-zoom-out]').onclick=ev=>{ev.stopPropagation();setZoom(c,zoomStep(c._zoom,-1))};c.querySelector('[data-zoom-in]').onclick=ev=>{ev.stopPropagation();setZoom(c,zoomStep(c._zoom,1))};c.querySelector('[data-zoom-range]').oninput=ev=>{ev.stopPropagation();setZoom(c,Number(ev.target.value))};c.querySelectorAll('[data-clear-i]').forEach(button=>button.onclick=async ev=>{ev.stopPropagation();const i=Number(button.dataset.clearI),canvas=c.querySelector(`canvas[data-i="${i}"]`);await ensureCanvas(canvas,e.views[i]);if(canvas._ann)commitBatch(e.views[i].id,[...labelsFor(e.views[i],canvas._ann).keys()].map(key=>({key,value:0})))});c.querySelectorAll('[data-raw-i]').forEach(button=>button.onclick=async ev=>{ev.stopPropagation();const i=Number(button.dataset.rawI),canvas=c.querySelector(`canvas[data-i="${i}"]`);await ensureCanvas(canvas,e.views[i]);if(canvas._ann)openInspector(canvas,e.name,e.views[i])});c.onclick=ev=>{if(!ev.target.closest('canvas,button,a,select,input'))toggle()};c.querySelectorAll('[data-v]').forEach(b=>b.onclick=()=>{const value=b.dataset.v;decisions[e.id]=value;persist();if(filter.value==='pending')render();else{c.className='card '+(value==='approve'?'approved':value==='reject'?'rejected':'');c.querySelector('.meta').textContent=`${events} events · ${e.structural} labels · ${e.loops} loops${layer} · ${value}`;updateStats(shown)}});grid.append(c);c.querySelectorAll('canvas').forEach(cv=>cv._pendingView=e.views[Number(cv.dataset.i)])}historyButtons();updateStats(shown);loadVisibleNow()}
function updateStats(shown){stats.textContent=`${shown}/${data.entries.length} · approved ${Object.values(decisions).filter(x=>x==='approve').length} · edits ${Object.values(corrections).reduce((n,x)=>n+Object.keys(x).length,0)} · edges ${edgeCount()}`}
filter.onchange=render;function syncTools(){document.querySelectorAll('.tool').forEach(x=>x.classList.toggle('active',Number(x.dataset.tool)===tool))}document.querySelectorAll('.tool').forEach(b=>b.onclick=()=>{tool=Number(b.dataset.tool);pairStart=null;syncTools();showHint(tool===4?'Edge: click anywhere between two existing red corners. Staircases and any length are allowed. Click again to remove it.':tool===3?'Short span: click the middle of a straight 1-2 px corner edge. Use point corner for an ordinary vertex.':tool===1?'Point corner: click directly on a sharp vertex.':tool===0?'Remove: click an existing marker or drag across markers.':'Occlusion: click a visible cut/junction corner.')});syncTools();
document.querySelectorAll('.inspecttools').forEach(box=>{if(box.querySelector('[data-tool="4"]'))return;const button=document.createElement('button');button.className='tool';button.dataset.tool='4';button.textContent='+ edge between corners (1 click)';button.onclick=()=>{tool=4;pairStart=null;syncTools();showHint('Edge: click anywhere between two existing red corners. Staircases and any length are allowed.')};box.insertBefore(button,box.children[1]||null)});
function correctionCount(){return Object.values(corrections).reduce((n,x)=>n+Object.keys(x).length,0)}
function edgeCount(){return Object.values(manualEdges).reduce((n,x)=>n+x.length,0)}
const drawCanvasBase=drawCanvas;
function drawReviewedEdges(canvas){const ann=canvas._ann,view=canvas._view,edges=manualEdges[view?.id]||[];if(!ann||!view||!edges.length)return;const ctx=canvas.getContext('2d'),sx=canvas.width/ann.width,sy=canvas.height/ann.height,rect=canvas.getBoundingClientRect(),screenScale=(canvas.width/Math.max(1,rect.width)+canvas.height/Math.max(1,rect.height))/2,shortSide=Math.min(rect.width,rect.height),markerCss=Math.min(6,Math.max(2.2,shortSide*.036)),markerRadius=markerCss*screenScale;for(const edge of edges){const loop=ann.loops[edge.loop],n=loop?.points?.length||0;if(!n||edge.start<0||edge.end<0||edge.start>=n||edge.end>=n)continue;const points=[];let index=edge.start,guard=0;while(guard++<=n){const p=loop.points[index];points.push([p[0]*sx,p[1]*sy]);if(index===edge.end)break;index=(index+1)%n}if(points.length<2)continue;let total=0;for(let i=1;i<points.length;i++)total+=Math.hypot(points[i][0]-points[i-1][0],points[i][1]-points[i-1][1]);const trim=Math.min(markerRadius+Math.max(2,2*screenScale),total*.22),trimmed=points.map(p=>p.slice());let remaining=trim;while(trimmed.length>1&&remaining>0){const a=trimmed[0],b=trimmed[1],length=Math.hypot(b[0]-a[0],b[1]-a[1]);if(length<=remaining){trimmed.shift();remaining-=length}else{trimmed[0]=[a[0]+(b[0]-a[0])*remaining/length,a[1]+(b[1]-a[1])*remaining/length];remaining=0}}remaining=trim;while(trimmed.length>1&&remaining>0){const a=trimmed[trimmed.length-1],b=trimmed[trimmed.length-2],length=Math.hypot(b[0]-a[0],b[1]-a[1]);if(length<=remaining){trimmed.pop();remaining-=length}else{trimmed[trimmed.length-1]=[a[0]+(b[0]-a[0])*remaining/length,a[1]+(b[1]-a[1])*remaining/length];remaining=0}}if(trimmed.length<2)continue;const stroke=(colour,width)=>{ctx.beginPath();ctx.strokeStyle=colour;ctx.lineWidth=width;ctx.lineCap='round';ctx.lineJoin='round';ctx.moveTo(trimmed[0][0],trimmed[0][1]);for(let i=1;i<trimmed.length;i++)ctx.lineTo(trimmed[i][0],trimmed[i][1]);ctx.stroke()};stroke('#10151d',Math.max(7,7*screenScale));stroke('#ffe24a',Math.max(3.4,3.4*screenScale))}}
drawCanvas=function(canvas){drawCanvasBase(canvas);drawReviewedEdges(canvas)};
document.addEventListener('pointerdown',event=>{if(event.target.tagName!=='CANVAS')return;const before=correctionCount(),beforeEdges=edgeCount(),mode=event.button===2?0:(event.shiftKey?2:tool);if(mode===4)return;setTimeout(()=>{const after=correctionCount(),afterEdges=edgeCount();if(afterEdges!==beforeEdges){showHint(afterEdges<beforeEdges?'Edge removed.':'Edge selected.');return}if(after!==before){showHint(mode===3?'Short span added.':mode===0?'Marker removed.':mode===2?'Occlusion marker added.':'Point corner added.')}else{showHint(mode===3?'No eligible 1-2 px straight span here. Use + corner (point) for an ordinary vertex.':'Nothing changed. Click closer to the boundary or an existing marker.',true)}},0)},true);
function nearestBoundaryHit(canvas,event){const ann=canvas._ann,view=canvas._view;if(!ann||!view)return null;const rect=canvas.getBoundingClientRect(),x=(event.clientX-rect.left)*ann.width/rect.width,y=(event.clientY-rect.top)*ann.height/rect.height,limit=14*((ann.width/rect.width+ann.height/rect.height)/2);let best=null,bd=Infinity;ann.loops.forEach((loop,li)=>loop.points.forEach((p,vi)=>{const d=Math.hypot(p[0]-x,p[1]-y);if(d<bd){bd=d;best={canvas,viewId:view.id,li,vi,key:`${li}:${vi}`,point:p}}}));return best&&bd<=limit?best:null}
function edgeContainsVertex(edge,n,vertex){if(edge.start<0||edge.end<0||edge.start>=n||edge.end>=n)return false;let index=edge.start,guard=0;while(guard++<=n){if(index===vertex)return true;if(index===edge.end)break;index=(index+1)%n}return false}
function selectedEdgeAtHit(hit){const n=hit.canvas._ann.loops[hit.li].points.length,edges=manualEdges[hit.viewId]??[],index=edges.findIndex(edge=>edge.loop===hit.li&&edgeContainsVertex(edge,n,hit.vi));return{edges,index}}
function neighbouringCornerEdge(hit){const ann=hit.canvas._ann,labels=labelsFor(hit.canvas._view,ann),loop=ann.loops[hit.li],n=loop.points.length,active=new Set();for(const [key,value] of labels){const [li,vi]=key.split(':').map(Number);if(li===hit.li&&value>0)active.add(vi)}if(active.size<2)return null;let start=null,end=null;for(let d=0;d<n;d++){const index=(hit.vi-d+n)%n;if(active.has(index)&&(d>0||!active.has(hit.vi))){start=index;break}}for(let d=0;d<n;d++){const index=(hit.vi+d)%n;if(active.has(index)&&(d>0||!active.has(hit.vi))){end=index;break}}return start===null||end===null||start===end?null:{loop:hit.li,start,end}}
document.addEventListener('pointerdown',event=>{if(tool!==4||event.target.tagName!=='CANVAS'||event.button!==0)return;event.preventDefault();event.stopPropagation();event.stopImmediatePropagation();const hit=nearestBoundaryHit(event.target,event);if(!hit){showHint('Click closer to the contour between two corners.',true);return}const selected=selectedEdgeAtHit(hit);if(selected.index>=0){selected.edges.splice(selected.index,1);manualEdges[hit.viewId]=selected.edges;showHint('Edge selection removed.')}else{const edge=neighbouringCornerEdge(hit);if(!edge){showHint('This contour needs two neighbouring marked corners around the clicked section.',true);return}selected.edges.push(edge);manualEdges[hit.viewId]=selected.edges;showHint('Edge selected between the neighbouring corners.')}persist();drawCanvas(hit.canvas);refreshEditStats()},true);
document.addEventListener('pointerdown',event=>{const mode=event.button===2?0:tool;if(mode!==0||event.target.tagName!=='CANVAS')return;const hit=nearestBoundaryHit(event.target,event);if(!hit)return;const selected=selectedEdgeAtHit(hit);if(selected.index<0)return;event.preventDefault();event.stopPropagation();event.stopImmediatePropagation();selected.edges.splice(selected.index,1);manualEdges[hit.viewId]=selected.edges;persist();drawCanvas(hit.canvas);refreshEditStats();showHint('Edge removed; corner markers were kept.')},true);
document.querySelector('#undo').onclick=undo;document.querySelector('#redo').onclick=redo;
function payload(){return{dataset:data.dataset,decisions,corrections,edges:manualEdges,updated_at:new Date().toISOString()}}
document.querySelector('#save').onclick=async()=>{const b=document.querySelector('#save');b.textContent='Saving…';const r=await fetch('/api/corner-review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload())});b.textContent=r.ok?'Saved ✓':'Save failed'};
document.querySelector('#export').onclick=()=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(payload(),null,2)],{type:'application/json'}));a.download='corner_review.json';a.click()};
fetch('manifest.json?t='+Date.now()).then(r=>r.json()).then(async x=>{data=x;loadDatasetStorage(data.dataset);try{const saved=await fetch('/api/corner-review?dataset='+encodeURIComponent(data.dataset)).then(r=>r.ok?r.json():({}));Object.assign(decisions,saved.decisions||{});Object.assign(corrections,saved.corrections||{});Object.assign(manualEdges,saved.edges||{});persist()}catch{}render()});
document.addEventListener('keydown',e=>{const mod=e.ctrlKey||e.metaKey,key=e.key.toLowerCase();if(mod&&key==='z'){e.preventDefault();e.shiftKey?redo():undo();return}if(mod&&key==='y'){e.preventDefault();redo();return}if(e.key==='Escape'&&modal.classList.contains('open')){closeInspector();return}if(e.key==='Escape')document.querySelectorAll('.card.expanded').forEach(c=>{c.classList.remove('expanded');applyZoom(c)})});
</script></body></html>'''
    (preview / "index.html").write_text(page, encoding="utf-8")


def build(roots: list[Path], out: Path, preview: Path, file_limit: int,
          resolutions: list[int], preview_files: int, scan_limit: int, seed: int,
          allow_empty_resolutions: bool = False) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    (preview / "images").mkdir(parents=True, exist_ok=True)
    (preview / "sources").mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    pools: list[list[Path]] = []
    for root in roots:
        if root.is_dir():
            pool = list(root.rglob("*.svg"))
            rng.shuffle(pool)
            pools.append(pool)
    # Round-robin roots so the huge Iconify tree cannot drown out curated
    # local/ground-truth logos in the review pilot.
    candidates: list[Path] = []
    cursor = 0
    while len(candidates) < scan_limit and any(cursor < len(pool) for pool in pools):
        for pool in pools:
            if cursor < len(pool):
                candidates.append(pool[cursor])
                if len(candidates) >= scan_limit:
                    break
        cursor += 1

    writer = ShardWriter(out)
    files: list[dict] = []
    preview_entries: list[dict] = []
    rejects: Counter[str] = Counter()
    totals = Counter()
    by_resolution: dict[int, Counter] = defaultdict(Counter)

    for candidate in candidates:
        if len(files) >= file_limit:
            break
        per_resolution = []
        failed = None
        for resolution in resolutions:
            try:
                frame = visible_svg_regions(candidate, resolution)
                examples = frame_loop_examples(frame)
            except UnsupportedSvg as exc:
                failed = str(exc)
                break
            except Exception as exc:
                failed = f"parse:{type(exc).__name__}"
                break
            if not examples:
                if allow_empty_resolutions:
                    # A 1px stem at 24px may legitimately disappear at 12px.
                    # Keep the source file and its other scales; never invent a
                    # negative loop for geometry that is no longer visible.
                    continue
                failed = "no-loops"
                break
            per_resolution.append((resolution, frame, examples))
        if not per_resolution and failed is None:
            failed = "no-loops-all-resolutions"
        if failed:
            rejects[failed] += 1
            continue

        file_index = len(files)
        key = _safe_stem(candidate, file_index)
        record = {"path": str(candidate), "name": candidate.stem, "split": _split(candidate), "id": key}
        files.append(record)
        preview_record = {
            "id": key, "name": candidate.stem, "views": [], "loops": 0,
            "structural": 0, "occlusion": 0, "events": 0, "short_spans": 0,
            "zero_corner": False,
        }
        if file_index < preview_files:
            copied = preview / "sources" / f"{key}.svg"
            shutil.copy2(candidate, copied)
            preview_record["source"] = f"sources/{key}.svg"

        for resolution, frame, examples in per_resolution:
            corners_here = 0
            structural_here = 0
            occlusion_here = 0
            zero_here = 0
            events_here = 0
            spans_here = 0
            for loop_index, example in enumerate(examples):
                writer.add(example.points, example.labels, file_index, resolution,
                           example.region_index, loop_index,
                           example.event_ids, example.event_kinds)
                structural = int(np.count_nonzero(example.labels == LABEL_STRUCTURAL))
                occlusion = int(np.count_nonzero(example.labels == LABEL_OCCLUSION))
                structural_here += structural
                occlusion_here += occlusion
                corners_here += structural + occlusion
                zero_here += int(structural + occlusion == 0)
                events_here += len(set(example.event_ids[example.event_ids >= 0].tolist()))
                spans_here += len(set(example.event_ids[example.event_kinds == EVENT_SHORT_SPAN].tolist()))
                totals["loops"] += 1
                totals["vertices"] += len(example.points)
            totals["structural"] += structural_here
            totals["occlusion"] += occlusion_here
            totals["zero_corner_loops"] += zero_here
            totals["events"] += events_here
            totals["short_spans"] += spans_here
            by_resolution[resolution].update({
                "loops": len(examples), "structural": structural_here,
                "occlusion": occlusion_here, "zero_corner_loops": zero_here,
                "events": events_here, "short_spans": spans_here,
            })
            preview_record["loops"] += len(examples)
            preview_record["structural"] += structural_here
            preview_record["occlusion"] += occlusion_here
            preview_record["events"] += events_here
            preview_record["short_spans"] += spans_here
            if file_index < preview_files:
                image_name = f"images/{key}_{resolution}.png"
                annotation_name = f"annotations/{key}_{resolution}.json"
                (preview / "annotations").mkdir(parents=True, exist_ok=True)
                base, display_scale = render_frame_base(frame)
                base.save(preview / image_name)
                annotation = {
                    "width": base.width,
                    "height": base.height,
                    "loops": [
                        {
                            "points": np.round(example.points * display_scale, 2).tolist(),
                            "labels": [[int(index), int(label)] for index, label in enumerate(example.labels)
                                       if int(label) != 0],
                            "events": [
                                [int(event_id), int(example.event_kinds[np.flatnonzero(example.event_ids == event_id)[0]]),
                                 np.flatnonzero(example.event_ids == event_id).astype(int).tolist()]
                                for event_id in sorted(set(example.event_ids[example.event_ids >= 0].tolist()))
                            ],
                        }
                        for example in examples
                    ],
                }
                (preview / annotation_name).write_text(
                    json.dumps(annotation, separators=(",", ":")), encoding="utf-8"
                )
                preview_record["views"].append({
                    "id": f"{key}@{resolution}", "res": resolution,
                    "image": image_name, "annotation": annotation_name,
                    "corners": corners_here,
                    "events": events_here,
                })
        preview_record["zero_corner"] = preview_record["structural"] + preview_record["occlusion"] == 0
        if file_index < preview_files:
            preview_entries.append(preview_record)
        print(f"[{len(files)}/{file_limit}] {candidate.stem}: "
              f"S={preview_record['structural']} O={preview_record['occlusion']} loops={preview_record['loops']}",
              flush=True)

    writer.flush()
    summary = {
        "version": 4,
        "definition": "C0/occlusion vertex labels grouped into point and short-span perceptual events",
        "files": len(files),
        "requested_files": file_limit,
        "resolutions": resolutions,
        **{key: int(value) for key, value in totals.items()},
        "negative_vertices": int(totals["vertices"] - totals["structural"] - totals["occlusion"]),
        "rejects": dict(rejects),
        "by_resolution": {str(key): dict(value) for key, value in by_resolution.items()},
    }
    manifest = {"dataset": out.name, "summary": summary, "files": files, "shards": writer.shards}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_review(preview, preview_entries, summary, out.name)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", action="append", type=Path, dest="roots")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--preview", type=Path, default=DEFAULT_PREVIEW)
    parser.add_argument("--files", type=int, default=80)
    parser.add_argument("--scan", type=int, default=1200)
    parser.add_argument("--preview-files", type=int, default=80)
    parser.add_argument("--resolutions", default="32,48,64,96,128,192,256")
    parser.add_argument("--seed", type=int, default=20260710)
    parser.add_argument("--allow-empty-resolutions", action="store_true",
                        help="skip scales where the whole shape disappears instead of rejecting the source")
    args = parser.parse_args()
    resolutions = sorted({int(value) for value in args.resolutions.split(",") if value.strip()})
    summary = build(args.roots or DEFAULT_ROOTS, args.out, args.preview, args.files,
                    resolutions, args.preview_files, args.scan, args.seed,
                    allow_empty_resolutions=args.allow_empty_resolutions)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
