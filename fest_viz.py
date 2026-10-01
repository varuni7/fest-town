"""Turn a run into a time-lapse you can watch.

Reads an evidence bundle and writes one self-contained HTML file. No
server, no assets, no network: the whole fest travels in the file.

Three panels. The ground, where people walk to the stall they chose.
Belief against quality, which is the result: red means a stall is
believed to be better than it is. The crowd strip, which is how many
people were on the ground at each hour of the day.

    python fest_viz.py runs/sim-xxxx -o fest.html
"""

from __future__ import annotations

import argparse
import json
import pathlib

PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Midway &middot; __TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Silkscreen:wght@400;700&display=swap"
      rel="stylesheet">
<style>
 :root{--bg:#ffffff;--paper:#faf8f3;--line:#ded8ca;--ink:#1b1d24;
       --dim:#6d7283;--over:#cf4233;--under:#2f6fc4;--gold:#c98b1b;
       --sky:#eef4fa;--ground:#e8dfcb;--px:"Silkscreen",ui-monospace,monospace;}
 *{box-sizing:border-box;margin:0}
 body{background:var(--bg);color:var(--ink);
      font:14px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace;
      padding:18px 16px;max-width:1040px;margin:0 auto}
 h1{font-family:var(--px);font-size:22px;font-weight:700;letter-spacing:2px;
    color:var(--ink)}
 h1 .tag{font-size:11px;color:var(--dim);letter-spacing:1px;margin-left:8px}
 .sub{color:var(--dim);font-size:12px;margin:2px 0 14px}
 h2{font-family:var(--px);font-size:11px;font-weight:400;letter-spacing:2px;
    color:var(--dim);margin:18px 0 6px}
 .bar{display:flex;gap:12px;align-items:center;margin-bottom:12px;
      flex-wrap:wrap}
 button,select{background:var(--paper);color:var(--ink);
   border:1px solid var(--line);border-radius:4px;padding:5px 11px;
   font:inherit;font-size:13px;cursor:pointer}
 button:hover{border-color:var(--dim)}
 #clock{font-size:21px;font-variant-numeric:tabular-nums;min-width:74px}
 #scrub{flex:1;min-width:170px;accent-color:var(--gold)}
 svg{width:100%;height:auto;display:block;
     image-rendering:pixelated;shape-rendering:crispEdges;
     border:1px solid var(--line);border-radius:6px}
 #stage{background:var(--sky)}
 #panel,#crowd{background:var(--paper)}
 .rbox{display:flex;gap:10px;align-items:baseline;margin:10px 0 4px;
       flex-wrap:wrap}
 .rbox .big{font-family:var(--px);font-size:19px}
 .rbox .what{color:var(--dim);font-size:12px}
 .legend{color:var(--dim);font-size:12px;margin-top:8px}
 .legend .sw{display:inline-block;width:9px;height:9px;margin-right:4px;
   vertical-align:baseline;border-radius:1px}
 #log{margin-top:12px;height:104px;overflow:auto;background:var(--paper);
      border:1px solid var(--line);border-radius:6px;padding:9px 11px;
      font-size:12px;color:var(--dim)}
 #log .hot{color:var(--over)}
 #log .ok{color:#1f7a4d}
 @media (max-width:600px){body{padding:14px 10px}h1{font-size:17px}}
</style></head><body>
<h1>MIDWAY <span class="tag">__TITLE__</span></h1>
<div class="sub">__SUB__</div>

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
     midway, people walking up from the gate to the stall they picked."></svg>

<h2>WHO IS ON THE GROUND</h2>
<svg id="crowd" viewBox="0 0 960 64" role="img"
     aria-label="How many people arrived in each hour of the day."></svg>

<h2>WHAT THE CROWD BELIEVES</h2>
<div class="rbox">
  <span class="big" id="rval">r = &mdash;</span>
  <span class="what">correlation between what a stall is worth and what
  it is rated. 1.0 is a crowd that is never wrong, 0 is noise, and below
  zero the ratings point the wrong way: following them is worse than
  picking at random.</span>
