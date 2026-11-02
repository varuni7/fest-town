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
 :root{
   --bg:#0b0d12; --panel:#141821; --panel2:#1a1f2b; --line:#262c3a;
   --ink:#eef1f7; --dim:#949db4; --faint:#6b7488;
   --over:#ff6b5a; --under:#5b9dff; --good:#3ddc97; --gold:#ffc44d;
   --sky:#0e1420; --px:"Silkscreen",ui-monospace,monospace;
   --ui:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,
        "Helvetica Neue",Arial,sans-serif;
   --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,monospace;
 }
 *{box-sizing:border-box;margin:0}
 html{-webkit-text-size-adjust:100%}
 body{background:var(--bg);color:var(--ink);font:400 15px/1.65 var(--ui);
      padding:40px 20px 72px;max-width:980px;margin:0 auto;
      -webkit-font-smoothing:antialiased}
 h1{font-family:var(--px);font-size:clamp(22px,4.5vw,34px);font-weight:400;
    letter-spacing:.06em;color:var(--ink);line-height:1.1}
 .tag{color:var(--gold);font-size:12px;margin-top:10px;letter-spacing:.14em;
      text-transform:uppercase;font-weight:600}
 .lede{margin:22px 0 0;max-width:68ch}
 .lede p{color:var(--dim);margin-bottom:10px}
 .lede p:last-child{margin-bottom:0}
 .lede b{color:var(--ink);font-weight:600}
 h2{font-size:11px;font-weight:600;letter-spacing:.16em;
    text-transform:uppercase;color:var(--faint);
    margin:44px 0 14px;display:flex;align-items:center;gap:12px}
 h2::after{content:"";flex:1;height:1px;background:var(--line)}
 .note{border-left:2px solid var(--line);padding:2px 0 2px 16px;
       margin:22px 0 0;color:var(--dim);font-size:13.5px;max-width:68ch}
 .note p{margin-bottom:8px} .note p:last-child{margin-bottom:0}
 .note b{color:var(--ink);font-weight:600}
 .note code{font:12.5px var(--mono);background:var(--panel2);
   border:1px solid var(--line);border-radius:4px;padding:1px 5px;
   color:var(--gold)}
 .bar{display:flex;gap:14px;align-items:center;margin:0 0 14px;
      flex-wrap:wrap}
 button,select{background:var(--panel2);color:var(--ink);
   border:1px solid var(--line);border-radius:7px;padding:8px 15px;
   font:500 13.5px var(--ui);cursor:pointer;transition:border-color .15s}
 button:hover,select:hover{border-color:var(--faint)}
 button:focus-visible,select:focus-visible{outline:2px solid var(--gold);
   outline-offset:2px}
 #clock{font:500 22px/1 var(--mono);font-variant-numeric:tabular-nums;
        min-width:76px;color:var(--gold)}
 #scrub{flex:1;min-width:160px;accent-color:var(--gold);height:4px}
 svg{width:100%;height:auto;display:block;
     image-rendering:pixelated;shape-rendering:crispEdges;
     border:1px solid var(--line);border-radius:12px}
 #stage{background:var(--sky)}
 #log{margin-top:14px;height:116px;overflow:auto;background:var(--panel);
      border:1px solid var(--line);border-radius:10px;padding:12px 15px;
      font:13px/1.7 var(--mono);color:var(--dim)}
 #log div{padding:1px 0}
 #log .hot{color:var(--over)} #log .ok{color:var(--good)}
 .cast{display:grid;grid-template-columns:repeat(auto-fill,minmax(258px,1fr));
       gap:10px}
 .cast+.cast{margin-top:10px}
 .who2{display:flex;gap:13px;align-items:flex-start;background:var(--panel);
       border:1px solid var(--line);border-radius:10px;padding:13px 15px}
 .who2 svg{flex:0 0 30px;width:30px;height:30px;border:0;border-radius:0;
           background:none;margin-top:1px}
 .who2 b{font-size:12px;font-weight:700;letter-spacing:.07em;
         text-transform:uppercase;display:block;margin-bottom:4px}
 .who2 span{font-size:13px;color:var(--dim);line-height:1.5}
 .cheat .who2{background:#1c1317;border-color:#3a2127}
 .cheat b{color:var(--over)}
 table.contracts{border-collapse:collapse;width:100%;font-size:13.5px}
 table.contracts th{text-align:left;padding:0 14px 9px 0;font-size:10.5px;
   font-weight:600;letter-spacing:.14em;text-transform:uppercase;
   color:var(--faint);border-bottom:1px solid var(--line)}
 table.contracts td{padding:13px 14px 13px 0;border-bottom:1px solid var(--line);
   vertical-align:top;color:var(--dim)}
 table.contracts td b{color:var(--ink);font-weight:600;font-size:14px}
 table.contracts tr:last-child td{border-bottom:0}
 .pill{display:inline-block;font-size:11px;font-weight:600;letter-spacing:.06em;
   text-transform:uppercase;padding:3px 9px;border-radius:999px;
   white-space:nowrap;border:1px solid}
 .pill.held{color:var(--good);border-color:#1e4a38;background:#10241c}
 .pill.broke{color:var(--over);border-color:#4a2320;background:#241312}
 .pill.open{color:var(--gold);border-color:#4a3a18;background:#241d10}
 .foot{color:var(--faint);font-size:13px;margin-top:46px;
       border-top:1px solid var(--line);padding-top:18px;max-width:68ch}
 a{color:var(--under);text-decoration:none;
   border-bottom:1px solid rgba(91,157,255,.35)}
 a:hover{border-bottom-color:var(--under)}
 @media (max-width:640px){
   body{padding:28px 16px 48px}
   .cast{grid-template-columns:1fr}
   table.contracts th:nth-child(2),table.contracts td:nth-child(2){display:none}
 }
</style></head><body>

<h1>FEST TOWN</h1>
<div class="tag">a college fest, simulated</div>
<div class="lede">
<p>Every stall, student, box office, stage and band is <b>its own
agent</b>, and nothing can see the whole ground. Students find stalls
from the cards stalls publish, tickets are sold, passed on and refunded
through a fake payment gateway, bands bid against each other for stage
slots, and students rate the stalls they bought from.</p>
<p>A whole fest day plays below in three minutes.</p>
</div>

<div class="note">
<p><b>Everything here is scripted, not a model call.</b> Each agent is a
small state machine, which is why a day replays exactly from its seed
and costs nothing to run.</p>
<p>One role can be model-driven instead. <code>llm_stall</code> asks a
model for its next price every hour, given its own sales, its stock and
what the stalls either side of it charge, with the floor and ceiling
clamped in code so it cannot talk its way past them. That version runs
in its own scenario, because a model call per stall per hour makes the
day slow and gives up determinism: the trace still records every prompt
and reply, but the same seed stops reproducing the same fest.</p>
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

<h2>WHO IS IN THE FEST</h2>
<div class="cast">
<div class="who2"><svg viewBox="0 0 32 32" shape-rendering="crispEdges" aria-hidden="true"><rect x="4" y="6" width="24" height="4" fill="#ff8a6a"/><rect x="4" y="10" width="24" height="2" fill="#e8eaf2"/><rect x="4" y="12" width="24" height="12" fill="#8b97b5"/><rect x="8" y="14" width="6" height="6" fill="#ffd98a"/><rect x="18" y="14" width="6" height="6" fill="#ffd98a"/><rect x="12" y="24" width="8" height="4" fill="#39425c"/></svg><div><b>STALL</b><span>Sells one kind of food until it runs out, and republishes its card after every sale so the queue is public.</span></div></div>
<div class="who2"><svg viewBox="0 0 32 32" shape-rendering="crispEdges" aria-hidden="true"><rect x="12" y="4" width="8" height="8" fill="#e0b48f"/><rect x="10" y="12" width="12" height="12" fill="#8b97b5"/><rect x="6" y="14" width="4" height="8" fill="#8b97b5"/><rect x="22" y="14" width="4" height="8" fill="#8b97b5"/><rect x="12" y="24" width="4" height="6" fill="#5a6480"/><rect x="18" y="24" width="4" height="6" fill="#5a6480"/></svg><div><b>STUDENT</b><span>Arrives, glances at three stalls, buys once, and rates what it got.</span></div></div>
<div class="who2"><svg viewBox="0 0 32 32" shape-rendering="crispEdges" aria-hidden="true"><rect x="4" y="10" width="24" height="14" fill="#9a6fc0"/><rect x="6" y="12" width="20" height="10" fill="#e8eaf2"/><rect x="8" y="14" width="16" height="2" fill="#5a6480"/><rect x="8" y="18" width="10" height="2" fill="#5a6480"/><rect x="2" y="10" width="2" height="14" fill="#6d4b85"/><rect x="28" y="10" width="2" height="14" fill="#6d4b85"/></svg><div><b>BOX OFFICE</b><span>Sells seats in a window, keeps the register of who holds what, takes refunds, admits at the gate.</span></div></div>
<div class="who2"><svg viewBox="0 0 32 32" shape-rendering="crispEdges" aria-hidden="true"><rect x="12" y="4" width="8" height="8" fill="#e0b48f"/><rect x="10" y="12" width="12" height="12" fill="#9a6fc0"/><rect x="22" y="14" width="8" height="6" fill="#e8eaf2"/><rect x="22" y="14" width="8" height="2" fill="#c9a9e0"/><rect x="12" y="24" width="4" height="6" fill="#5a6480"/><rect x="18" y="24" width="4" height="6" fill="#5a6480"/></svg><div><b>TICKET HOLDER</b><span>Buys in the morning, might pass the ticket on or return it, turns up at the venue.</span></div></div>
<div class="who2"><svg viewBox="0 0 32 32" shape-rendering="crispEdges" aria-hidden="true"><rect x="2" y="8" width="28" height="4" fill="#9a6fc0"/><rect x="4" y="12" width="2" height="2" fill="#ffc44d"/><rect x="10" y="12" width="2" height="2" fill="#ffc44d"/><rect x="16" y="12" width="2" height="2" fill="#ffc44d"/><rect x="22" y="12" width="2" height="2" fill="#ffc44d"/><rect x="26" y="12" width="2" height="2" fill="#ffc44d"/><rect x="4" y="16" width="24" height="10" fill="#4a3a66"/><rect x="8" y="18" width="16" height="6" fill="#1b1428"/><rect x="2" y="26" width="28" height="2" fill="#5a6480"/></svg><div><b>STAGE</b><span>Publishes its slots, takes bids from bands, awards each one, and holds the money until they play.</span></div></div>
<div class="who2"><svg viewBox="0 0 32 32" shape-rendering="crispEdges" aria-hidden="true"><rect x="20" y="4" width="6" height="16" fill="#8b97b5"/><rect x="10" y="16" width="14" height="4" fill="#8b97b5"/><rect x="6" y="18" width="10" height="10" fill="#8b97b5"/><rect x="8" y="20" width="6" height="6" fill="#ffd98a"/><rect x="20" y="4" width="8" height="4" fill="#8b97b5"/></svg><div><b>BAND</b><span>Bids for the slot it wants, pays into escrow, and has to actually turn up to get paid.</span></div></div>
<div class="who2"><svg viewBox="0 0 32 32" shape-rendering="crispEdges" aria-hidden="true"><rect x="4" y="8" width="24" height="16" fill="#8b97b5"/><rect x="4" y="12" width="24" height="4" fill="#ff8a6a"/><rect x="8" y="18" width="8" height="2" fill="#ffd98a"/><rect x="20" y="18" width="4" height="4" fill="#3ddc97"/></svg><div><b>GATEWAY</b><span>Takes the money, then confirms it later. Or twice. Or never.</span></div></div>
</div>
<div class="cast cheat">
<div class="who2"><svg viewBox="0 0 32 32" shape-rendering="crispEdges" aria-hidden="true"><rect x="4" y="6" width="24" height="4" fill="#ff6b5a"/><rect x="4" y="10" width="24" height="2" fill="#e8eaf2"/><rect x="4" y="12" width="24" height="12" fill="#8b97b5"/><rect x="8" y="14" width="6" height="6" fill="#ff6b5a"/><rect x="18" y="14" width="6" height="6" fill="#ff6b5a"/><rect x="12" y="24" width="8" height="4" fill="#39425c"/></svg><div><b>SMEAR STALL</b><span>Sells like any other stall, and rates its rivals down twenty five times.</span></div></div>
<div class="who2"><svg viewBox="0 0 32 32" shape-rendering="crispEdges" aria-hidden="true"><rect x="12" y="4" width="8" height="8" fill="#e0b48f"/><rect x="10" y="12" width="12" height="12" fill="#ff6b5a"/><rect x="6" y="14" width="4" height="8" fill="#ff6b5a"/><rect x="22" y="14" width="4" height="8" fill="#ff6b5a"/><rect x="4" y="2" width="12" height="8" fill="#e8eaf2"/><rect x="4" y="2" width="12" height="2" fill="#ff6b5a"/><rect x="12" y="24" width="4" height="6" fill="#5a6480"/><rect x="18" y="24" width="4" height="6" fill="#5a6480"/></svg><div><b>SHILL</b><span>Praises one stall over and over. Never queues, never pays, never eats.</span></div></div>
<div class="who2"><svg viewBox="0 0 32 32" shape-rendering="crispEdges" aria-hidden="true"><rect x="12" y="4" width="8" height="8" fill="#e0b48f"/><rect x="10" y="12" width="12" height="12" fill="#ff6b5a"/><rect x="22" y="14" width="8" height="8" fill="#ffc44d"/><rect x="24" y="16" width="4" height="4" fill="#ff6b5a"/><rect x="12" y="24" width="4" height="6" fill="#5a6480"/><rect x="18" y="24" width="4" height="6" fill="#5a6480"/></svg><div><b>VOTE BUYER</b><span>Buys the cheapest thing at the fest to earn a vote, then spends it on a stall it never visited.</span></div></div>
<div class="who2"><svg viewBox="0 0 32 32" shape-rendering="crispEdges" aria-hidden="true"><rect x="12" y="4" width="8" height="8" fill="#e0b48f"/><rect x="10" y="12" width="12" height="12" fill="#ff6b5a"/><rect x="22" y="14" width="8" height="6" fill="#e8eaf2"/><rect x="22" y="14" width="8" height="2" fill="#ff6b5a"/><rect x="2" y="14" width="8" height="6" fill="#e8eaf2"/><rect x="2" y="14" width="8" height="2" fill="#ff6b5a"/><rect x="12" y="24" width="4" height="6" fill="#5a6480"/><rect x="18" y="24" width="4" height="6" fill="#5a6480"/></svg><div><b>TICKET CHEAT</b><span>Tries to pass on a ticket it does not hold, and to walk in twice on one.</span></div></div>
<div class="who2"><svg viewBox="0 0 32 32" shape-rendering="crispEdges" aria-hidden="true"><rect x="20" y="4" width="6" height="16" fill="#ff6b5a"/><rect x="10" y="16" width="14" height="4" fill="#ff6b5a"/><rect x="6" y="18" width="10" height="10" fill="#ff6b5a"/><rect x="8" y="20" width="6" height="6" fill="#e8eaf2"/><rect x="20" y="4" width="8" height="4" fill="#ff6b5a"/></svg><div><b>GREEDY BAND</b><span>Bids on every slot at once, bids below zero, and walks on stage it did not win.</span></div></div>
</div>

<h2>WHAT KIND OF PROMISE EACH ONE MAKES</h2>
<table class="contracts">
<tr><th>contract</th><th>the promise</th><th>what the run showed</th><th></th></tr>
<tr><td><b>Purchase</b></td><td>Hand over money, get the thing, both at once</td><td>Every sale settled, nothing sold from an empty stall</td><td><span class="pill held">held</span></td></tr>
<tr><td><b>Transfer</b></td><td>A claim handed to somebody else, who can use it</td><td>Every transfer made by whoever actually held the ticket</td><td><span class="pill held">held</span></td></tr>
<tr><td><b>Refund</b></td><td>Unwinding a deal that already completed</td><td>Who gets the money when the holder is not the payer</td><td><span class="pill open">open</span></td></tr>
<tr><td><b>Delayed settlement</b></td><td>Pay a third party who confirms later</td><td>A lost confirmation leaves a fan paid up with no ticket</td><td><span class="pill broke">broke</span></td></tr>
<tr><td><b>Auction</b></td><td>The right to a future slot, money held until you deliver</td><td>Three slots of eight went empty with live bids on them</td><td><span class="pill broke">broke</span></td></tr>
<tr><td><b>Reputation</b></td><td>Saying something about someone that changes what they earn</td><td>A vote costs one purchase of the cheapest item on the ground</td><td><span class="pill broke">broke</span></td></tr>
</table>
<div class="legend">Six different shapes of agreement, not six features. Each
one can fail in a way the others cannot, and four of the six did.</div>

<div class="foot">Built from one run's evidence bundle, with no server and
no network behind it. Code and scenarios:
<a href="https://github.com/varuni7/fest-town">github.com/varuni7/fest-town</a>.</div>

<script>
const ALL = __DATA__;
const NS = 'http://www.w3.org/2000/svg';
const REAL = 180;                             // 3 minutes at 1x
const W = 960, PX = 4, pad = 26;
const BASE = 300, GATE = 382;
const OVER = '#ff6b5a', UNDER = '#5b9dff', INK = '#eef1f7', DIM = '#949db4';
const WARM = '#ffd98a', GOLD = '#ffc44d';

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
  // a lit stall at night: striped awning, warm windows, a lantern
  for(let i=0;i<bw/PX;i+=2)
    px(g,x+i*PX,base-118,2,5,i%4===0?hue:'#e8e2d4');
  px(g,x,base-98,bw/PX,24,'#2b3346');
  px(g,x,base-98,bw/PX,2,hue);
  px(g,x+3*PX,base-86,5,5,WARM);
  px(g,x+bw-9*PX,base-86,5,5,WARM);
  px(g,x+2*PX,base-62,(bw/PX)-4,1,'#3c4660');
  px(g,cx-3*PX,base-50,6,12,'#141a28');
  px(g,cx-1*PX,base-138,2,5,'#4a5570');
  px(g,cx-1*PX,base-140,2,2,GOLD);
}
function stageBox(g,cx,base,w){
  const bw = Math.min(w-14,128), x = cx-bw/2;
  px(g,x,base-74,bw/PX,4,'#59406f');
  for(let i=1;i<bw/PX;i+=3) px(g,x+i*PX,base-70,1,1,GOLD);
  px(g,x+2*PX,base-58,(bw/PX)-4,14,'#2b2340');
  px(g,x+5*PX,base-52,(bw/PX)-10,9,'#15101f');
  px(g,x+6*PX,base-50,(bw/PX)-12,1,'#4a3a66');
  px(g,x,base-6,bw/PX,2,'#4a5570');
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

  el('rect',{x:0,y:BASE,width:W,height:400-BASE,fill:'#171410'},svg);
  el('rect',{x:0,y:BASE,width:W,height:2,fill:'#2e2820'},svg);

  (D.shows||[]).forEach((v,i)=>{
    const n = D.shows.length, sw = (W-pad*2)/n;
    const x = pad + i*sw + sw/2, g = el('g',{},svg);
    stageBox(g,x,92,sw);
    label(g,x,20,v.name.toUpperCase(),9,'#c9a9e0');
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
  if(e.k==='considered' && b){ walker(b.x,BASE+14,'#cfd6e6'); }
  else if(e.k==='bought' && b){ b.n++; totalSales++;
    b.sold.textContent=b.n+' sold'; }
  else if(e.k==='ticket'){const v=venues[e.s];
    if(v){v.sold++; v.seats.textContent=v.sold+'/'+v.cap;}}
  else if(e.k==='refund'){const v=venues[e.s];
    if(v){v.sold=Math.max(0,v.sold-1); v.seats.textContent=v.sold+'/'+v.cap;}
    say(fmt(e.t)+'  '+e.m);}
  else if(e.k==='enter'){const v=venues[e.s];
    if(v) walker(v.x,116,'#c9a9e0');}
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

HUES = ["#ff8a6a", "#c98b1b", "#3f9d6d", "#3f7fc4", "#c9a9e0",
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
