# flash_desktop.py  (Python 3.13 + PySimpleGUI 5.x)
# v4.7 — English=카테고리 UI 고정, 항상 랜덤·중복 최소화, r1→휴식→r2→휴식→r3 자동, 전체화면 리스케일

import os, json, time, random
import PySimpleGUI as sg
import pyttsx3          # TTS 엔진 (윈도우 SAPI5)
import threading        # 비동기 재생(UI 멈춤 방지)


try:
    import winsound
except Exception:
    winsound = None

TITLE        = "Flash Learning"
DATA_DIR     = os.path.dirname(__file__)
REST_DEFAULT = 120
PAGE_DEFAULT = 30

# 호흡 애니메이션
INHALE_S = 4
HOLD_S   = 4
EXHALE_S = 6
CYCLE_S  = INHALE_S + HOLD_S + EXHALE_S

TEXT_COLOR = "#FFFFFF"
KEY_BG     = "#111111"
MEAN_BG    = "#111111"
USAGE_BG   = "#111111"

try:
    sg.set_options(font=("Segoe UI", 11))
except Exception:
    pass
# --------- TTS helpers ---------
def tts_init():
    try:
        eng = pyttsx3.init()                                # (모듈 초기화 + 기본 SAPI 보이스 로드)
        eng.setProperty('rate', 180)                        # (발화속도) 180 wpm 정도
        eng.setProperty('volume', 1.0)                      # (볼륨) 0.0~1.0
        return eng
    except Exception:
        return None

def tts_pick_voice(engine, lang_hint: str):
    """lang_hint: 'en' or 'ko' 등. 보이스 목록에서 언어/이름에 해당 접두가 들어간 것을 고름."""
    try:
        for v in engine.getProperty('voices'):
            vid = (getattr(v, 'id', '') or '').lower()
            vnm = (getattr(v, 'name','') or '').lower()
            # 일부 드라이버는 v.languages 제공
            vlangs = []
            try:
                vlangs = [str(x).lower() for x in getattr(v, 'languages', [])]
            except Exception:
                pass
            if lang_hint in vid or lang_hint in vnm or any(lang_hint in x for x in vlangs):
                return v.id
    except Exception:
        pass
    return None

def tts_say_async(ctx, text: str, voice_id: str | None):
    """UI가 멈추지 않도록 TTS는 별 스레드에서 실행"""
    if not ctx.tts_engine or not text: 
        return
    def run():
        try:
            eng = ctx.tts_engine
            eng.stop()                                      # (겹침 방지) 이전 재생 중지
            if voice_id:
                eng.setProperty('voice', voice_id)          # (보이스 선택)
            eng.say(text)                                   # (큐에 등록)
            eng.runAndWait()                                # (재생 + 완료까지 대기, 스레드 안에서)
        except Exception:
            pass
    threading.Thread(target=run, daemon=True).start()

def speak_en(ctx):
    c = ctx.cur_card()
    if not c: return
    if c.get("category") == "pattern" and c.get("items"):
        lines = [it.get("en","") for it in c["items"][:3]]
        text = (c.get("keyword","") + ". " + ". ".join([x for x in lines if x])).strip()
    else:
        text = c.get("usage_one_liner") or c.get("keyword","")
    tts_say_async(ctx, text, ctx.voice_en or None)

def speak_ko(ctx):
    c = ctx.cur_card()
    if not c: return
    text = c.get("meaning") or ""
    if not text and c.get("items"):
        text = " ".join([it.get("ko","") for it in c["items"][:3]])
    tts_say_async(ctx, text, ctx.voice_ko or None)
# --------------------------------

def _screen_size():
    try:
        return sg.Window.get_screen_size()
    except Exception:
        try:
            import tkinter as tk
            r = tk.Tk(); w=r.winfo_screenwidth(); h=r.winfo_screenheight(); r.destroy()
            return (w, h)
        except Exception:
            return (1920, 1080)

def set_card_metrics(ctx, fullscreen: bool):
    if fullscreen:
        sw, sh = _screen_size()
        ctx.card_w = int(sw * 0.82)
        ctx.key_h  = int(sh * 0.20)
        ctx.mean_h = int(sh * 0.12)
        ctx.usage_h= int(sh * 0.32)
        ctx.font_scale = 1.6
    else:
        ctx.card_w = 1000
        ctx.key_h  = 160
        ctx.mean_h = 80
        ctx.usage_h= 200
        ctx.font_scale = 1.0

def _load_json(path):
    if not os.path.exists(path): return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_level_cards(domain: str, level: int):
    return _load_json(os.path.join(DATA_DIR, f"{domain}_L{level}.json"))

def load_master(domain: str):
    return _load_json(os.path.join(DATA_DIR, f"{domain}_master.json"))

