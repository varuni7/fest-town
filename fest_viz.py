"""Turn runs into one page you can watch.

Reads evidence bundles and writes a single self-contained HTML file. No
server, no assets, no network: the whole fest travels in the file. Give
it more than one bundle and the page carries a switch between them,
which is how the same day under two trust layers sits side by side.

The page is the fest ground. People come through the gate, walk to the
stall they picked, and fill the venues, with a running log of what the
agents are doing to each other.

    python fest_viz.py runs/sim-aaa runs/sim-bbb -o index.html
"""

from __future__ import annotations

import argparse
import json
import pathlib

T0_HOUR = 8.0         # the fest opens at 08:00
MINS_PER_UNIT = 12.0   # one unit of logical time

PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fest Town</title>
<meta name="description" content="A college fest as a multi-agent
 simulation. A whole day plays in three minutes.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Silkscreen:wght@400;700&display=swap"
      rel="stylesheet">
<style>
 :root{--bg:#ffffff;--paper:#faf8f3;--line:#ded8ca;--ink:#1b1d24;
       --dim:#6d7283;--over:#cf4233;--under:#2f6fc4;--good:#1f7a4d;
       --gold:#c98b1b;--sky:#eef4fa;--ground:#e8dfcb;
       --px:"Silkscreen",ui-monospace,monospace;}
 *{box-sizing:border-box;margin:0}
 body{background:var(--bg);color:var(--ink);
      font:14px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace;
      padding:16px 14px 44px;max-width:1040px;margin:0 auto}
 h1{font-family:var(--px);font-size:21px;font-weight:700;letter-spacing:3px}
 .tag{color:var(--dim);font-size:12.5px;margin:5px 0 0;
      font-family:var(--px);letter-spacing:1px}
 ol.why{margin:9px 0 14px 19px;font-size:12.5px;color:var(--dim);
        line-height:1.5}
 ol.why li{margin-bottom:3px}
 ol.why b{color:var(--ink);font-weight:700}
 .who{border-left:2px solid var(--line);padding:1px 0 1px 11px;
      margin:0 0 15px 2px;font-size:12.5px;color:var(--dim);
      line-height:1.5}
 .who p{margin-bottom:5px}
 .who b{color:var(--ink);font-weight:700}
 .who code{background:var(--paper);border:1px solid var(--line);
   border-radius:3px;padding:0 3px;font-size:11.5px}
 h2{font-family:var(--px);font-size:10px;font-weight:400;letter-spacing:2px;
    color:var(--dim);margin:16px 0 6px}
 .tabs{display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap}
 .tab{background:var(--paper);border:1px solid var(--line);border-radius:6px;
      padding:7px 13px;cursor:pointer;font:inherit;font-size:12.5px;
      text-align:left;line-height:1.35}
 .tab:hover{border-color:var(--dim)}
 .tab[aria-selected="true"]{border-color:var(--ink);background:#fff;
   box-shadow:inset 0 0 0 1px var(--ink)}
 .tab .k{font-family:var(--px);font-size:14px;display:block}
 .tab .v{color:var(--dim);font-size:11.5px}
 .tab.bad .k{color:var(--over)} .tab.good .k{color:var(--good)}
 .bar{display:flex;gap:11px;align-items:center;margin:10px 0;flex-wrap:wrap}
 button,select{background:var(--paper);color:var(--ink);
   border:1px solid var(--line);border-radius:4px;padding:5px 11px;
   font:inherit;font-size:13px;cursor:pointer}
 button:hover{border-color:var(--dim)}
 #clock{font-size:20px;font-variant-numeric:tabular-nums;min-width:70px}
 #scrub{flex:1;min-width:150px;accent-color:var(--gold)}
 svg{width:100%;height:auto;display:block;
     image-rendering:pixelated;shape-rendering:crispEdges;
     border:1px solid var(--line);border-radius:6px}
 #stage{background:var(--sky)}
 #log{margin-top:10px;height:92px;overflow:auto;background:var(--paper);
      border:1px solid var(--line);border-radius:6px;padding:8px 11px;
      font-size:12px;color:var(--dim)}
 #log .hot{color:var(--over)}
 #log .ok{color:var(--good)}
 .foot{color:var(--dim);font-size:11.5px;margin-top:22px;
       border-top:1px solid var(--line);padding-top:11px}
 @media (max-width:620px){h1{font-size:16px}body{padding:14px 10px 36px}}
