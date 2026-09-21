"""The page shell: CSS and the small amount of JavaScript."""



CSS = """
:root{--bg:#0b1220;--panel:#101a2e;--panel2:#16233c;--ink:#e6edf7;--dim:#8fa3bf;
--line:#1e2c47;--accent:#38bdf8;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 ui-sans-serif,system-ui,"Noto Sans SC",sans-serif}
header.top{position:sticky;top:0;z-index:5;background:linear-gradient(180deg,#0b1220,#0d1526);border-bottom:1px solid var(--line);padding:14px 20px}
h1{font-size:17px;margin:0 0 4px}
.meta{color:var(--dim);font-size:12px}
nav{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}
nav button{background:var(--panel);color:var(--ink);border:1px solid var(--line);padding:6px 12px;border-radius:999px;cursor:pointer;font-size:13px}
nav button[aria-selected=true]{background:var(--accent);color:#062133;border-color:var(--accent);font-weight:600}
main{padding:18px 20px 60px}
section.pane{display:none}section.pane.active{display:block}
h3{margin:18px 0 6px;font-size:14px;text-transform:uppercase;letter-spacing:.06em;color:var(--dim)}
h4{margin:16px 0 6px;font-size:13px;color:var(--ink)}
.board{display:flex;gap:12px;overflow-x:auto;align-items:flex-start;padding-bottom:8px}
.col{min-width:260px;flex:1 0 260px;background:var(--panel);border:1px solid var(--line);border-radius:10px}
.col h3{display:flex;align-items:center;gap:6px;margin:0;padding:10px 12px;border-bottom:1px solid var(--line);text-transform:none;letter-spacing:0;color:var(--ink);font-size:13px}
.count{color:var(--dim);font-weight:400}
.colbody{padding:10px;display:flex;flex-direction:column;gap:10px;max-height:70vh;overflow:auto}
.card{background:var(--panel2);border:1px solid var(--line);border-radius:8px;padding:10px}
.card header{display:flex;gap:8px;align-items:baseline}
.card h4{margin:0;font-size:13px;font-weight:600}
.tid{color:var(--accent);font:600 11px ui-monospace,monospace}
.chips{display:flex;flex-wrap:wrap;gap:4px;margin-top:8px}
.chip{font-size:11px;padding:1px 6px;border-radius:999px;background:#1b2a44;color:var(--dim);border:1px solid var(--line)}
.chip.draft{background:#3b2a12;color:#fbbf24;border-color:#5b4318}
.chip.blocker{background:#3b1414;color:#fca5a5}
.chip.due.overdue{background:#3b1414;color:#fca5a5}
.chip.seed{background:#14243b;color:#7dd3fc}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block;background:#64748b}
.s-backlog{background:#94a3b8}.s-ready{background:#60a5fa}.s-doing{background:#f59e0b}
.s-review{background:#a78bfa}.s-done{background:#34d399}.s-blocked{background:#ef4444}.s-dropped{background:#9ca3af}
.stats{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:10px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:8px 12px;display:flex;align-items:center;gap:8px;font-size:12px;color:var(--dim)}
.stat b{font-size:18px;color:var(--ink)}
.gantt{background:var(--panel);border:1px solid var(--line);border-radius:10px}
.gantt text{font:11px ui-monospace,monospace;fill:var(--dim)}
.gantt .rlabel{fill:var(--ink)}
.gantt .mslabel{fill:#7dd3fc;font-weight:600}
.gantt .barlabel{fill:var(--dim)}
.msbg{fill:#0e1a30}
.grid{stroke:#182741;stroke-width:1}
.grid.week{stroke:#24365a}
.axis{font-size:10px}
.bar{opacity:.85}
.dep{fill:none;stroke:#5b7ba8;stroke-width:1.2;stroke-dasharray:3 2}
.msdiamond{fill:#38bdf8;stroke:#0b1220}
.today{stroke:#f87171;stroke-width:1.4;stroke-dasharray:4 3}
.todaylabel{fill:#f87171}
.legend{display:flex;gap:10px;flex-wrap:wrap;font-size:12px;color:var(--dim);margin:0 0 8px}
.lg{display:flex;align-items:center;gap:4px}
table.items{width:100%;border-collapse:collapse;font-size:12.5px;background:var(--panel);border:1px solid var(--line);border-radius:8px;overflow:hidden}
table.items th{text-align:left;background:#0e1a30;color:var(--dim);font-weight:600;padding:7px 9px;border-bottom:1px solid var(--line)}
table.items td{padding:7px 9px;border-bottom:1px solid #16233c;vertical-align:top}
td.overdue{color:#fca5a5}
.filters{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:10px;font-size:12px;color:var(--dim)}
.filters select,.filters input{background:var(--panel);color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:4px 6px}
ul.plain{list-style:none;padding-left:0}ul.plain>li{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:8px 10px;margin-bottom:6px}
p.dim,.dim{color:var(--dim)}
.note{color:var(--dim);font-size:12.5px;background:#0e1a30;border-left:3px solid var(--accent);padding:8px 10px;border-radius:0 6px 6px 0}
.warn{color:#fca5a5}.ok{color:#6ee7b7}
.meter{display:inline-block;width:110px;height:8px;background:#1b2a44;border-radius:999px;overflow:hidden;vertical-align:middle}
.meter>span{display:block;height:100%;background:#34d399}
.stalebar{position:sticky;top:0;z-index:9;background:#3b2a12;color:#fbbf24;border-bottom:1px solid #5b4318;
padding:7px 20px;font-size:12.5px;display:flex;gap:10px;align-items:center}
.stalebar button{background:#fbbf24;color:#3b2a12;border:0;border-radius:999px;padding:3px 12px;font-weight:600;cursor:pointer}
details summary{cursor:pointer;color:var(--dim);font-size:12px;margin-top:6px}
details p{margin:6px 0 0;color:var(--dim);font-size:12.5px}
.reason{margin:8px 0 0;color:#fca5a5;font-size:12.5px}
.empty{color:var(--dim);font-size:12.5px;font-style:italic}
.msg{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:8px 10px;margin-bottom:6px}
.msg header{display:flex;gap:8px;align-items:center;font-size:12.5px;flex-wrap:wrap}
.msg pre{white-space:pre-wrap;word-break:break-word;margin:6px 0 0;font:12.5px/1.5 ui-monospace,monospace;color:#cbd5e1}
.burndown{background:var(--panel);border:1px solid var(--line);border-radius:10px}
.burndown .line{fill:none;stroke:#38bdf8;stroke-width:2}
.burndown .thr{fill:#34d399;opacity:.55}
.burndown .axis{font:10px ui-monospace,monospace;fill:var(--dim)}
"""


