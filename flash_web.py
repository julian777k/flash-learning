# flash_web.py — 모바일 브라우저용 웹앱 + PWA + TTS(영/한) + 명상 음성 안내
# 실행:  py -3.13 -m pip install flask
#        py -3.13 flash_web.py  → PC에서 http://127.0.0.1:7860 , 폰은 http://<PC-IP>:7860
from __future__ import annotations
import os, json, random
from pathlib import Path
from flask import Flask, request, send_from_directory, jsonify, render_template_string

APP = Flask(__name__, static_folder="static")
BASE = Path(__file__).parent.resolve()
DATA = (BASE / "data").resolve()

EN_FILES = {
    "vocab": "english_vocab.json",
    "coding": "english_coding.json",
    "pattern": "english_pattern.json",
    "conversation": "english_conversation.json",
}

def load_json(p: Path):
    if not p.exists(): return []
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

HTML = r"""
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1" />
<meta name="theme-color" content="#0f0f12">
<link rel="manifest" href="/manifest.webmanifest">
<title>Flash Learning (Mobile)</title>
<style>
  :root { --fg:#fff; --bg:#0f0f12; --box:#14161b; --accent:#58a6ff; --muted:#aab2c0;}
  body { margin:0; background:var(--bg); color:var(--fg); font-family:system-ui, -apple-system, Segoe UI, Roboto, sans-serif; }
  .wrap { max-width: 1024px; margin: 0 auto; padding: 16px; }
  h1 { font-size: 22px; margin: 8px 0 12px; }
  .row { display:flex; gap:10px; align-items:center; flex-wrap:wrap; }
  select, input[type=number] { padding:8px 10px; background:#0c0d10; color:var(--fg); border:1px solid #222; border-radius:10px; }
  button { padding:10px 14px; border-radius:12px; border:0; background:var(--accent); color:#000; font-weight:700; cursor:pointer;}
  .grid { display:grid; grid-template-rows: 26vh 14vh 36vh; gap:10px; margin-top:12px; }
  .box { background:var(--box); border-radius:18px; display:flex; align-items:center; justify-content:center; text-align:center; padding:10px; }
  #kw { font-weight:800; }
  #mean { font-weight:700; opacity:.95; }
  #usage { white-space:pre-wrap; line-height:1.25; }
  .ctrl { display:flex; gap:10px; align-items:center; margin-top:10px; flex-wrap:wrap;}
  input[type=range] { width: 160px; }
  .sub { opacity:.8; font-size:13px; color:var(--muted); }
  .hidden { display:none !important; }
  .topbar { display:flex; justify-content:space-between; align-items:center; margin:6px 0 8px; }
  .pill { padding:6px 10px; border-radius:999px; background:#1a1d24; border:1px solid #2a303a; }
  /* breathing */
  .breathWrap { display:flex; flex-direction:column; gap:12px; align-items:center; justify-content:center; height:70vh; }
  .circle { width: 220px; height:220px; border-radius:50%; background:#1f6feb; display:flex; align-items:center; justify-content:center; font-weight:800; transition:transform .25s ease; }
  .timer { font-size: 28px; letter-spacing:1px; }
  .state { font-size: 18px; opacity:.9; }
  .ttsbar { display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin-top:10px;}
  .ttsbar select { max-width:220px; }
  .link { color:#7fdcff; text-decoration:underline; }
</style>
</head>
<body>
<div class="wrap" id="screenSelect">
  <h1>Flash Learning — English (PWA+TTS)</h1>
  <div class="row">
    <label>Category</label>
    <select id="cat">
      <option value="vocab">vocab</option>
      <option value="coding">coding</option>
      <option value="pattern">pattern</option>
      <option value="conversation">conversation</option>
    </select>
    <label>장수</label>
    <input id="page" type="number" min="10" max="60" step="5" value="30">
    <button id="start">3회 루프 시작</button>
  </div>
  <p class="sub">영어는 라운드마다 <b>랜덤</b>, 세션 전체에서 <b>중복 최소화</b>. 라운드 사이 <b>2분 명상</b>. <span id="pwa-hint" class="hidden">설치하려면 브라우저 메뉴에서 “홈 화면에 추가”</span></p>
</div>

<div class="wrap hidden" id="screenStudy">
  <div class="topbar">
    <span class="pill" id="stateText">EN · vocab · 1/3 · 1/30</span>
    <span class="sub"><span id="percent">0%</span></span>
  </div>
  <div class="grid">
    <div class="box"><div id="kw" style="font-size:46px;">keyword</div></div>
    <div class="box"><div id="mean" style="font-size:28px;">의미</div></div>
    <div class="box"><div id="usage" style="font-size:24px;">예문/패턴</div></div>
  </div>

  <div class="ctrl">
    <span class="sub">글자크기</span>
    <input id="size" type="range" min="24" max="96" step="2" value="46">
    <span class="sub">자동(초)</span>
    <input id="interval" type="range" min="0.5" max="5" step="0.1" value="1.2">
    <button id="toggle">▶ 자동</button>
    <button id="next">다음</button>
    <button id="speakEN">🔊 EN</button>
    <button id="speakKO">🔊 KO</button>
    <label class="sub"><input type="checkbox" id="autoTTS" checked> 자동 읽기</label>
  </div>

  <div class="ttsbar">
    <span class="sub">EN Voice</span>
    <select id="voiceEN"></select>
    <span class="sub">KO Voice</span>
    <select id="voiceKO"></select>
    <span class="sub">Rate</span><input id="rate" type="range" min="0.6" max="1.4" step="0.05" value="1.0">
    <span class="sub">Pitch</span><input id="pitch" type="range" min="0.7" max="1.3" step="0.05" value="1.0">
    <span class="sub">Volume</span><input id="volume" type="range" min="0.2" max="1.0" step="0.05" value="1.0">
  </div>
  <p class="sub">팁: EN은 keyword + (패턴이면 묶음 일부) / KO는 뜻만. TTS는 기기 내장 엔진(오프라인 가능) 사용.</p>
</div>

<div class="wrap hidden" id="screenRest">
  <h1>명상 휴식</h1>
  <div class="breathWrap">
    <div class="circle" id="circle"><span id="phase">들이마시기</span></div>
    <div class="timer" id="left">120</div>
    <div class="state sub">들이마시기 4초 → 멈춤 4초 → 내쉬기 6초</div>
    <div class="row">
      <label class="sub"><input type="checkbox" id="coach" checked> 🎧 음성 코칭</label>
      <button id="skip">건너뛰기</button>
    </div>
  </div>
</div>

<script>
const $ = sel => document.querySelector(sel);
const screenSelect = $("#screenSelect");
const screenStudy  = $("#screenStudy");
const screenRest   = $("#screenRest");
const kw=$("#kw"), mean=$("#mean"), usage=$("#usage");
const stateText=$("#stateText"), percent=$("#percent");
const size=$("#size"), interval=$("#interval");
const btnToggle=$("#toggle"), btnNext=$("#next");
const btnStart=$("#start"), catSel=$("#cat"), pageInp=$("#page");
const btnEN=$("#speakEN"), btnKO=$("#speakKO"), autoTTS=$("#autoTTS");
const voiceEN=$("#voiceEN"), voiceKO=$("#voiceKO");
const rate=$("#rate"), pitch=$("#pitch"), volume=$("#volume");
const phaseEl=$("#phase"), leftEl=$("#left"), circle=$("#circle");
const coach=$("#coach");
const pwaHint=$("#pwa-hint");

let allCards=[], deck=[], idx=0, roundNo=1, page=30, auto=false, last=0, seen=new Set();
let voices=[], voiceMap=new Map();

function shuffle(a){ for(let i=a.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1)); [a[i],a[j]]=[a[j],a[i]];} return a; }
function pickEnglish(cards, seenSet, k){
  const unseen = cards.filter(c=>!seenSet.has(c.keyword));
  let out = [];
  if(unseen.length>=k){ out = shuffle(unseen.slice()).slice(0,k); }
  else {
    out = unseen.slice();
    const rest = cards.filter(c=>!out.some(x=>x.keyword===c.keyword));
    out = out.concat(shuffle(rest).slice(0, Math.min(k-out.length, rest.length)));
  }
  return out.slice(0,k);
}

function setFonts(base){
  kw.style.fontSize = base + "px";
  mean.style.fontSize = Math.max(14, Math.min(40, Math.floor(base*0.55))) + "px";
  usage.style.fontSize = Math.max(14, Math.min(58, Math.floor(base*0.52))) + "px";
}

function render(){
  if(!deck.length){ return; }
  const c = deck[idx];
  kw.textContent   = c.keyword || "";
  mean.textContent = (c.meaning? "의미: " + c.meaning : "");
  if(c.category==="pattern" && c.items){
    const lines = c.items.slice(0,14).map(it=>"• " + (it.en||"") + " / " + (it.ko||""));
    usage.textContent = lines.join("\n");
  }else{
    usage.textContent = c.usage_one_liner || "";
  }
  stateText.textContent = `EN · ${c.category||$("#cat").value} · ${roundNo}/3 · ${idx+1}/${deck.length}`;
  percent.textContent = Math.round((idx+1)/deck.length*100) + "%";

  if(autoTTS.checked){
    setTimeout(()=>{ speakEN(); setTimeout(()=>speakKO(), 250); }, 50);
  }
}

async function loadCategory(cat){
  const map = {"vocab":"english_vocab.json","coding":"english_coding.json","pattern":"english_pattern.json","conversation":"english_conversation.json"};
  const url = "/data/" + map[cat];
  const res = await fetch(url);
  const data = await res.json();
  data.forEach(d=>{ if(!d.category) d.category=cat; });
  return data;
}

async function startLoop(){
  const cat = catSel.value; page = parseInt(pageInp.value||"30");
  allCards = await loadCategory(cat);
  seen = new Set(); roundNo = 1;
  deck = pickEnglish(allCards, seen, page);
  idx = 0;
  screenSelect.classList.add("hidden");
  screenRest.classList.add("hidden");
  screenStudy.classList.remove("hidden");
  render();
}

function toRest(){
  screenStudy.classList.add("hidden");
  screenRest.classList.remove("hidden");
  runRest(120);
}

function runRest(sec){
  let left = sec;
  leftEl.textContent = left.toString();
  let lastSec = Math.floor(performance.now()/1000);
  let phase = "들이마시기";
  let lastPhase = "";
  function step(ts){
    const t = (ts/1000)%14.0;
    if(t<4){ phase="들이마시기"; circle.style.transform=`scale(${1+0.25*(t/4)})`; circle.style.background="#7fdcff";}
    else if(t<8){ phase="멈춤"; circle.style.transform=`scale(1.25)`; circle.style.background="#a0ffa0";}
    else { const r=(t-8)/6; phase="내쉬기"; circle.style.transform=`scale(${1.25-0.25*r})`; circle.style.background="#ffd07f";}
    phaseEl.textContent = phase;
    // phase 바뀔 때 음성 코칭
    if(coach.checked && phase!==lastPhase){ speak(phase, "ko"); lastPhase=phase; }

    const nowSec = Math.floor(ts/1000);
    if(nowSec>lastSec){ lastSec=nowSec; left--; leftEl.textContent = left.toString(); }
    if(left>0 && !screenRest.classList.contains("hidden")) requestAnimationFrame(step);
    else if(left<=0){ screenRest.classList.add("hidden"); nextRound(); }
  }
  requestAnimationFrame(step);
}

function nextRound(){
  roundNo++;
  if(roundNo<=3){
    const cat = catSel.value;
    deck = pickEnglish(allCards, seen, page);
    idx = 0;
    screenStudy.classList.remove("hidden");
    render();
    auto = true; last = performance.now()/1000.0;
    btnToggle.textContent = "⏸ 정지";
  } else {
    screenSelect.classList.remove("hidden");
    screenStudy.classList.add("hidden");
    screenRest.classList.add("hidden");
    alert("3회 루프 완료!");
  }
}

btnStart.addEventListener("click", startLoop);
$("#size").addEventListener("input", ()=> setFonts(parseInt(size.value)));
setFonts(parseInt(size.value));

btnToggle.addEventListener("click", ()=>{
  auto = !auto;
  btnToggle.textContent = auto ? "⏸ 정지" : "▶ 자동";
  last = performance.now()/1000.0;
});

btnNext.addEventListener("click", ()=>{
  if(!deck.length) return;
  seen.add(deck[idx].keyword||"");
  if(idx < deck.length-1){
    idx++; render();
  }else{
    toRest();
  }
});

// ---------- TTS ----------
function fillVoices(){
  voices = window.speechSynthesis.getVoices();
  voiceMap.clear();
  voiceEN.innerHTML = ""; voiceKO.innerHTML = "";
  voices.forEach(v=>{
    const opt = document.createElement("option");
    opt.value = v.name; opt.textContent = `${v.name} (${v.lang})`;
    voiceMap.set(v.name, v);
    if(v.lang.toLowerCase().startsWith("en")) voiceEN.appendChild(opt.cloneNode(true));
    if(v.lang.toLowerCase().startsWith("ko")) voiceKO.appendChild(opt.cloneNode(true));
  });
  // 기본 선택
  if(!voiceEN.value && voiceEN.options.length) voiceEN.selectedIndex = 0;
  if(!voiceKO.value && voiceKO.options.length) voiceKO.selectedIndex = 0;
}
fillVoices();
if('speechSynthesis' in window){
  window.speechSynthesis.onvoiceschanged = fillVoices;
}
function speak(text, langHint){
  if(!('speechSynthesis' in window)) return;
  if(!text) return;
  const u = new SpeechSynthesisUtterance(text);
  u.rate = parseFloat(rate.value||"1.0");
  u.pitch= parseFloat(pitch.value||"1.0");
  u.volume=parseFloat(volume.value||"1.0");
  // 선택한 보이스 우선, 없으면 langHint로 fallback
  let vname = (langHint==="en") ? voiceEN.value : voiceKO.value;
  if(vname && voiceMap.has(vname)) u.voice = voiceMap.get(vname);
  else {
    const found = voices.find(v => v.lang.toLowerCase().startsWith(langHint||"en"));
    if(found) u.voice = found;
  }
  window.speechSynthesis.cancel(); // 겹침 방지
  window.speechSynthesis.speak(u);
}
function speakEN(){
  const c = deck[idx]; if(!c) return;
  if(c.category==="pattern" && c.items){
    const lines = c.items.slice(0,4).map(it=>it.en||"");
    speak([c.keyword, ...lines].join(". "), "en");
  }else{
    const line = c.usage_one_liner || c.keyword || "";
    speak(line, "en");
  }
}
function speakKO(){
  const c = deck[idx]; if(!c) return;
  const line = c.meaning || (c.items? (c.items.slice(0,3).map(it=>it.ko||"").join(" ")) : "");
  speak(line, "ko");
}
btnEN.addEventListener("click", speakEN);
btnKO.addEventListener("click", speakKO);

// ---------- AUTO TICK ----------
function tick(){
  const now = performance.now()/1000.0;
  const sec = parseFloat(interval.value);
  if(auto && (now - last) >= sec && !screenStudy.classList.contains("hidden")){
    last = now;
    btnNext.click();
  }
  requestAnimationFrame(tick);
}
requestAnimationFrame(tick);

// ---------- PWA 등록 ----------
if('serviceWorker' in navigator){
  navigator.serviceWorker.register('/sw.js').then(()=> {
    // 설치 힌트 노출(간단)
    pwaHint.classList.remove("hidden");
  }).catch(()=>{});
}
</script>
</body>
</html>
"""

@APP.route("/")
def index():
    return render_template_string(HTML)

@APP.route("/data/<path:fname>")
def data(fname):
    # data/ 하위 JSON 제공
    p = (DATA / fname).resolve()
    if not str(p).startswith(str(DATA)) or not p.exists():
        return jsonify({"error":"not found"}), 404
    return send_from_directory(DATA, fname)

# PWA 정적 파일 라우팅
@APP.route("/manifest.webmanifest")
def manifest():
    return send_from_directory(APP.static_folder, "manifest.webmanifest")

@APP.route("/sw.js")
def sw():
    # service worker는 올바른 MIME을 위해 별도 라우팅
    return send_from_directory(APP.static_folder, "sw.js")

@APP.route("/static/<path:fname>")
def static_files(fname):
    return send_from_directory(APP.static_folder, fname)

def main():
    host = os.environ.get("HOST","0.0.0.0")
    port = int(os.environ.get("PORT","7860"))
    print(f" * open http://127.0.0.1:{port}  (mobile: http://<PC-IP>:{port})")
    APP.run(host=host, port=port, debug=False)

if __name__ == "__main__":
    main()