</style></head><body>

<h1>FEST TOWN</h1>
<div class="tag">a college fest, simulated</div>
<ol class="why">
<li>Every stall, student, box office, stage and band is its own agent.
Nothing can see the whole ground.</li>
<li>Students find stalls from the cards stalls publish, tickets are
issued, passed on and refunded through a fake payment gateway, students
rate the stalls they buy from, and bands bid for stage slots.</li>
<li>A whole fest day plays here in three minutes. Watch people come
through the gate, pick a stall, and fill the venues.</li>
</ol>

<div class="who">
<p><b>Everything you are watching is scripted.</b> Every stall, student,
box office, stage and band is a small state machine, which is why a day
replays exactly from its seed and costs nothing to run.</p>
<p>One role can be model-driven instead: <code>llm_stall</code> asks a
model for its next price every hour, given its own sales, its stock and
what the stalls either side of it charge. The floor and ceiling are
clamped in code, so the model picks inside bounds it cannot talk its way
out of.</p>
<p>That version runs in its own scenario and not here, because a model
call per stall per hour makes the day slow and gives up determinism. The
trace still records every prompt and reply, so the run stays replayable,
but the same seed stops reproducing the same fest.</p>
</div>

<div class="tabs" id="tabs" role="tablist"></div>

<div class="bar">
  <button id="play">pause</button>
  <span id="clock">08:00</span>
  <input type="range" id="scrub" min="0" max="1000" value="0">
  <select id="speed">
    <option value="0.5">0.5x</option>
    <option value="1" selected>1x &middot; 3 min</option>
    <option value="2">2x</option>
    <option value="4">4x</option>
  </select>
</div>

<svg id="stage" viewBox="0 0 960 400" role="img"
     aria-label="The fest ground: stages at the top, stalls along the
     avenue, people walking up from the gate to the stall they picked."></svg>

<div id="log"></div>

<div class="foot">Built from one run's evidence bundle, with no server and
no network behind it. Code and scenarios:
<a href="https://github.com/varuni7/fest-town">github.com/varuni7/fest-town</a>.</div>

<script>
const ALL = __DATA__;
const NS = 'http://www.w3.org/2000/svg';
const REAL = 180;                             // 3 minutes at 1x
const W = 960, PX = 4, pad = 26;
const BASE = 300, GATE = 382;
const OVER = '#cf4233', UNDER = '#2f6fc4', INK = '#1b1d24', DIM = '#6d7283';

const svg = document.getElementById('stage');
const log = document.getElementById('log');

function el(t,a,p){const e=document.createElementNS(NS,t);
  for(const k in a) e.setAttribute(k,a[k]); if(p) p.appendChild(e); return e;}
function px(g,x,y,w,h,f){el('rect',{x:Math.round(x),y:Math.round(y),
  width:w*PX,height:h*PX,fill:f},g);}
function label(p,x,y,s,size,fill,anchor){
  const t=el('text',{x:x,y:y,'font-size':size||9,fill:fill||DIM,
    'text-anchor':anchor||'middle','font-family':'Silkscreen,monospace',
    'shape-rendering':'auto'},p); t.textContent=s; return t;}
function clear(node){while(node.firstChild) node.removeChild(node.firstChild);}

function stall(g,cx,base,w,hue){
  const bw = Math.min(w-18,108), x = cx-bw/2;
  for(let i=0;i<bw/PX;i+=2)
    px(g,x+i*PX,base-118,2,5,i%4===0?hue:'#ffffff');
  px(g,x,base-98,bw/PX,24,'#36405c');
  px(g,x,base-98,bw/PX,2,'#55628a');
  px(g,x+3*PX,base-86,5,5,'#cfe2f5');
  px(g,x+bw-9*PX,base-86,5,5,'#cfe2f5');
  px(g,cx-3*PX,base-50,6,12,'#232b40');
  px(g,cx-1*PX,base-138,2,5,'#8d9ab8');
}
function stageBox(g,cx,base,w){
  const bw = Math.min(w-14,128), x = cx-bw/2;
  px(g,x,base-74,bw/PX,4,'#6d4b85');
  for(let i=1;i<bw/PX;i+=3) px(g,x+i*PX,base-70,1,1,'#f0c04f');
  px(g,x+2*PX,base-58,(bw/PX)-4,14,'#3d3152');
  px(g,x+5*PX,base-52,(bw/PX)-10,9,'#211a2e');
  px(g,x,base-6,bw/PX,2,'#8d9ab8');
}