</div>
<svg id="panel" viewBox="0 0 960 __PH__" role="img"
     aria-label="One row per stall comparing its real quality with its
     reputation, and its share of all sales."></svg>
<div class="legend">
  Each row places a stall twice on the same line of six places. The
  <span class="sw" style="background:#1b1d24"></span>grey notch is where
  it belongs on quality. The coloured block is where the crowd put it.
  <span class="sw" style="background:#cf4233"></span>Red means the crowd
  rates it above where it belongs,
  <span class="sw" style="background:#2f6fc4"></span>blue below. The band
  is how many places out the crowd is.
</div>

<div id="log"></div>

<script>
const DATA = __DATA__;
const NS = 'http://www.w3.org/2000/svg';
const T_END = DATA.span, REAL = 180;          // 3 minutes at 1x
const W = 960, PX = 4;
const OVER = '#cf4233', UNDER = '#2f6fc4', INK = '#1b1d24', DIM = '#6d7283';

function el(t,a,p){const e=document.createElementNS(NS,t);
  for(const k in a) e.setAttribute(k,a[k]); if(p) p.appendChild(e); return e;}
function px(g,x,y,w,h,f){el('rect',{x:Math.round(x),y:Math.round(y),
  width:w*PX,height:h*PX,fill:f},g);}
function label(p,x,y,s,size,fill,anchor){
  const t=el('text',{x:x,y:y,'font-size':size||9,fill:fill||DIM,
    'text-anchor':anchor||'middle','font-family':'Silkscreen,monospace',
    'shape-rendering':'auto'},p); t.textContent=s; return t;}

/* ------------------------------------------------- the ground ----- */
const svg = document.getElementById('stage');
const boxes = {}, venues = {};
const cols = DATA.stalls.length, pad = 26, slot = (W-pad*2)/cols;
const BASE = 300, GATE = 382;

el('rect',{x:0,y:BASE,width:W,height:400-BASE,fill:'#e8dfcb'},svg);
el('rect',{x:0,y:BASE,width:W,height:2,fill:'#cfc4a8'},svg);

function stall(g,cx,base,w,hue){
  const bw = Math.min(w-18,108), x = cx-bw/2;
  for(let i=0;i<bw/PX;i+=2)                       // awning stripes
    px(g,x+i*PX,base-118,2,5,i%4===0?hue:'#ffffff');
  px(g,x,base-98,bw/PX,24,'#36405c');             // body
  px(g,x,base-98,bw/PX,2,'#55628a');              // counter lip
  px(g,x+3*PX,base-86,5,5,'#cfe2f5');             // windows
  px(g,x+bw-9*PX,base-86,5,5,'#cfe2f5');
  px(g,cx-3*PX,base-50,6,12,'#232b40');           // door
  px(g,cx-1*PX,base-138,2,5,'#8d9ab8');           // sign post
}
function stage(g,cx,base,w){
  const bw = Math.min(w-14,128), x = cx-bw/2;
  px(g,x,base-74,bw/PX,4,'#6d4b85');              // marquee
  for(let i=1;i<bw/PX;i+=3) px(g,x+i*PX,base-70,1,1,'#f0c04f');
  px(g,x+2*PX,base-58,(bw/PX)-4,14,'#3d3152');    // proscenium
  px(g,x+5*PX,base-52,(bw/PX)-10,9,'#211a2e');    // the dark stage
  px(g,x,base-6,bw/PX,2,'#8d9ab8');               // apron
}

(DATA.shows||[]).forEach((v,i)=>{
  const n = DATA.shows.length, sw = (W-pad*2)/n;
  const x = pad + i*sw + sw/2, g = el('g',{},svg);
  stage(g,x,92,sw);
  label(g,x,20,v.name.toUpperCase(),9,'#6d4b85');
  const seats = label(g,x,106,'0/'+v.capacity,9,DIM);
  venues[v.name]={x,seats,sold:0,cap:v.capacity};
});