JS = """
function showTab(name){
  var b=document.querySelector('nav button[data-tab="'+name+'"]');
  if(!b) return false;
  document.querySelectorAll('nav button').forEach(function(x){x.setAttribute('aria-selected','false')});
  document.querySelectorAll('section.pane').forEach(function(p){p.classList.remove('active')});
  b.setAttribute('aria-selected','true');
  document.getElementById('pane-'+name).classList.add('active');
  return true;
}
document.querySelectorAll('nav button').forEach(function(b){
  b.addEventListener('click', function(){
    if(showTab(b.dataset.tab)) history.replaceState(null,'','#'+b.dataset.tab);
  });
});
if(!showTab((location.hash||'').replace('#','')) && location.hash) showTab('overview');
function applyFilters(){
  var f={};
  document.querySelectorAll('[data-filter]').forEach(function(el){f[el.dataset.filter]=el.value.trim().toLowerCase()});
  document.querySelectorAll('table.items tbody tr, .board .card').forEach(function(el){
    var ok=true;
    if(f.owner && (el.dataset.owner||'').toLowerCase().indexOf(f.owner)<0) ok=false;
    if(f.status && (el.dataset.status||'')!==f.status) ok=false;
    if(f.milestone && (el.dataset.milestone||'')!==f.milestone) ok=false;
    if(f.tag && (el.dataset.tags||'').toLowerCase().indexOf(f.tag)<0) ok=false;
    el.style.display = ok ? '' : 'none';
  });
}
document.querySelectorAll('[data-filter]').forEach(function(el){el.addEventListener('input',applyFilters)});

// Poll for change and say so. A dashboard that reloads itself takes the page away
// from the person reading it; a banner lets them finish the sentence first.
if(window.__pollMs > 0){
  setInterval(function(){
    if(document.hidden) return;
    fetch('/state.json', {cache:'no-store'}).then(function(r){return r.json()}).then(function(s){
      if(s.digest && window.__digest && s.digest !== window.__digest){
        document.getElementById('stale').hidden = false;
      }
    }).catch(function(){});
  }, window.__pollMs);
}
"""