/* ---------------------------------------------- state per run ----- */
let D = null, boxes = {}, venues = {}, N = 0;
let layer = null;
let t = 0, playing = true, idx = 0, speed = 1, dots = [];
let arrived = 0, totalSales = 0, last = performance.now();

function scene(run){
  D = run; N = D.stalls.length;
  boxes = {}; venues = {}; dots = [];
  clear(svg); log.innerHTML = '';

  el('rect',{x:0,y:BASE,width:W,height:400-BASE,fill:'#e8dfcb'},svg);
  el('rect',{x:0,y:BASE,width:W,height:2,fill:'#cfc4a8'},svg);

  (D.shows||[]).forEach((v,i)=>{
    const n = D.shows.length, sw = (W-pad*2)/n;
    const x = pad + i*sw + sw/2, g = el('g',{},svg);
    stageBox(g,x,92,sw);
    label(g,x,20,v.name.toUpperCase(),9,'#6d4b85');
    venues[v.name]={x,seats:label(g,x,106,'0/'+v.capacity,9,DIM),
                    sold:0,cap:v.capacity};
  });

  const slot = (W-pad*2)/N;
  D.stalls.forEach((s,i)=>{
    const x = pad + i*slot + slot/2, g = el('g',{},svg);
    stall(g,x,BASE,slot,s.hue);
    label(g,x,170,s.name.toUpperCase(),9,INK);
    boxes[s.name]={x,sold:label(g,x,320,'0 sold',9,DIM),n:0,hue:s.hue};
  });
  label(svg,W/2,396,'G A T E',9,DIM);
  layer = el('g',{},svg);

  t = 0; idx = 0; arrived = 0; totalSales = 0; playing = true;
  // Without this the first frame after a switch sees the gap since the
  // last one as elapsed fest time and jumps the clock.
  last = performance.now();
  document.getElementById('play').textContent = 'pause';
}

/* ------------------------------------------------- playback ------- */
function say(txt,cls){
  const d=document.createElement('div'); if(cls) d.className=cls;
  d.textContent=txt; log.appendChild(d); log.scrollTop=log.scrollHeight;
}
function walker(x1,y1,fill){
  const d=el('rect',{x:W/2,y:GATE,width:4,height:4,fill:fill},layer);
  dots.push({e:d,x0:W/2,y0:GATE,x1:x1,y1:y1,born:t});
  arrived++;
}
function fmt(lt){const m=Math.round(ALL.t0*60+lt*ALL.mins);
  return String(Math.floor(m/60)).padStart(2,'0')+':'+
         String(Math.round(m%60)).padStart(2,'0');}
function apply(e){
  const b=boxes[e.s];
  if(e.k==='considered' && b){ walker(b.x,BASE+14,'#36405c'); }
  else if(e.k==='bought' && b){ b.n++; totalSales++;
    b.sold.textContent=b.n+' sold'; }
  else if(e.k==='ticket'){const v=venues[e.s];
    if(v){v.sold++; v.seats.textContent=v.sold+'/'+v.cap;}}
  else if(e.k==='refund'){const v=venues[e.s];
    if(v){v.sold=Math.max(0,v.sold-1); v.seats.textContent=v.sold+'/'+v.cap;}
    say(fmt(e.t)+'  '+e.m);}
  else if(e.k==='enter'){const v=venues[e.s];
    if(v) walker(v.x,116,'#6d4b85');}
  else if(e.k==='attack'){ say(fmt(e.t)+'  '+e.m,'hot'); }
  else if(e.k==='note'){ say(fmt(e.t)+'  '+e.m,'ok'); }
}