DATA.stalls.forEach((s,i)=>{
  const x = pad + i*slot + slot/2, g = el('g',{},svg);
  stall(g,x,BASE,slot,s.hue);
  label(g,x,170,s.name.toUpperCase(),9,INK);
  const sold = label(g,x,320,'0 sold',9,DIM);
  boxes[s.name]={x,sold,n:0,hue:s.hue};
});
label(svg,W/2,396,'G A T E',9,DIM);

/* ------------------------------------------- the crowd strip ------ */
const cs = document.getElementById('crowd');
const CW = W-52, CX = 36;
(function(){
  const peak = Math.max(1,...DATA.crowd.map(b=>b.n));
  const bw = CW/DATA.crowd.length;
  DATA.crowd.forEach((b,i)=>{
    const h = Math.max(1,Math.round(b.n/peak*38));
    el('rect',{x:Math.round(CX+i*bw)+1,y:46-h,
      width:Math.max(2,Math.round(bw)-2),height:h,fill:'#c9d6e4'},cs);
  });
  el('line',{x1:CX,x2:CX+CW,y1:46,y2:46,stroke:'#ded8ca','stroke-width':1},cs);
  label(cs,CX,12,String(peak)+' PEAK/HR',8,DIM,'start');
  label(cs,CX,60,DATA.open,8,DIM,'start');
  label(cs,CX+CW,60,DATA.close,8,DIM,'end');
})();
const head = el('rect',{x:CX,y:6,width:2,height:40,fill:'#c98b1b'},cs);
const liveN = label(cs,CX+CW,12,'0 ARRIVED',8,'#c98b1b','end');

/* ------------------------------------------- belief vs quality ---- */
const pn = document.getElementById('panel');
const AX0 = 132, AXW = 452, SH0 = 640, SHW = 230;
const rows = {}, N = DATA.stalls.length;
const place = i => N>1 ? AX0 + (i/(N-1))*AXW : AX0 + AXW/2;
DATA.stalls.forEach((s,i)=>{
  const y = 26 + i*26, g = el('g',{},pn);
  label(g,AX0-12,y+4,s.name.toUpperCase(),9,INK,'end');
  el('rect',{x:AX0,y:y-1,width:AXW,height:2,fill:'#eae5d9'},g);
  const band = el('rect',{x:AX0,y:y-3,width:0,height:6,fill:OVER,
    opacity:0.7},g);
  const qt = el('rect',{x:AX0-1,y:y-9,width:3,height:18,fill:INK,
    opacity:0.2},g);
  const mark = el('rect',{x:AX0-3,y:y-7,width:6,height:14,fill:DIM,
    opacity:0},g);
  const gap = label(g,AX0+AXW+46,y+4,'',9,DIM,'end');
  const share = el('rect',{x:SH0,y:y-5,width:0,height:10,fill:s.hue},g);
  const pct = label(g,SH0+SHW+28,y+4,'0%',9,DIM,'end');
  rows[s.name]={y,q:s.quality,band,qt,mark,gap,share,pct,score:null};
});
for(let i=0;i<N;i++) el('rect',{x:place(i),y:20,width:1,height:4,
  fill:'#ded8ca'},pn);
label(pn,AX0,14,'WORST',8,DIM,'start');
label(pn,AX0+AXW,14,'BEST',8,DIM,'end');
label(pn,SH0,14,'SHARE OF ALL SALES',8,DIM,'start');