EN_FILES = {
  "coding": "english_coding.json",
  "pattern": "english_pattern.json",
  "conversation": "english_conversation.json",
  "vocab": "english_vocab.json"
}

def load_english(category: str):
    fname = EN_FILES.get(category, "english_vocab.json")
    candidates = [
        os.path.join(DATA_DIR, fname),
        os.path.join(DATA_DIR, "data", fname),
    ]
    for p in candidates:
        if os.path.exists(p):
            return _load_json(p)
    return []

def ensure_page(cards, domain: str, want: int):
    if len(cards) >= want: return cards[:want]
    master = load_master(domain)
    seen = {c.get("keyword") for c in cards}
    extra = [c for c in master if c.get("keyword") not in seen]
    return (cards + extra)[:want]

def pick_round2(cards, page=PAGE_DEFAULT, seed=None):
    rng = random.Random(seed)
    k = min(page, len(cards))
    return rng.sample(cards, k=k) if k > 0 else []

def pick_round3(cards, prev_ids: set, page=PAGE_DEFAULT, seed=None):
    rng = random.Random(seed)
    def dedup_keep_order(seq):
        seen=set(); out=[]
        for c in seq:
            kw=c.get("keyword")
            if kw and kw not in seen:
                out.append(c); seen.add(kw)
        return out
    unseen = [c for c in cards if c.get("keyword") not in prev_ids]
    pool = unseen[:]
    if len(pool) < page:
        rest = [c for c in cards if c not in pool]; rng.shuffle(rest); pool += rest
    if len(pool) < page:
        extra = cards * (page // max(1, len(cards)) + 1); rng.shuffle(extra); pool += extra
    rng.shuffle(pool); pool = dedup_keep_order(pool)
    core    = [c for c in pool if "core"    in (c.get("tags") or [])]
    applied = [c for c in pool if "applied" in (c.get("tags") or [])]
    taken = set((c.get("keyword") for c in core)) | set((c.get("keyword") for c in applied))
    other = [c for c in pool if c.get("keyword") not in taken]
    rng.shuffle(core); rng.shuffle(applied); rng.shuffle(other)
    result=[]; seen=set()
    def take(B, k):
        nonlocal result, seen
        for c in B:
            kw=c.get("keyword")
            if kw in seen: continue
            result.append(c); seen.add(kw)
            if len(result)>=k: break
    take(core, min(10, page))
    take(applied, min(20, page))
    for c in pool:
        if len(result)>=page: break
        kw=c.get("keyword"); 
        if kw in seen: continue
        result.append(c); seen.add(kw)
    if len(result)<page:
        for c in cards:
            if len(result)>=page: break
            kw=c.get("keyword")
            if kw in seen: continue
            result.append(c); seen.add(kw)
    return result[:page]

# English 전용: 항상 랜덤 + 세션 누적 중복 최소화
def pick_english(cards, seen_ids: set, k: int, seed=None):
    rng = random.Random(seed)
    unseen = [c for c in cards if c.get("keyword") not in seen_ids]
    take = min(k, len(unseen))
    chosen = rng.sample(unseen, k=take) if take>0 else []
    if len(chosen) < k:
        rest_pool = [c for c in cards if c.get("keyword") not in {x.get('keyword') for x in chosen}]
        if rest_pool:
            chosen += rng.sample(rest_pool, k=min(k-len(chosen), len(rest_pool)))
    return chosen[:k]

class Ctx:
    def __init__(self):
        self.domain="python"
        self.category="coding"    # english 전용
        self.level=1
        self.page=PAGE_DEFAULT
        self.start_page=0
        self.seed=None
        self.fill=True

        self.deck=[]
        self.idx=0
        self.prev_ids=set()

        self.kw_font=36
        self.interval=1.2
        self.rest=REST_DEFAULT
        self.auto=False
        self.fullscreen=False
        self.focus=False
                # TTS
        self.tts_engine = tts_init()                 # (엔진 인스턴스)
        self.voice_en   = tts_pick_voice(self.tts_engine, "en") if self.tts_engine else None
        self.voice_ko   = tts_pick_voice(self.tts_engine, "ko") if self.tts_engine else None
        self.auto_tts   = True                       # (자동 읽기 여부)
        self.last_spoken = (-1, -1)                  # (라운드, 카드 인덱스) 중복 읽기 방지

        self.state="splash"
        self.round_no=0
        self.session_mode=False
        self.start_time=None
        self.total_seconds=0

        self.shuffle_r1=True

        set_card_metrics(self, False)

    def cur_card(self):
        return None if not self.deck else self.deck[self.idx]

def HSEP():
    try: return sg.HorizontalSeparator()
    except: return sg.Text("—"*80)

def safe_update(win, key, *a, **k):
    try: win[key].update(*a, **k)
    except: pass

def progress_row():
    return [sg.ProgressBar(100, orientation="h", size=(60,16), key="-PROG-"),
            sg.Text("0/0 (0%)", key="-PROG_TXT-", size=(18,1))]

def graph_box(key: str, w: int, h: int, bg="#111"):
    return sg.Graph(canvas_size=(w, h),
                    graph_bottom_left=(0, 0),
                    graph_top_right=(w, h),
                    background_color=bg,
                    key=key, enable_events=False)

def graph_center_text(graph: sg.Graph, text: str, font, color=TEXT_COLOR):
    w, h = graph.CanvasSize
    graph.erase()
    graph.draw_text(text or "", (w/2, h/2), color=color, font=font)

def graph_center_multiline(graph: sg.Graph, text: str, font, color=TEXT_COLOR):
    w, h = graph.CanvasSize
    graph.erase()
    lines = (text or "").split("\n")
    try: fsize = int(font[1])
    except: fsize = 20
    line_h = int(fsize * 1.25)
    total_h = line_h * max(1, len(lines))
    y0 = (h - total_h) / 2 + line_h/2
    for i, ln in enumerate(lines):
        graph.draw_text(ln, (w/2, y0 + i*line_h), color=color, font=font)

def layout_splash():
    return [
        [sg.Text("Flash Learning", font=("Segoe UI", 26, "bold"))],
        [sg.Text("Python · MySQL · Pandas · English", font=("Segoe UI", 13))],
        [HSEP()],
        [sg.Text("학습 방법 안내\n"
                 "이 훈련은 외워야 한다는 압박이 아닌 \n반복 노출 훈련입니다.\n"
                 "노출 시간은 짧고(1~1.5초), 3회 루프로 진행하며\n"
                 "회차 사이 2분 명상 휴식이 들어갑니다.")],
        [sg.Button("시작하기", key="-TO_HOME-", size=(12,1))]
    ]

def layout_home():
    return [
        [sg.Text("무의식 기억 훈련", font=("Segoe UI", 18, "bold"))],
        [sg.Text("1회차(순차) → 2회차(랜덤) → 3회차(혼합) / 2분 명상", font=("Segoe UI", 11))],
        [HSEP()],
        [sg.Button("학습 시작", key="-TO_SELECT-", size=(14,1))],
        [sg.Button("OUTPUT 모드", key="-TO_OUTPUT-", size=(14,1))],
        [sg.Button("메뉴얼", key="-TO_MANUAL-", size=(14,1))],
        
    ]

def layout_select(ctx: Ctx):
    dom_combo = sg.Combo(
        ["python","mysql","pandas","english"],
        default_value=ctx.domain,
        key="-DOMAIN-",
        readonly=True,
        size=(12,1),
        enable_events=True   # ← 중요: 변경 시 즉시 이벤트 발생
    )

    if ctx.domain == "english":
        body = [
            [sg.Text("카테고리"),
             sg.Combo(
                 ["vocab","coding","pattern","conversation"],
                 default_value=ctx.category,
                 key="-CAT-",
                 readonly=True,
                 size=(16,1),
                 enable_events=True  # ← 선택 바꾸면 즉시 반영(선택 사항이지만 추천)
             )],
            [sg.Text("한 회차 장수"), sg.Spin([i for i in range(10,61,5)], initial_value=ctx.page, key="-PAGE-", size=(6,1))],
            [sg.Text("seed(선택)"), sg.Input("" if ctx.seed is None else str(ctx.seed), key="-SEED-", size=(12,1))],
            [sg.Text("영어는 항상 랜덤·중복 최소화로 동작합니다.", text_color="#aaaaaa")],
        ]
    else:
        body = [
            [sg.Text("레벨"),   sg.Spin([1,2,3,4,5], initial_value=ctx.level, key="-LEVEL-", size=(6,1))],
            [sg.Text("page 장수"), sg.Spin([i for i in range(10,61,5)], initial_value=ctx.page, key="-PAGE-", size=(6,1))],
            [sg.Text("start 페이지(r1)"), sg.Spin([i for i in range(0,999)], initial_value=ctx.start_page, key="-START-", size=(6,1))],
            [sg.Text("seed(선택)"), sg.Input("" if ctx.seed is None else str(ctx.seed), key="-SEED-", size=(12,1))],
            [sg.Checkbox("레벨 부족 시 마스터로 보충", default=ctx.fill, key="-FILL-")],
            [sg.Checkbox("r1도 랜덤 섞기", default=ctx.shuffle_r1, key="-SHUF_R1-")],
        ]

    return [[sg.Column([
        [sg.Text("세션을 선택하세요", font=("Segoe UI", 16, "bold"))],
        [sg.Text("도메인"), dom_combo],
        *body,
        [HSEP()],
        [sg.Button("다음(루프 안내)", key="-TO_LOOP-", size=(16,1))],
        [sg.Button("뒤로", key="-BACK_HOME-", size=(10,1))],
    ])]]


def layout_loopinfo(ctx: Ctx):
    return [
        [sg.Text("오늘의 루프", font=("Segoe UI", 16, "bold"))],
        [sg.Text("1회차: 순차 30장 — 기본 흐름")],
        [sg.Text("2회차: 랜덤 30장 — 인출 다양화")],
        [sg.Text("3회차: 혼합 30장 — 응용·전이")],
        [sg.Text("메모: 회차 사이 2분 호흡 / 노출 1.0–1.5초")],
        [HSEP()],
        [sg.Button("3회 루프 자동 시작", key="-START_SESSION-", size=(18,1)),
         sg.Button("수동으로 r1만 시작", key="-START_R1-", size=(18,1))],
        [sg.Button("뒤로", key="-BACK_SELECT-", size=(10,1))],
    ]

def layout_study(ctx: Ctx):
    state_line = f"{ctx.domain.upper()} · {(ctx.category if ctx.domain=='english' else 'L'+str(ctx.level))} · {ctx.round_no}/3 · {min(ctx.idx+1, len(ctx.deck))}/{max(1,len(ctx.deck))}"
    top = [[*progress_row()],[sg.Text(state_line, key="-STATE-", size=(60,1))]]
    ctrl_row = sg.Column([
        [sg.Text("키워드 폰트"),
         sg.Slider(range=(24,96), resolution=2, default_value=ctx.kw_font,  orientation="h", key="-KW_SIZE-",   size=(24,15)),
         sg.Text("자동 넘김(초)"),
         sg.Slider(range=(0.5,5.0), resolution=0.1, default_value=ctx.interval, orientation="h", key="-AUTOSEC-", size=(24,15)),
         sg.Checkbox("포커스", default=ctx.focus, key="-FOCUS-"),
         sg.Button("F11 전체화면", key="-FULL-", visible=not ctx.fullscreen),
         sg.Button("🔊 EN", key="-SAY_EN-"),
         sg.Button("🔊 KO", key="-SAY_KO-"),
         sg.Checkbox("자동 읽기", default=ctx.auto_tts, key="-AUTO_TTS-"),
]
         
    ], key="-CTRL-ROW-", visible=not ctx.fullscreen, pad=(0,6))

    key_box   = [graph_box("-GKW-",   ctx.card_w, ctx.key_h,   KEY_BG)]
    mean_box  = [graph_box("-GMEAN-", ctx.card_w, ctx.mean_h,  MEAN_BG)]
    usage_box = [graph_box("-GUSAGE-",ctx.card_w, ctx.usage_h, USAGE_BG)]

    btn_row = sg.Column([[sg.Button("◀ 이전", key="-PREV-"),
                          sg.Button("▶ 자동시작/일시정지", key="-AUTO-"),
                          sg.Button("다음 ▶", key="-NEXT-"),
                          sg.Button("종료", key="-EXIT-")]],
                        key="-BTN-ROW-", visible=not ctx.fullscreen, pad=(0,6))

    fs_help = sg.Text("전체화면: ←/→ 이전·다음, Space 자동/일시정지, Esc 복귀",
                      key="-FS-HELP-", visible=ctx.fullscreen, justification="center")

    return top + [[ctrl_row]] + [key_box] + [mean_box] + [usage_box] + [[fs_help]] + [[btn_row]]

def layout_rest(ctx: Ctx, seconds: int):
    return [
        [sg.Text("명상 휴식", font=("Segoe UI", 18, "bold"))],
        [sg.Text("들이마시기 4초 → 멈춤 4초 → 내쉬기 6초", text_color="#CCCCCC")],
        [sg.Text(f"남은 시간: {seconds}초", key="-REST-LEFT-", font=("Consolas", 16))],
        [graph_box("-GBREATH-", 260, 260, bg="#2a2a2a")],
        [sg.Text("phase", key="-PHASE-", font=("Segoe UI", 12))],
        [sg.Button("건너뛰기", key="-SKIP-")],
    ]

def layout_summary(ctx: Ctx):
    mm = int(ctx.total_seconds // 60); ss = int(ctx.total_seconds % 60)
    label = f"{ctx.domain.upper()}·{(ctx.category if ctx.domain=='english' else 'L'+str(ctx.level))} / 30×3회 / 총 {mm}분 {ss}초"
    return [
        [sg.Text("오늘의 학습 요약", font=("Segoe UI", 18, "bold"))],
        [sg.Text(label)],
        [sg.Button("OUTPUT 모드로", key="-TO_OUTPUT-", size=(14,1)),
         sg.Button("메인으로", key="-TO_HOME-", size=(14,1))],
    ]

def layout_output_menu():
    return [
        [sg.Text("OUTPUT — 인출 연습", font=("Segoe UI", 18, "bold"))],
        [sg.Text("정답은 중요하지 않습니다. 떠오르는 대로 말하거나 써 보세요.", text_color="#CCCCCC")],
        [sg.Button("말하기 30초", key="-OUT_SAY-", size=(14,1)),
         sg.Button("서술 60초", key="-OUT_WRITE-", size=(14,1))],
        [sg.Button("메인으로", key="-TO_HOME-", size=(10,1))],
    ]

def layout_output_say():
    return [
        [sg.Text("말하기 30초", font=("Segoe UI", 16, "bold"))],
        [sg.Text("키워드를 설명해 보세요.", key="-OUT_PROMPT-")],
        [sg.Text("00:30", key="-TIMER-", font=("Consolas", 24))],
        [sg.Button("다음", key="-OUT_DONE-"), sg.Button("메인으로", key="-TO_HOME-")],
    ]

def layout_output_write():
    return [
        [sg.Text("서술 60초", font=("Segoe UI", 16, "bold"))],
        [sg.Text("키워드를 1–2문장으로 요약해 보세요.")],
        [sg.Multiline("", key="-WRITE-", size=(64,8))],
        [sg.Text("01:00", key="-TIMER-", font=("Consolas", 24))],
        [sg.Button("제출/저장", key="-SAVE-"), sg.Button("다음", key="-OUT_DONE-"), sg.Button("메인으로", key="-TO_HOME-")],
    ]

def make_window(ctx: Ctx):
    pages = {
        "splash":       lambda: sg.Window(TITLE, layout_splash(),     finalize=True, return_keyboard_events=True),
        "home":         lambda: sg.Window(TITLE, layout_home(),       finalize=True, return_keyboard_events=True),
        "select":       lambda: sg.Window(TITLE, layout_select(ctx),  finalize=True, return_keyboard_events=True),
        "loop":         lambda: sg.Window(TITLE, layout_loopinfo(ctx),finalize=True, return_keyboard_events=True),
        "study":        lambda: sg.Window(TITLE, layout_study(ctx),   finalize=True, return_keyboard_events=True, resizable=True),
        "rest":         lambda: sg.Window("Meditation", layout_rest(ctx, ctx.rest), finalize=True, return_keyboard_events=True, modal=True, keep_on_top=True),
        "summary":      lambda: sg.Window(TITLE, layout_summary(ctx), finalize=True, return_keyboard_events=True),
        "output_menu":  lambda: sg.Window(TITLE, layout_output_menu(),finalize=True, return_keyboard_events=True),
        "output_say":   lambda: sg.Window(TITLE, layout_output_say(), finalize=True, return_keyboard_events=True),
        "output_write": lambda: sg.Window(TITLE, layout_output_write(),finalize=True, return_keyboard_events=True),
        "manual":       lambda: sg.Window(TITLE, [[sg.Text("메뉴얼은 추후 보강")]], finalize=True, return_keyboard_events=True),
        "settings":     lambda: sg.Window(TITLE, [[sg.Text("설정은 홈에서 조정")]], finalize=True, return_keyboard_events=True),
    }
    return pages.get(ctx.state, lambda: sg.Window(TITLE, [[sg.Text("state error")]], finalize=True))()

def update_progress(win, ctx: Ctx):
    t = len(ctx.deck); cur = ctx.idx + 1 if t else 0
    pct = int(cur / t * 100) if t else 0
    safe_update(win, "-PROG-", pct)
    safe_update(win, "-PROG_TXT-", f"{cur}/{t} ({pct}%)")
    label = f"{ctx.domain.upper()} · {(ctx.category if ctx.domain=='english' else 'L'+str(ctx.level))} · {ctx.round_no}/3 · {cur}/{t}"
    safe_update(win, "-STATE-", label)

def render_card(win, ctx: Ctx):
    c = ctx.cur_card()
    scale = ctx.font_scale
    kw_size    = int(ctx.kw_font * scale)
    mean_size  = max(14, min(40, int(ctx.kw_font * 0.55 * scale)))
    usage_size = max(14, min(58, int(ctx.kw_font * 0.52 * scale)))
    kw_font    = ("Segoe UI", kw_size, "bold")
    mean_font  = ("Segoe UI", mean_size, "bold")
    usage_font = ("Consolas", usage_size)
        # --- 자동 읽기: 같은 카드/라운드에서 중복 발화 방지 ---
    if ctx.auto_tts and (ctx.round_no, ctx.idx) != ctx.last_spoken:
        speak_en(ctx)
        # KO는 살짝 텀을 두고
        def later():
            speak_ko(ctx)
        threading.Timer(0.25, later).start()
        ctx.last_spoken = (ctx.round_no, ctx.idx)

    if not c:
        graph_center_text(win["-GKW-"],   "카드가 없습니다.", kw_font)
        graph_center_text(win["-GMEAN-"], "",               mean_font)
        graph_center_text(win["-GUSAGE-"],"",               usage_font)
        update_progress(win, ctx); return

    graph_center_text(win["-GKW-"],   c.get("keyword",""),            kw_font)
    graph_center_text(win["-GMEAN-"], (c.get("meaning","") or ""), mean_font)

    if c.get("category") == "pattern" and c.get("items"):
        lines = [f"• {it.get('en','')} / {it.get('ko','')}" for it in c["items"]][:16]
        txt = "\n".join(lines)
    else:
        txt = c.get("usage_one_liner","")
    graph_center_multiline(win["-GUSAGE-"], txt, usage_font)
    update_progress(win, ctx)

def toggle_full(win, ctx: Ctx):
    ctx.fullscreen = not ctx.fullscreen
    set_card_metrics(ctx, ctx.fullscreen)
    win.close()
    win = make_window(ctx)
    if ctx.state == "study": render_card(win, ctx)
    return win

def breath_phase(t_in_cycle: float):
    if t_in_cycle < INHALE_S: return "들이마시기", t_in_cycle / INHALE_S
    t_in_cycle -= INHALE_S
    if t_in_cycle < HOLD_S:   return "멈춤", 1.0
    t_in_cycle -= HOLD_S
    if t_in_cycle < EXHALE_S: return "내쉬기", 1.0 - (t_in_cycle / EXHALE_S)
    return "들이마시기", 0.0

def draw_breath(graph: sg.Graph, phase: str, ratio: float):
    graph.erase()
    w, h = graph.CanvasSize
    cx, cy = w//2, h//2
    r_min, r_max = 30, 110
    r = int(r_min + (r_max - r_min) * max(0.0, min(1.0, ratio)))
    color = {"들이마시기":"#7fdcff","멈춤":"#a0ffa0","내쉬기":"#ffd07f"}.get(phase, "#ffffff")
    graph.draw_circle((cx, cy), r, fill_color=color, line_color="#333333")
    graph.draw_text(phase, (cx, cy), color="#000000", font=("Segoe UI", 14, "bold"))

def main():
    ctx = Ctx()
    win = make_window(ctx)
    last_tick = time.time()

    while True:
        timeout = 50 if (ctx.state == "study" and ctx.auto) else 400
        event, values = win.read(timeout=timeout)

        if event in (sg.WIN_CLOSED, "-EXIT-") and ctx.state != "rest":
            break

        if event in ("F11","F11:122") and ctx.state in {"study","home","select","loop","summary","output_menu"}:
            win = toggle_full(win, ctx); continue
        if event in ("Escape","Escape:27") and ctx.fullscreen and ctx.state in {"study","home","select","loop","summary","output_menu"}:
            win = toggle_full(win, ctx); continue

        # splash
        if ctx.state == "splash":
            if event in ("-TO_HOME-","space","space:32"):
                win.close(); ctx.state="home"; win = make_window(ctx)

        # home
        elif ctx.state == "home":
            if event == "-TO_SELECT-":
                win.close(); ctx.state="select"; win = make_window(ctx)
            elif event == "-TO_OUTPUT-":
                win.close(); ctx.state="output_menu"; win = make_window(ctx)
            elif event == "-TO_MANUAL-":
                sg.popup_ok("메뉴얼은 추후 보강", keep_on_top=True)
            elif event == "-TO_SETTINGS-":
                sg.popup_ok("설정은 좌측 슬라이더/루프에서 조정", keep_on_top=True)

        # select
        elif ctx.state == "select":
            if event == "-DOMAIN-":
                ctx.domain = values.get("-DOMAIN-", ctx.domain)
                # 도메인 바뀌면 카테고리/레벨 UI도 즉시 갱신
                if ctx.domain != "english":
                    ctx.category = "vocab"
                win.close(); win = make_window(ctx); continue

            if event == "-BACK_HOME-":
                win.close(); ctx.state="home"; win = make_window(ctx)

            elif event == "-TO_LOOP-":
                ctx.domain = values.get("-DOMAIN-", ctx.domain)
                seed_str   = str(values.get("-SEED-","")).strip()
                ctx.seed   = int(seed_str) if seed_str.isdigit() else None

                if ctx.domain == "english":
                    ctx.category = values.get("-CAT-", ctx.category or "vocab")
                    ctx.page     = int(values.get("-PAGE_", values.get("-PAGE-", ctx.page)))
                else:
                    ctx.level      = int(values.get("-LEVEL_", values.get("-LEVEL-", ctx.level)))
                    ctx.page       = int(values.get("-PAGE_",  values.get("-PAGE-",  ctx.page)))
                    ctx.start_page = int(values.get("-START_", values.get("-START-", ctx.start_page)))
                    ctx.fill       = bool(values.get("-FILL_",  values.get("-FILL-",  ctx.fill)))
                    ctx.shuffle_r1 = bool(values.get("-SHUF_R1_", values.get("-SHUF_R1-", ctx.shuffle_r1)))

                win.close(); ctx.state="loop"; win = make_window(ctx)

        # loop
        elif ctx.state == "loop":
            if event == "-BACK_SELECT-":
                win.close(); ctx.state="select"; win = make_window(ctx)

            elif event == "-START_R1-":
                ctx.session_mode=False; ctx.round_no=1; ctx.prev_ids=set()
                if ctx.domain == "english":
                    rows = load_english(ctx.category)
                    dyn_seed = int(time.time_ns() & 0xFFFFFFFF) if ctx.seed is None else ctx.seed
                    ctx.deck = pick_english(rows, ctx.prev_ids, ctx.page, dyn_seed)
                else:
                    if ctx.shuffle_r1:
                        rows = load_level_cards(ctx.domain, ctx.level)
                        if ctx.fill: rows = ensure_page(rows, ctx.domain, ctx.page)
                        dyn_seed = int(time.time_ns() & 0xFFFFFFFF) if ctx.seed is None else ctx.seed
                        ctx.deck = pick_round2(rows, page=ctx.page, seed=dyn_seed)
                    else:
                        rows = load_level_cards(ctx.domain, ctx.level)
                        if ctx.fill: rows = ensure_page(rows, ctx.domain, ctx.page)
                        ctx.deck = rows[:ctx.page]
                ctx.idx=0; ctx.auto=False
                win.close(); ctx.state="study"; win = make_window(ctx); render_card(win, ctx)

            elif event == "-START_SESSION-":
                ctx.session_mode=True; ctx.round_no=1; ctx.prev_ids=set()
                if ctx.domain == "english":
                    rows = load_english(ctx.category)
                    dyn_seed = int(time.time_ns() & 0xFFFFFFFF) if ctx.seed is None else ctx.seed
                    ctx.deck = pick_english(rows, ctx.prev_ids, ctx.page, dyn_seed)
                else:
                    rows = load_level_cards(ctx.domain, ctx.level)
                    if ctx.fill: rows = ensure_page(rows, ctx.domain, ctx.page)
                    if ctx.shuffle_r1:
                        dyn_seed = int(time.time_ns() & 0xFFFFFFFF) if ctx.seed is None else ctx.seed
                        ctx.deck = pick_round2(rows, page=ctx.page, seed=dyn_seed)
                    else:
                        ctx.deck = rows[:ctx.page]
                ctx.idx=0; ctx.auto=True; ctx.interval=1.2
                ctx.start_time=time.time()
                win.close(); ctx.state="study"; win = make_window(ctx); render_card(win, ctx)

        # study
        elif ctx.state == "study":
            try:
                ctx.kw_font  = int(values.get("-KW_SIZE_", values.get("-KW_SIZE-", ctx.kw_font)))
                ctx.interval = float(values.get("-AUTOSEC_", values.get("-AUTOSEC-", ctx.interval)))
                ctx.focus    = bool(values.get("-FOCUS_", values.get("-FOCUS-", ctx.focus)))
            except Exception:
                pass

            if event == "-FULL-":
                win = toggle_full(win, ctx); continue
                        # --- TTS 이벤트 ---
            if event == "-SAY_EN-":
                speak_en(ctx)
            elif event == "-SAY_KO-":
                speak_ko(ctx)

            # 체크박스 상태 반영
            try:
                ctx.auto_tts = bool(values.get("-AUTO_TTS_", values.get("-AUTO_TTS-", ctx.auto_tts)))
            except Exception:
                pass

            if event in ("-NEXT-","Right","Right:39"):
                if ctx.idx < len(ctx.deck)-1:
                    ctx.prev_ids.add(ctx.cur_card().get("keyword","")); ctx.idx += 1; render_card(win, ctx)
                else:
                    ctx.prev_ids.add(ctx.cur_card().get("keyword",""))
                    if ctx.session_mode:
                        win.close(); ctx.state="rest"; win = make_window(ctx)

            if event in ("-PREV-","Left","Left:37"):
                ctx.idx = max(0, ctx.idx-1); render_card(win, ctx)

            if event in ("-AUTO-","space","space:32"):
                ctx.auto = not ctx.auto; last_tick = time.time()

            if ctx.auto and ctx.deck and (time.time() - last_tick >= ctx.interval):
                last_tick = time.time()
                if ctx.idx < len(ctx.deck)-1:
                    ctx.prev_ids.add(ctx.cur_card().get("keyword","")); ctx.idx += 1; render_card(win, ctx)
                else:
                    ctx.prev_ids.add(ctx.cur_card().get("keyword",""))
                    if ctx.session_mode:
                        win.close(); ctx.state="rest"; win = make_window(ctx)

            if ctx.state == "study":
                render_card(win, ctx)

        # rest
        elif ctx.state == "rest":
            left = ctx.rest; base = time.time()
            g: sg.Graph = win["-GBREATH-"]; last_phase=None
            while True:
                ev,_ = win.read(timeout=50)
                if ev in (sg.WIN_CLOSED, "-SKIP-"):
                    break
                now = time.time()
                t_in = (now % CYCLE_S)
                phase, ratio = breath_phase(t_in)
                if phase != last_phase:
                    try:
                        if winsound:
                            f = 880 if phase == "들이마시기" else 700 if phase == "멈춤" else 550
                            winsound.Beep(f, 120)
                    except Exception:
                        pass
                    last_phase = phase
                draw_breath(g, phase, ratio); safe_update(win, "-PHASE-", phase)
                if now - base >= 1.0:
                    base = now; left -= 1; safe_update(win, "-REST-LEFT-", f"남은 시간: {left}초")
                    if left <= 0: break
                win.refresh()

            try:
                if winsound:
                    for f in (880,700,550): winsound.Beep(f,120)
            except Exception:
                pass

            win.close()
            ctx.round_no += 1
            dyn_seed = int(time.time_ns() & 0xFFFFFFFF) if ctx.seed is None else ctx.seed

            if ctx.round_no == 2:
                if ctx.domain == "english":
                    rows = load_english(ctx.category)
                    ctx.deck = pick_english(rows, ctx.prev_ids, ctx.page, dyn_seed)
                else:
                    rows = load_level_cards(ctx.domain, ctx.level)
                    if ctx.fill: rows = ensure_page(rows, ctx.domain, ctx.page)
                    ctx.deck = pick_round2(rows, page=ctx.page, seed=dyn_seed)
                ctx.idx=0; ctx.auto=True; ctx.state="study"
                win = make_window(ctx); render_card(win, ctx)

            elif ctx.round_no == 3:
                if ctx.domain == "english":
                    rows = load_english(ctx.category)
                    ctx.deck = pick_english(rows, ctx.prev_ids, ctx.page, dyn_seed)
                else:
                    rows = load_level_cards(ctx.domain, ctx.level)
                    if ctx.fill: rows = ensure_page(rows, ctx.domain, ctx.page)
                    ctx.deck = pick_round3(rows, prev_ids=ctx.prev_ids, page=ctx.page, seed=dyn_seed)
                ctx.idx=0; ctx.auto=True; ctx.state="study"
                win = make_window(ctx); render_card(win, ctx)

            else:
                ctx.session_mode=False; ctx.auto=False
                ctx.total_seconds=(time.time()-ctx.start_time) if ctx.start_time else 0
                ctx.state="summary"; win = make_window(ctx)

        elif ctx.state == "summary":
            if event == "-TO_OUTPUT-":
                win.close(); ctx.state="output_menu"; win = make_window(ctx)
            elif event == "-TO_HOME-":
                win.close(); ctx.state="home"; win = make_window(ctx)

        elif ctx.state == "output_menu":
            if event == "-OUT_SAY-":
                win.close(); ctx.state="output_say"; win = make_window(ctx)
            elif event == "-OUT_WRITE-":
                win.close(); ctx.state="output_write"; win = make_window(ctx)
            elif event == "-TO_HOME-":
                win.close(); ctx.state="home"; win = make_window(ctx)

        elif ctx.state == "output_say":
            t=30; base=time.time()
            while True:
                ev,_=win.read(timeout=100)
                if ev in (sg.WIN_CLOSED,"-OUT_DONE-","-TO_HOME-"): break
                if time.time()-base>=1: t-=1; base=time.time()
                mm,ss=divmod(t,60); safe_update(win,"-TIMER-",f"{mm:02d}:{ss:02d}")
                if t<=0: break
            win.close(); ctx.state="output_menu" if ev!="-TO_HOME-" else "home"; win = make_window(ctx)

        elif ctx.state == "output_write":
            t=60; base=time.time()
            while True:
                ev,_=win.read(timeout=100)
                if ev in (sg.WIN_CLOSED,"-OUT_DONE-","-TO_HOME-","-SAVE-"): break
                if time.time()-base>=1: t-=1; base=time.time()
                mm,ss=divmod(t,60); safe_update(win,"-TIMER-",f"{mm:02d}:{ss:02d}")
                if t<=0: break
            win.close(); ctx.state="output_menu" if ev!="-TO_HOME-" else "home"; win = make_window(ctx)

    win.close()

if __name__ == "__main__":
    main()