function frame(now){
  const dt=(now-last)/1000; last=now;
  const END = D.span;
  if(playing){
    t += dt*(END/REAL)*speed;
    if(t>=END){t=END; playing=false;
      document.getElementById('play').textContent='replay';}
  }
  while(idx<D.ev.length && D.ev[idx].t<=t){apply(D.ev[idx]); idx++;}
  dots = dots.filter(d=>{
    const k=Math.min(1,(t-d.born)/1.6);
    d.e.setAttribute('x', d.x0+(d.x1-d.x0)*k);
    d.e.setAttribute('y', d.y0+(d.y1-d.y0)*k);
    if(k>=1){d.e.remove(); return false;} return true;});
  document.getElementById('clock').textContent=fmt(t);
  document.getElementById('scrub').value=Math.round(t/END*1000);
  requestAnimationFrame(frame);
}

/* --------------------------------------------- the run switch ----- */
const want = (location.hash || '').replace('#','').toLowerCase();
let cur = Math.max(0, ALL.runs.findIndex(r=>r.slug===want));
const tabs = document.getElementById('tabs');
ALL.runs.forEach((run,i)=>{
  const b=document.createElement('button');
  b.className='tab '+(run.tone||'');
  b.setAttribute('role','tab');
  b.setAttribute('aria-selected', i===cur ? 'true' : 'false');
  b.innerHTML='<span class="k">'+run.headline+'</span>'+
              '<span class="v">'+run.label+'</span>';
  b.onclick=()=>{cur=i; scene(ALL.runs[i]);
    if(history.replaceState) history.replaceState(null,'','#'+run.slug);
    [...tabs.children].forEach((c,j)=>
      c.setAttribute('aria-selected', i===j ? 'true' : 'false'));};
  tabs.appendChild(b);
});
if(ALL.runs.length<2) tabs.style.display='none';

document.getElementById('play').onclick=e=>{
  if(t>=D.span){scene(ALL.runs[cur]); return;}
  playing=!playing; e.target.textContent=playing?'pause':'play';};
document.getElementById('speed').onchange=e=>speed=+e.target.value;
document.getElementById('scrub').oninput=e=>{
  const nt=e.target.value/1000*D.span;
  if(nt<t){const was=playing; scene(ALL.runs[cur]); playing=was;}
  t=nt;};