// Both sides sit on the same axis of places, so the band is a number
// of places and not a rating count held up against a quality score.
function ranks(vals){
  const order = vals.map((v,i)=>[v,i]).sort((a,b)=>a[0]-b[0]);
  const out = new Array(vals.length);
  order.forEach((p,i)=>{out[p[1]]=i;});
  return out;
}
function pearson(a,b){
  const n=a.length; if(n<2) return null;
  const ma=a.reduce((x,y)=>x+y,0)/n, mb=b.reduce((x,y)=>x+y,0)/n;
  let sab=0,sa=0,sb=0;
  for(let i=0;i<n;i++){const da=a[i]-ma,db=b[i]-mb;
    sab+=da*db; sa+=da*da; sb+=db*db;}
  return (sa&&sb) ? sab/Math.sqrt(sa*sb) : null;
}
function redrawPanel(){
  const live = DATA.stalls.filter(s=>rows[s.name].score!==null);
  const qr = ranks(live.map(s=>s.quality));
  const br = ranks(live.map(s=>rows[s.name].score));
  live.forEach((s,i)=>{
    const r=rows[s.name], qx=place(qr[i]), bx=place(br[i]), d=br[i]-qr[i];
    r.qt.setAttribute('x',qx-1); r.qt.setAttribute('opacity',0.85);
    r.mark.setAttribute('x',bx-3); r.mark.setAttribute('opacity',1);
    r.mark.setAttribute('fill', d>0?OVER : d<0?UNDER : DIM);
    r.band.setAttribute('x',Math.min(qx,bx));
    r.band.setAttribute('width',Math.abs(qx-bx));
    r.band.setAttribute('fill', d>0?OVER:UNDER);
    r.gap.textContent = d===0 ? 'right' :
      (d>0?'+':'')+d+(Math.abs(d)===1?' place':' places');
    r.gap.setAttribute('fill', d>0?OVER : d<0?UNDER : DIM);
  });
  const rr = pearson(live.map(s=>s.quality),
                     live.map(s=>rows[s.name].score));
  const out = document.getElementById('rval');
  if(rr===null){out.textContent='r = n/a'; out.style.color=DIM; return;}
  out.textContent = 'r = '+(rr>=0?'+':'')+rr.toFixed(2);
  out.style.color = rr>=0.5 ? '#1f7a4d' : rr>=0 ? '#c98b1b' : OVER;
}


/* ------------------------------------------------- playback ------- */
const log = document.getElementById('log');
const layer = el('g',{},svg);
let t=0, playing=true, idx=0, speed=1, dots=[], arrived=0, totalSales=0;