scene(ALL.runs[cur]);
requestAnimationFrame(frame);
</script></body></html>
"""

HUES = ["#e0674f", "#c98b1b", "#3f9d6d", "#3f7fc4", "#8f63b0",
        "#c4648f", "#6fa345", "#a89425", "#3fa79a"]


def clock(units: float) -> str:
    m = round(T0_HOUR * 60 + units * MINS_PER_UNIT)
    return f"{int(m // 60):02d}:{int(m % 60):02d}"


def one_run(bundle: str) -> dict:
    b = pathlib.Path(bundle)
    prof = json.loads((b / "profile.json").read_text())
    events = [json.loads(l) for l in (b / "events.jsonl").read_text().splitlines()]

    stalls = [{"name": a["name"],
               "quality": float(a["config"].get("quality", 0.5)),
               "hue": HUES[i % len(HUES)]}
              for i, a in enumerate(a for a in prof["agents"]
              if a["role"] in ("stall", "smear_stall", "llm_stall"))]
    names = {s["name"] for s in stalls}
    shows = [{"name": a["config"]["show"],
              "capacity": int(a["config"].get("capacity", 0))}
             for a in prof["agents"] if a["role"] == "box_office"]

    ev = []
    for e in events:
        k, s, d, t = e["kind"], e["subject"], e["detail"], e["at"]
        if k == "considered" and d.get("chose") in names:
            ev.append({"t": t, "k": "considered", "s": d["chose"]})
        elif k == "bought" and s in names:
            ev.append({"t": t, "k": "bought", "s": s})
        elif k == "reputation_updated" and s in names:
            ev.append({"t": t, "k": "rep", "s": s, "v": d.get("score", 0)})
        elif k == "smeared":
            ev.append({"t": t, "k": "attack",
                       "m": f"{s} rated its rivals down {d['count']} times"})
        elif k == "shilled":
            ev.append({"t": t, "k": "attack",
                       "m": f"{d['by']} praised {s} {d['count']} times "
                            f"without buying anything"})
        elif k == "rating_ignored":
            ev.append({"t": t, "k": "note",
                       "m": f"trust layer ignored a rating of {s}: "
                            f"{d.get('reason','')}"})
        elif k == "ticket_issued":
            ev.append({"t": t, "k": "ticket", "s": d.get("show", "")})
        elif k == "ticket_refunded":
            ev.append({"t": t, "k": "refund", "s": d.get("show", ""),
                       "m": f"{d.get('held_by')} returned {s}"})
        elif k == "admitted":
            ev.append({"t": t, "k": "enter", "s": d.get("show", "")})
        elif k == "repriced":
            ev.append({"t": t, "k": "note",
                       "m": f"{s} moved its price {d['from']} -> {d['to']}"})
    ev.sort(key=lambda x: x["t"])

    seen, trimmed = set(), []
    for e in ev:
        if e["k"] == "note" and "ignored a rating" in e.get("m", ""):
            if e["m"] in seen:
                continue
            seen.add(e["m"])
        trimmed.append(e)

    span = max((e["t"] for e in trimmed), default=1.0) or 1.0

    # Who was on the ground, by the hour. An arrival is an attendee
    # choosing a stall or a ticket holder walking into a venue.
    per_hour = 60.0 / MINS_PER_UNIT
    hours = max(1, int(span / per_hour) + 1)
    crowd = [{"n": 0} for _ in range(hours)]
    for e in trimmed:
        if e["k"] in ("considered", "enter"):
            crowd[min(hours - 1, int(e["t"] / per_hour))]["n"] += 1

    return {"name": prof.get("name", "fest"), "stalls": stalls,
            "shows": shows, "ev": trimmed, "span": span, "crowd": crowd,
            "open": clock(0), "close": clock(span)}


def describe(run: dict) -> tuple[str, str, str]:
    """Headline, caption and tone for this run's tab."""
    qual = {s["name"]: s["quality"] for s in run["stalls"]}
    last, bought = {}, {}
    for e in run["ev"]:
        if e["k"] == "rep":
            last[e["s"]] = e["v"]
        elif e["k"] == "bought":
            bought[e["s"]] = bought.get(e["s"], 0) + 1
    pairs = [(qual[n], last[n]) for n in last if n in qual]
    r = None
    if len(pairs) > 1:
        n = len(pairs)
        mq = sum(p[0] for p in pairs) / n
        mr = sum(p[1] for p in pairs) / n
        sab = sum((p[0] - mq) * (p[1] - mr) for p in pairs)
        sa = sum((p[0] - mq) ** 2 for p in pairs)
        sb = sum((p[1] - mr) ** 2 for p in pairs)
        r = sab / (sa * sb) ** 0.5 if sa and sb else None
    ignored = sum(1 for e in run["ev"]
                  if e["k"] == "note" and "ignored a rating" in e.get("m", ""))
    top = max(bought, key=lambda k: (bought[k], k)) if bought else None
    tot = sum(bought.values()) or 1
    head = f"r = {r:+.2f}" if r is not None else run["name"]
    if top:
        cap = (f"top seller {top}, quality {qual.get(top, 0):.2f},"
               f" {bought[top] / tot:.0%} of trade")
    else:
        cap = run["name"]
    cap += (" · ratings must be earned" if ignored
            else " · anyone can rate anything")
    tone = "good" if (r or 0) >= 0.5 else "bad"
    return head, cap, tone


def build(bundles: list[str], out: str) -> str:
    runs = []
    for b in bundles:
        run = one_run(b)
        run["headline"], run["label"], run["tone"] = describe(run)
        run["slug"] = run["name"].split("_")[-1]
        # describe() needed the rating scores; the page does not draw
        # them, so they do not travel.
        run["ev"] = [e for e in run["ev"] if e["k"] != "rep"]
        run.pop("crowd", None)
        runs.append(run)
    data = {"t0": T0_HOUR, "mins": MINS_PER_UNIT, "runs": runs}
    pathlib.Path(out).write_text(PAGE.replace("__DATA__", json.dumps(data)))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle", nargs="+")
    ap.add_argument("-o", "--out", default="index.html")
    a = ap.parse_args()
    print("wrote", build(a.bundle, a.out))