function reset(){
  idx=0; arrived=0; totalSales=0;
  dots.forEach(d=>d.e.remove()); dots=[]; log.innerHTML='';
  for(const k in boxes){const b=boxes[k]; b.n=0; b.sold.textContent='0 sold';}
  for(const k in venues){const v=venues[k]; v.sold=0;
    v.seats.textContent='0/'+v.cap;}
  for(const k in rows){const r=rows[k]; r.score=null;
    r.mark.setAttribute('opacity',0); r.qt.setAttribute('opacity',0.2);
    r.band.setAttribute('width',0); r.gap.textContent='';
    r.share.setAttribute('width',0); r.pct.textContent='0%';}
  redrawPanel();
}
function say(txt,cls){
  const d=document.createElement('div'); if(cls) d.className=cls;
  d.textContent=txt; log.appendChild(d); log.scrollTop=log.scrollHeight;
}
function walker(x1,y1,fill){
  const d=el('rect',{x:W/2,y:GATE,width:4,height:4,fill:fill},layer);
  dots.push({e:d,x0:W/2,y0:GATE,x1:x1,y1:y1,born:t});
  arrived++;
}
function shares(){
  for(const k in rows){const r=rows[k], b=boxes[k];
    const f = totalSales ? b.n/totalSales : 0;
    r.share.setAttribute('width',f*SHW);
    r.pct.textContent=Math.round(f*100)+'%';}
}
function apply(e){
  const b=boxes[e.s], r=rows[e.s];
  if(e.k==='considered' && b){ walker(b.x,BASE+14,'#36405c'); }
  else if(e.k==='bought' && b){ b.n++; totalSales++;
    b.sold.textContent=b.n+' sold'; shares(); }
  else if(e.k==='rep' && r){ r.score = e.v; redrawPanel(); }
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
function fmt(lt){const m=Math.round(DATA.t0*60+lt*DATA.mins);
  return String(Math.floor(m/60)).padStart(2,'0')+':'+
         String(Math.round(m%60)).padStart(2,'0');}

let last=performance.now();
function frame(now){
  const dt=(now-last)/1000; last=now;
  if(playing){
    t += dt*(T_END/REAL)*speed;
    if(t>=T_END){t=T_END; playing=false;
      document.getElementById('play').textContent='replay';}
  }
  while(idx<DATA.ev.length && DATA.ev[idx].t<=t){apply(DATA.ev[idx]); idx++;}
  dots = dots.filter(d=>{
    const k=Math.min(1,(t-d.born)/1.6);
    d.e.setAttribute('x', d.x0+(d.x1-d.x0)*k);
    d.e.setAttribute('y', d.y0+(d.y1-d.y0)*k);
    if(k>=1){d.e.remove(); return false;} return true;});
  head.setAttribute('x', CX + (t/T_END)*CW);
  liveN.textContent = arrived+' ARRIVED';
  document.getElementById('clock').textContent=fmt(t);
  document.getElementById('scrub').value=Math.round(t/T_END*1000);
  requestAnimationFrame(frame);
}
document.getElementById('play').onclick=e=>{
  if(t>=T_END){reset(); t=0;}
  playing=!playing; e.target.textContent=playing?'pause':'play';};
document.getElementById('speed').onchange=e=>speed=+e.target.value;
document.getElementById('scrub').oninput=e=>{
  const nt=e.target.value/1000*T_END;
  if(nt<t){reset();} t=nt;};
requestAnimationFrame(frame);
</script></body></html>
"""

T0_HOUR = 8.0        # the fest opens at 08:00
MINS_PER_UNIT = 12.0  # one unit of logical time


def build(bundle: str, out: str) -> str:
    b = pathlib.Path(bundle)
    prof = json.loads((b / "profile.json").read_text())
    events = [json.loads(l) for l in (b / "events.jsonl").read_text().splitlines()]

    HUES = ["#e0674f", "#c98b1b", "#3f9d6d", "#3f7fc4", "#8f63b0",
            "#c4648f", "#6fa345", "#a89425", "#3fa79a"]
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
    # one line per attack burst, not one per rating
    seen, trimmed = set(), []
    for e in ev:
        if e["k"] == "note" and "ignored a rating" in e.get("m", ""):
            if e["m"] in seen:
                continue
            seen.add(e["m"])
        trimmed.append(e)

    span = max((e["t"] for e in ev), default=1.0) or 1.0

    # Who was on the ground, by the hour. An arrival is an attendee
    # choosing a stall or a ticket holder walking into a venue.
    hours = max(1, int(span / (60.0 / MINS_PER_UNIT)) + 1)
    crowd = [{"n": 0} for _ in range(hours)]
    for e in trimmed:
        if e["k"] in ("considered", "enter"):
            crowd[min(hours - 1, int(e["t"] / (60.0 / MINS_PER_UNIT)))]["n"] += 1

    def clock(units: float) -> str:
        m = round(T0_HOUR * 60 + units * MINS_PER_UNIT)
        return f"{int(m // 60):02d}:{int(m % 60):02d}"

    data = {"stalls": stalls, "shows": shows, "ev": trimmed, "span": span,
            "crowd": crowd,
            "t0": T0_HOUR, "mins": MINS_PER_UNIT,
            "open": clock(0), "close": clock(span)}

    sold = sum(1 for e in trimmed if e["k"] == "bought")
    shown = sum(1 for e in trimmed if e["k"] == "ticket")
    back = sum(1 for e in trimmed if e["k"] == "refund")
    people = sum(c["n"] for c in crowd)
    sub = (f"{len(stalls)} stalls &middot; {len(shows)} shows &middot; "
           f"{people} people through the gate &middot; {sold} purchases "
           f"&middot; {shown} tickets, {back} refunded &middot; "
           f"{clock(0)} to {clock(span)}")
    html = (PAGE.replace("__DATA__", json.dumps(data))
                .replace("__TITLE__", prof.get("name", "fest"))
                .replace("__PH__", str(26 + len(stalls) * 26 + 10))
                .replace("__SUB__", sub))
    pathlib.Path(out).write_text(html)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle")
    ap.add_argument("-o", "--out", default="fest.html")
    a = ap.parse_args()
    print("wrote", build(a.bundle, a.out))
