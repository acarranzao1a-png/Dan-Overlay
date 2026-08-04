const WS_URL = "ws://localhost:24050/ws";

const DAN_PALETTES = {
  "1st Dan": ["rgb(118,199,255)", "rgb(231,244,255)"],
  "2nd Dan": ["rgb(113,180,255)", "rgb(196,236,255)"],
  "3rd Dan": ["rgb(115,166,255)", "rgb(180,224,255)"],
  "4th Dan": ["rgb(120,155,255)", "rgb(168,205,255)"],
  "5th Dan": ["rgb(139,152,255)", "rgb(211,224,255)"],
  "6th Dan": ["rgb(166,146,255)", "rgb(238,221,255)"],
  "7th Dan": ["rgb(196,143,255)", "rgb(255,226,239)"],
  "8th Dan": ["rgb(235,160,114)", "rgb(255,224,163)"],
  "9th Dan": ["rgb(255,175,99)", "rgb(255,235,170)"],
  "10th Dan": ["rgb(255,199,108)", "rgb(255,248,200)"],
  Alpha: ["rgb(70,60,180)", "rgb(220,65,80)", "rgb(245,225,45)"],
  Beta: ["rgb(255,245,180)", "rgb(255,165,0)"],
  Gamma: ["rgb(255,0,0)", "rgb(0,60,255)", "rgb(0,255,90)"],
  Delta: ["rgb(95,60,125)", "rgb(215,130,50)"],
  Epsilon: ["rgb(215,45,95)", "rgb(30,80,150)", "rgb(245,240,215)"],
  Zeta: ["rgb(240,130,105)", "rgb(130,190,225)"],
  Eta: ["rgb(145,0,0)", "rgb(200,80,70)"],
  Theta: ["rgb(105,5,5)", "rgb(170,65,55)"],
  Iota: ["rgb(75,10,10)", "rgb(145,50,50)"],
  Kappa: ["rgb(125,125,125)", "rgb(190,190,200)"]
};

const PALETTES_7K = {
  "0th Dan": ["rgb(180,185,210)", "rgb(130,135,185)", "rgb(200,210,240)"],
  "1st Dan": ["rgb(0,75,100)", "rgb(0,180,180)", "rgb(100,245,185)"],
  "2nd Dan": ["rgb(160,40,240)", "rgb(255,20,147)", "rgb(40,10,80)"],
  "3rd Dan": ["rgb(100,10,30)", "rgb(220,80,20)", "rgb(255,160,50)"],
  "4th Dan": ["rgb(5,60,45)", "rgb(0,255,120)", "rgb(180,255,50)"],
  "5th Dan": ["rgb(15,15,110)", "rgb(115,20,180)", "rgb(255,40,150)"],
  "6th Dan": ["rgb(140,40,10)", "rgb(255,190,0)", "rgb(255,250,220)"],
  "7th Dan": ["rgb(15,15,20)", "rgb(180,185,200)", "rgb(120,40,255)"],
  "8th Dan": ["rgb(60,5,30)", "rgb(220,10,70)", "rgb(0,240,255)"],
  "9th Dan": ["rgb(10,5,5)", "rgb(255,60,0)", "rgb(255,210,0)"],
  "10th Dan": ["rgb(100,0,220)", "rgb(0,255,150)", "rgb(240,245,255)"],
  "Gamma": ["rgb(0,255,170)", "rgb(10,50,120)", "rgb(180,0,255)"],
  "Azimuth": ["rgb(255,90,0)", "rgb(200,20,60)", "rgb(255,230,150)"],
  "Zenith": ["rgb(240,245,255)", "rgb(100,110,130)", "rgb(0,100,255)"],
  "Stellium": ["rgb(255,0,128)", "rgb(140,50,255)", "rgb(0,255,255)"],
  "Beyond Stellium": ["rgb(255,0,128)", "rgb(140,50,255)", "rgb(0,255,255)"]
};

const DAN_NAMES = Object.keys(DAN_PALETTES).sort((a, b) => b.length - a.length);

// ── Celestial tiers ───────────────────────────────────────────────────────────
const CELESTIAL_PALETTES = {
  "Beginner": ["rgb(138,130,255)", "rgb(200,197,255)"],
  "Intermediate": ["rgb(76,175,80)", "rgb(178,223,180)"],
  "Expert": ["rgb(255,193,7)", "rgb(255,235,150)"],
  "Mastery": ["rgb(255,112,67)", "rgb(255,200,175)"],
  "Ascension": ["rgb(229,57,53)", "rgb(255,160,158)"],
  "Transcendence": ["rgb(171,71,188)", "rgb(230,180,238)"],
  "Singularity": ["rgb(220,220,220)", "rgb(255,255,255)"],
};

const CELESTIAL_PNG = {
  "Beginner": "Beginner",
  "Intermediate": "Intermediate",
  "Expert": "Expert",
  "Mastery": "Mastery",
  "Ascension": "Ascension",
  "Transcendence": "Transcendence",
  "Singularity": "Singularity",
};

const GREEK_PNG = {
  "Alpha": "11-alpha", "Beta": "12-beta", "Gamma": "13-gamma",
  "Delta": "14-delta", "Epsilon": "15-epsilon", "Zeta": "16-zeta",
  "Eta": "17-eta", "Theta": "18-theta", "Iota": "19-iota", "Kappa": "20-kappa",
};

// Signicial Greek symbol images (background for stages XI+)
const SIGNICIAL_PNG = {
  "XI": "Stage11icon",           // Alpha
  "XII": "Stage12icon",          // Beta
  "XIII": "Stage13icon",         // Gamma
  "XIV": "Stage14icon",          // Delta
  "LastStage": "Stage15icon",    // Epsilon
  "ExtraStageI": "EX1icon",      // Zeta
  "ExtraStageII": "EtaIcon",     // Eta
  "ExtraStageIII": "ThetaIcon",  // Theta
};

// ── Signicial stages ──────────────────────────────────────────────────────────
// HSL-based saturation boost helper (for Alpha-Zeta: Reform colors +5% sat)
function _saturateColor(colorStr, deltaPct) {
  const [r, g, b] = parseRGB(colorStr);
  const rn = r / 255, gn = g / 255, bn = b / 255;
  const max = Math.max(rn, gn, bn), min = Math.min(rn, gn, bn), d = max - min;
  let h = 0, s = 0;
  const l = (max + min) / 2;
  if (d > 0) {
    s = d / (1 - Math.abs(2 * l - 1));
    if (max === rn) h = (((gn - bn) / d) % 6) * 60;
    else if (max === gn) h = ((bn - rn) / d + 2) * 60;
    else h = ((rn - gn) / d + 4) * 60;
    if (h < 0) h += 360;
  }
  s = Math.min(1, s + deltaPct / 100);
  const c = (1 - Math.abs(2 * l - 1)) * s;
  const x = c * (1 - Math.abs((h / 60) % 2 - 1));
  const m = l - c / 2;
  let r1 = 0, g1 = 0, b1 = 0;
  const sec = Math.floor(h / 60) % 6;
  if (sec === 0) { r1 = c; g1 = x; b1 = 0; }
  else if (sec === 1) { r1 = x; g1 = c; b1 = 0; }
  else if (sec === 2) { r1 = 0; g1 = c; b1 = x; }
  else if (sec === 3) { r1 = 0; g1 = x; b1 = c; }
  else if (sec === 4) { r1 = x; g1 = 0; b1 = c; }
  else { r1 = c; g1 = 0; b1 = x; }
  return `rgb(${Math.round((r1 + m) * 255)},${Math.round((g1 + m) * 255)},${Math.round((b1 + m) * 255)})`;
}

// Stage I-X: exact colors from the official CSS gradients
// Stage XI-XVI (Alpha-Zeta): Reform colors + 5% saturation (computed at load)
const SIGNICIAL_PALETTES = {
  "I": ["rgb(232,232,232)", "rgb(154,154,154)"],   // Prelude
  "II": ["rgb(165,242,211)", "rgb(0,128,128)"],     // Abnormality
  "III": ["rgb(220,232,245)", "rgb(49,97,139)"],     // Termination
  "IV": ["rgb(217,191,255)", "rgb(74,0,130)"],      // Resuscitation
  "V": ["rgb(255,248,178)", "rgb(214,123,30)"],    // Disturbance
  "VI": ["rgb(186,205,255)", "rgb(56,41,122)"],     // Revitalization
  "VII": ["rgb(255,69,0)", "rgb(255,215,0)", "rgb(50,205,50)", "rgb(0,255,255)"],  // Motivation
  "VIII": ["rgb(92,147,255)", "rgb(20,0,64)"],        // Misfortune
  "IX": ["rgb(255,255,255)", "rgb(92,92,92)"],      // Catastrophe
  "X": ["rgb(255,102,178)", "rgb(139,0,42)"],      // Finale
  // Greek stages: Reform palette + 5% saturation
  "XI": DAN_PALETTES["Alpha"].map(c => _saturateColor(c, 5)),
  "XII": DAN_PALETTES["Beta"].map(c => _saturateColor(c, 5)),
  "XIII": DAN_PALETTES["Gamma"].map(c => _saturateColor(c, 5)),
  "XIV": DAN_PALETTES["Delta"].map(c => _saturateColor(c, 5)),
  "LastStage": DAN_PALETTES["Epsilon"].map(c => _saturateColor(c, 5)),
  "ExtraStageI": DAN_PALETTES["Zeta"].map(c => _saturateColor(c, 5)),
  // Signicial Eta: royal blue → pure red gradient
  "ExtraStageII": ["rgb(0,41,134)", "rgb(255,0,0)"],
  // Signicial Theta: crimson → cobalt blue gradient
  "ExtraStageIII": ["rgb(168,0,15)", "rgb(0,3,117)"],
};

// ── Shoegazer palettes (12 stages: 1st-10th Dan, Luminal, Tachyon) ──────────
const SHOEGAZER_PALETTES = {
  "1st": ["rgb(255,183,197)", "rgb(135,206,235)"],           // Pastel pink → sky blue
  "2nd": ["rgb(144,238,144)", "rgb(34,139,34)"],            // Light green → forest
  "3rd": ["rgb(180,160,220)", "rgb(75,0,130)"],             // Lavender → indigo
  "4th": ["rgb(255,223,128)", "rgb(204,102,0)"],            // Gold → burnt orange
  "5th": ["rgb(135,206,250)", "rgb(0,51,102)"],             // Light blue → deep navy
  "6th": ["rgb(255,120,120)", "rgb(139,0,0)"],              // Salmon → dark red
  "7th": ["rgb(0,230,230)", "rgb(0,80,80)"],                // Teal → dark teal
  "8th": ["rgb(180,130,255)", "rgb(60,0,100)"],             // Violet → deep purple
  "9th": ["rgb(210,210,210)", "rgb(60,60,60)"],             // Silver → charcoal
  "10th": ["rgb(200,50,80)", "rgb(60,0,20)"],                // Crimson → deep maroon
  "Luminal": ["rgb(220,240,255)", "rgb(100,180,255)", "rgb(200,200,200)"],  // Ethereal white-blue
  "Tachyon": ["rgb(100,120,255)", "rgb(40,0,80)", "rgb(0,0,0)"],            // Deep blue-purple → void
};

// ── LN Course palettes (16 stages: 1st-10th Dan, Yoake-Yokaze) ─────────────
const LN_COURSE_PALETTES = {
  "1st": ["rgb(200,230,255)", "rgb(120,175,230)"],           // Ice blue
  "2nd": ["rgb(180,230,180)", "rgb(60,160,60)"],             // Mint → green
  "3rd": ["rgb(230,200,255)", "rgb(130,80,200)"],            // Soft lilac → violet
  "4th": ["rgb(255,220,160)", "rgb(200,130,40)"],            // Warm sand → amber
  "5th": ["rgb(160,220,255)", "rgb(30,100,180)"],            // Sky → ocean blue
  "6th": ["rgb(255,175,175)", "rgb(180,40,40)"],             // Blush → crimson
  "7th": ["rgb(120,240,220)", "rgb(0,120,100)"],             // Aqua → dark teal
  "8th": ["rgb(200,160,255)", "rgb(80,20,140)"],             // Amethyst → deep violet
  "9th": ["rgb(220,220,220)", "rgb(90,90,100)"],             // Steel grey → charcoal
  "10th": ["rgb(255,160,200)", "rgb(140,20,80)"],             // Rose → deep magenta
  "Yoake": ["rgb(255,200,120)", "rgb(200,100,0)"],             // Dawn gold
  "Yuugure": ["rgb(255,140,100)", "rgb(160,40,80)"],             // Sunset glow
  "Yoru": ["rgb(100,100,200)", "rgb(20,20,80)"],              // Twilight indigo
  "Yami": ["rgb(80,60,120)", "rgb(15,5,40)"],               // Deep darkness
  "Yume": ["rgb(200,150,255)", "rgb(100,0,180)", "rgb(255,200,220)"],  // Dreamscape
  "Yokaze": ["rgb(160,200,240)", "rgb(40,60,100)", "rgb(200,220,255)"],  // Night wind
};

const ui = {
  panel: document.getElementById("danPanel") || document.getElementById("overlay"),
  line: document.getElementById("danLine"),
  bg: document.getElementById("danBg"),
  badgeLeft: document.getElementById("badgeLeft"),
  badgeCenter: document.getElementById("badgeCenter"),
  badgeRight: document.getElementById("badgeRight"),
  loadingText: document.getElementById("loadingText"),
  danName: document.getElementById("danName"),
  danImage: document.getElementById(window.location.href.includes("/ui-6/") ? "danImage2" : "danImage"),
  danSub: document.getElementById("danSub"),
  danGreekBg: document.getElementById("danGreekBg"),
  dpTooltip: document.getElementById("dpTooltip"),
  danDpRow: document.getElementById("danDpRow"),
  danDpValue: document.getElementById("danDpValue"),
  intensityBar: document.getElementById("intensityBar"),
  intensityFill: document.getElementById("intensityFill"),
  intensityThumb: document.getElementById("intensityThumb"),
  chartFamily: document.getElementById("chartFamily"),
  modBadge: document.getElementById("modBadge"),
  metrics: document.getElementById("danMetrics"),
  details: document.getElementById("danDetails"),
  bands: document.getElementById("danBands"),
  density: document.getElementById("danDensity"),
  mapTicker: document.getElementById("mapTicker"),
  statsTicker: document.getElementById("statsTicker"),
  chartBtn: document.getElementById("chartBtn"),
  toast: document.getElementById("toast"),
  progressWrap: document.getElementById("progressWrap"),
  progressBar: document.getElementById("progressBar"),
  progressTime: document.getElementById("progressTime"),
  progressTrack: document.getElementById("progressTrack"),
  progressResult: document.getElementById("progressResult"),
  vizCanvas: document.getElementById("vizCanvas"),
  pausedOverlay: document.getElementById("pausedOverlay"),
  // New compact-bar elements
  mapTitle: document.getElementById("mapTitle"),
  mapTitleWrap: document.getElementById("mapTitleWrap"),
  mapTitleTrack: document.getElementById("mapTitleTrack"),
  mapTitleGhost: document.getElementById("mapTitleGhost"),
  mapArtist: document.getElementById("mapArtist"),
  mapDuration: document.getElementById("mapDuration"),
  mapBpm: document.getElementById("mapBpm"),
  mapOd: document.getElementById("mapOd"),
  mapSr: document.getElementById("mapSr"),
  mapTransition: document.getElementById("mapTransitionScreen"),
  drainBar: document.getElementById("drainBar"),
  skinMapTitle: document.getElementById("skinMapTitle"),
  skinMapTitleWrap: document.getElementById("skinMapTitleWrap"),
  skinMapTitleTrack: document.getElementById("skinMapTitleTrack"),
  skinMapTitleGhost: document.getElementById("skinMapTitleGhost"),
  danDpDec: document.getElementById("danDpDec"),
};

let ws = null;
let reconnectTimer = null;
let bridgeMode = false;

// Progress bar state variables
let prog_wasPlaying = false;
let prog_lastMs = 0;
let prog_lastAcc = 0;
let prog_finishTimeout = null;
let prog_isPaused = false;
// Stall-based in-game pause detection (tosu keeps game_state=2 during pause)
let prog_lastSeenMs = -1;   // last currentMs value we received
let prog_playingAt = 0;    // performance.now() when currentMs last changed
const PAUSE_STALL_MS = 700;  // ms of no time advance before treating as paused

// BPM range cache — tosu sometimes sends a plain number (e.g. the instantaneous
// BPM at the current timing point) instead of a {min,max,common} object.
// We cache the last seen proper range so the display stays correct mid-play.
let _cachedBpmRange = null;

// ── Audio visualizer state ──────────────────────────────────────────
let vizTarget = new Float32Array(32);
let vizSmooth = new Float32Array(32);
let vizActive = false;
let vizCtx = null;
let vizPrimary = "rgb(120, 155, 255)";
let vizSecondary = "rgb(168, 205, 255)";
let vizGradient = null;
let vizLogicalW = 0;
let vizLogicalH = 0;
let vizRenderScale = 1;
let vizLastFrameAt = 0;

// ── Mini-viz (small bars beside duration) ───────────────────────────
const MINI_VIZ_BARS = 12;
let miniVizEls = [];

function initVisualizer() {
  if (!ui.vizCanvas) return;
  vizCtx = ui.vizCanvas.getContext("2d", { alpha: true, desynchronized: true });
  if (vizCtx) vizCtx.imageSmoothingEnabled = true;

  // Use ResizeObserver to track canvas dimensions so vizRender never has
  // to touch clientWidth/clientHeight (both flush style/layout every call).
  const ro = new ResizeObserver((entries) => {
    const rect = entries[0].contentRect;
    const w = Math.round(rect.width);
    const h = Math.round(rect.height);
    if (!w || !h) return;
    const isLargeOverlay = w >= 900;
    const maxPixels = isLargeOverlay ? 220000 : 320000;
    const targetScale = Math.min(1, Math.sqrt(maxPixels / (w * h)));
    if (vizLogicalW !== w || vizLogicalH !== h || Math.abs(vizRenderScale - targetScale) > 0.001) {
      vizLogicalW = w;
      vizLogicalH = h;
      vizRenderScale = targetScale;
      ui.vizCanvas.width = Math.max(1, Math.round(w * vizRenderScale));
      ui.vizCanvas.height = Math.max(1, Math.round(h * vizRenderScale));
      vizGradient = null;
    }
  });
  ro.observe(ui.vizCanvas);

  requestAnimationFrame(vizRender);
}

function initMiniViz() {
  const container = document.getElementById("miniViz");
  if (!container) return;
  for (let i = 0; i < MINI_VIZ_BARS; i++) {
    const bar = document.createElement("div");
    bar.className = "viz-bar";
    container.appendChild(bar);
    miniVizEls.push(bar);
  }
}

function updateMiniViz() {
  if (!miniVizEls.length) return;
  const step = Math.max(1, Math.floor(vizSmooth.length / MINI_VIZ_BARS));
  for (let i = 0; i < MINI_VIZ_BARS; i++) {
    const val = vizSmooth[Math.min(i * step, vizSmooth.length - 1)] || 0;
    const h = Math.round(2 + val * 10);
    miniVizEls[i].style.height = h + "px";
  }
}

function syncVisualizerCanvasSize() {
  // Dimensions are now kept up-to-date by the ResizeObserver in initVisualizer.
  // This function is retained only for its return value; no layout reads needed.
  return { w: vizLogicalW, h: vizLogicalH };
}

function vizRender(now = 0) {
  requestAnimationFrame(vizRender);
  if (!vizCtx) return;

  const { w, h } = syncVisualizerCanvasSize();
  if (!w || !h) return;

  const maxFps = w >= 900 ? 45 : 60;
  const frameInterval = 1000 / maxFps;
  if (now - vizLastFrameAt < frameInterval) return;
  vizLastFrameAt = now;

  // ─ lerp smoothing ─────────────────────────────────────────────
  const lerpUp = 0.70;  // fast but smooth rise — masks the 30fps data rate cleanly at 60fps rAF
  const lerpDown = 0.25;  // fast decay — tight without flickering
  for (let i = 0; i < vizSmooth.length; i++) {
    const t = vizTarget[i];
    const rate = t > vizSmooth[i] ? lerpUp : lerpDown;
    vizSmooth[i] += (t - vizSmooth[i]) * rate;
    if (vizSmooth[i] < 0.002) vizSmooth[i] = 0;
  }

  // Update mini-viz sidebar bars from the same smooth data
  updateMiniViz();

  vizCtx.setTransform(1, 0, 0, 1, 0, 0);
  vizCtx.clearRect(0, 0, ui.vizCanvas.width, ui.vizCanvas.height);

  let hasSignal = false;
  for (let i = 0; i < vizSmooth.length; i++) {
    if (vizSmooth[i] > 0.005) { hasSignal = true; break; }
  }
  if (!hasSignal) return;

  vizCtx.setTransform(vizRenderScale, 0, 0, vizRenderScale, 0, 0);

  const n = vizSmooth.length;
  const gap = 2;
  const barW = Math.max(1, (w - gap * (n - 1)) / n);
  const maxH = h * 0.75;

  if (!vizGradient) {
    vizGradient = vizCtx.createLinearGradient(0, h, 0, 0);
    vizGradient.addColorStop(0, vizPrimary);
    vizGradient.addColorStop(1, vizSecondary);
  }

  // ─ pass 1: cheap glow for loud bars (replaces expensive shadowBlur) ──
  vizCtx.shadowBlur = 0;
  for (let i = 0; i < n; i++) {
    const val = vizSmooth[i];
    if (val <= 0.55) continue;
    const barH = val * maxH;
    const x = i * (barW + gap);
    const y = h - barH;
    const spread = 5;
    vizCtx.globalAlpha = (val - 0.55) * 0.5;
    vizCtx.fillStyle = vizSecondary;
    vizCtx.fillRect(x - spread * 0.5, y - spread, barW + spread, barH + spread);
  }

  // ─ pass 2: all bars with gradient ─────────────────────────────────
  vizCtx.fillStyle = vizGradient;
  for (let i = 0; i < n; i++) {
    const val = vizSmooth[i];
    const barH = val >= 0.003 ? val * maxH : 2;
    const x = i * (barW + gap);
    const y = h - barH;

    vizCtx.globalAlpha = val >= 0.003 ? 0.42 + val * 0.38 : 0.10;

    if (barH > 4 && vizCtx.roundRect) {
      const r = Math.min(barW / 2, 3);
      vizCtx.beginPath();
      vizCtx.roundRect(x, y, barW, barH, [r, r, 0, 0]);
      vizCtx.fill();
    } else {
      vizCtx.fillRect(x, y, barW, barH);
    }
  }

  vizCtx.globalAlpha = 1;
}
// payloads.  We remember the last dan string and the current beatmap key so we
// only reset when the map changes.
let lastDanRaw = "";
let lastMapKey = "";
let _bgGeneration = 0;
let currentPlaybackMs = 0;
let currentTotalMs = 0;
let isMapTransitioning = false;
let _transitionSafetyTimer = 0;

// ── Settings system ──────────────────────────────────────────────────
const _SETTINGS_KEY = "dan_overlay_settings";

const _DEFAULT_KEYBINDS = {
  generate_chart: { key: "g", ctrl: false, alt: false },
  resize_toggle: { key: "r", ctrl: false, alt: false },
  resize_reset: { key: "r", ctrl: true, alt: false },
  overlay_pin: { key: "Tab", ctrl: false, alt: false },
  mode_reform: { key: "1", ctrl: true, alt: false },
  mode_celestial: { key: "2", ctrl: true, alt: false },
  mode_signicial: { key: "3", ctrl: true, alt: false },
  mode_shoegazer: { key: "4", ctrl: true, alt: false },
  mode_ln_course: { key: "5", ctrl: true, alt: false },
  open_settings: { key: ",", ctrl: true, alt: false },
  layout_cycle: { key: "l", ctrl: false, alt: false },
};

const _KEYBIND_LABELS = {
  generate_chart: "Generate chart PNG",
  resize_toggle: "Toggle resize mode",
  resize_reset: "Reset window size",
  overlay_pin: "Pin overlay above osu",
  mode_reform: "Scoring mode: Reform",
  mode_celestial: "Scoring mode: Celestial",
  mode_signicial: "Scoring mode: Signicial",
  mode_shoegazer: "Scoring mode: Shoegazer",
  mode_ln_course: "Scoring mode: LN Course",
  open_settings: "Open settings panel",
  layout_cycle: "Cycle layout density",
};

// Default slider values (0–100 scale)
// blur:  value × 0.3 → px  (40 → 12px)
// bright: value/100 → brightness filter (85 → 0.85)
const _DEF_BLUR = 40;
const _DEF_BRIGHT = 82.35;

const _CURRENT_SKIN = window.location.href.includes("/ui-8/") ? "8"
  : window.location.href.includes("/ui-7/") ? "7"
    : window.location.href.includes("/ui-6/") ? "6"
      : window.location.href.includes("/ui-5/") ? "5"
        : window.location.href.includes("/ui-4/") ? "4"
          : window.location.href.includes("/ui-3/") ? "3"
            : window.location.href.includes("/ui-2/") ? "2"
              : "1";

let _settings = {
  blur: _DEF_BLUR,
  brightness: _DEF_BRIGHT,
  layout: "complete",
  skin: _CURRENT_SKIN,
  logoSize: 50,   // 0-100; maps to 100-500px for Reform, 74-370px for Celestial
  logoOpacity: 14,   // 0-100; maps directly to 0.00-1.00 opacity
  danScale: 50,   // 0-100; maps to 0.5x-1.5x scale for dan name, DP, intensity bar
  broadcastBorderBright: 75, // 0-100; border opacity in broadcast skin
  broadcastBorderThick: 1,   // 0-10px; border width in broadcast skin
  greenScreen: false, // replace map background with solid #00ff00 for chroma key
  frameless: false,   // remove OS title bar for clean OBS capture (requires restart)
  ui6_no_vignette: false,
  ui6_simple_mode: false,
  ui6_outlines: false,
  neverShowTutorial: false,
  windowWidth: null,   // explicit window width in px (null = use default / drag resize)
  windowHeight: null,  // explicit window height in px
  keybinds: JSON.parse(JSON.stringify(_DEFAULT_KEYBINDS)),
};

async function _waitForPywebviewMethod(methodName, timeoutMs = 2000) {
  if (!window.pywebview) return null;
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const method = window.pywebview?.api?.[methodName];
    if (typeof method === "function") {
      return method.bind(window.pywebview.api);
    }
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  return null;
}

async function _loadSettings() {
  let raw = null;
  try {
    const loadSettingsApi = await _waitForPywebviewMethod("load_settings");
    if (loadSettingsApi) {
      raw = await loadSettingsApi();
    }
  } catch (_) { }
  if (!raw) {
    // Fallback: localStorage (dev mode or migration from older install)
    try { raw = localStorage.getItem(_SETTINGS_KEY); } catch (_) { }
  }
  if (!raw) return;
  try {
    const saved = JSON.parse(raw);
    if (typeof saved.blur === "number") _settings.blur = saved.blur;
    if (typeof saved.brightness === "number") _settings.brightness = saved.brightness;
    if (typeof saved.logoSize === "number") _settings.logoSize = Math.max(0, Math.min(100, saved.logoSize));
    if (typeof saved.logoOpacity === "number") _settings.logoOpacity = Math.max(0, Math.min(100, saved.logoOpacity));
    if (typeof saved.danScale === "number") _settings.danScale = Math.max(0, Math.min(100, saved.danScale));
    if (typeof saved.greenScreen === "boolean") _settings.greenScreen = saved.greenScreen;
    if (typeof saved.frameless === "boolean") _settings.frameless = saved.frameless;
    if (typeof saved.ui6_no_vignette === "boolean") _settings.ui6_no_vignette = saved.ui6_no_vignette;
    if (typeof saved.ui6_simple_mode === "boolean") _settings.ui6_simple_mode = saved.ui6_simple_mode;
    if (typeof saved.ui6_outlines === "boolean") _settings.ui6_outlines = saved.ui6_outlines;
    if (typeof saved.neverShowTutorial === "boolean") _settings.neverShowTutorial = saved.neverShowTutorial;
    if (typeof saved.windowWidth === "number") _settings.windowWidth = saved.windowWidth;
    if (typeof saved.windowHeight === "number") _settings.windowHeight = saved.windowHeight;
    if (typeof saved.layout === "string" && ["complete", "simplified", "compact"].includes(saved.layout))
      _settings.layout = saved.layout;
    if (saved.keybinds && typeof saved.keybinds === "object") {
      for (const action of Object.keys(_DEFAULT_KEYBINDS)) {
        if (saved.keybinds[action]) {
          _settings.keybinds[action] = { ..._DEFAULT_KEYBINDS[action], ...saved.keybinds[action] };
        }
      }
    }
    if (typeof saved.skin === "string" && ["1", "2", "3", "4", "5"].includes(saved.skin)) {
      _settings.skin = saved.skin;
    }
  } catch (_) { }
}

async function _saveSettings() {
  const json = JSON.stringify(_settings);
  // Always mirror to localStorage (dev/fallback)
  try { localStorage.setItem(_SETTINGS_KEY, json); } catch (_) { }
  // Primary: persist via Python to %APPDATA%\DanOverlay\settings.json
  try {
    const saveSettingsApi = await _waitForPywebviewMethod("save_settings");
    if (saveSettingsApi) {
      await saveSettingsApi(json);
    }
  } catch (_) { }
}

function _applySettings() {
  const blurPx = (_settings.blur * 0.3).toFixed(2);
  document.documentElement.style.setProperty("--cfg-blur", blurPx + "px");
  const bright = (_settings.brightness / 100).toFixed(4);
  document.documentElement.style.setProperty("--cfg-brightness", bright);
  // Logo watermark: size 0-100 → reform 100-500px / celestial 74-370px; opacity 0-100 → 0.00-1.00
  const logoSizePx = Math.round(100 + _settings.logoSize * 4);   // 100px at 0, 500px at 100
  const logoSizeCelPx = Math.round(74 + _settings.logoSize * 2.96); // proportional for celestial
  const logoOpacityVal = (_settings.logoOpacity / 100).toFixed(3);
  document.documentElement.style.setProperty("--logo-size", logoSizePx + "px");
  document.documentElement.style.setProperty("--logo-size-cel", logoSizeCelPx + "px");
  document.documentElement.style.setProperty("--logo-opacity", logoOpacityVal);
  // Dan display scale: 0→0.5x, 50→1.0x, 100→1.5x
  const danScaleVal = (0.5 + _settings.danScale / 100).toFixed(3);
  document.documentElement.style.setProperty("--dan-scale", danScaleVal);

  // Broadcast border settings
  const bcastThick = typeof _settings.broadcastBorderThick === "number" ? _settings.broadcastBorderThick : 1;
  const bcastBright = typeof _settings.broadcastBorderBright === "number" ? _settings.broadcastBorderBright : 75;
  document.documentElement.style.setProperty("--cfg-bcast-border-thick", bcastThick + "px");
  document.documentElement.style.setProperty("--cfg-bcast-border-bright", (bcastBright / 100).toFixed(2));

  // Green screen mode: replace map background with solid chroma-key green
  const panel = document.getElementById("danPanel");
  const bg = document.getElementById("danBg");
  if (_settings.greenScreen) {
    if (panel) panel.classList.add("green-screen");
    if (bg) bg.style.opacity = "0";
  } else {
    if (panel) panel.classList.remove("green-screen");
    // bg opacity is managed by crossfadeBackground / the ws handler
  }

  const ui6SettingsWrap = document.getElementById("cfgUi6Settings");
  if (ui6SettingsWrap) {
    ui6SettingsWrap.style.display = _settings.skin === "6" ? "block" : "none";
  }

  if (_settings.skin === "6" && panel) {
    if (_settings.ui6_no_vignette) panel.classList.add("ui6-no-vignette");
    else panel.classList.remove("ui6-no-vignette");
    
    if (_settings.ui6_simple_mode) panel.classList.add("ui6-simple-mode");
    else panel.classList.remove("ui6-simple-mode");

    if (_settings.ui6_outlines) panel.classList.add("ui6-outlines");
    else panel.classList.remove("ui6-outlines");
  } else if (panel) {
    panel.classList.remove("ui6-no-vignette", "ui6-simple-mode", "ui6-outlines");
  }
}

/* ── Layout density modes ───────────────────────────────────────────── */
const _LAYOUT_MODES = ["complete", "simplified", "compact"];
const _LAYOUT_HEIGHTS = { complete: 320, simplified: 220, compact: 76 };
let _layoutMode = "complete";

function _applyLayoutMode(skipResize) {
  // Classic skin and new skins (4-8) have fixed layouts; JS layout modes are not applicable.
  if (_CURRENT_SKIN === "2" || _CURRENT_SKIN === "4" || _CURRENT_SKIN === "5" || _CURRENT_SKIN === "6" || _CURRENT_SKIN === "7" || _CURRENT_SKIN === "8") return;
  const panel = document.getElementById("danPanel");
  if (!panel) return;
  panel.classList.remove("layout-simplified", "layout-compact");
  if (_layoutMode !== "complete") panel.classList.add("layout-" + _layoutMode);
  if (skipResize) return;
  const h = _LAYOUT_HEIGHTS[_layoutMode];
  
  const isFrameless = _settings && _settings.frameless;
  const currentOuterW = isFrameless ? window.innerWidth : (window.innerWidth + 16);
  
  if (window.pywebview?.api?.set_window_size) {
    window.pywebview.api.set_window_size(currentOuterW, h);
  }
}

function _cycleLayout() {
  if (_CURRENT_SKIN === "2") {
    showToast("Classic skin — layout is fixed", 1600);
    return;
  }

  if (_CURRENT_SKIN === "4" || _CURRENT_SKIN === "5" || _CURRENT_SKIN === "6" || _CURRENT_SKIN === "8") {
    const panel = document.getElementById("overlay") || document.getElementById("danPanel");
    if (!panel) return;
    // Single source of truth: both classes stay in sync. The ui-8 HTML starts
    // with only "expanded", so independent toggles would desync and the OR
    // check below would report expanded forever (never collapsing).
    const willExpand = !(panel.classList.contains("is-expanded") || panel.classList.contains("expanded"));
    panel.classList.toggle("expanded", willExpand);
    panel.classList.toggle("is-expanded", willExpand);
    const isExp = willExpand;
    if (typeof showToast === "function") showToast(isExp ? "Map info: Expanded" : "Map info: Hidden", 1600);
    
    // Ignore the programmatic resize to prevent double-stretching the UI
    window._ignoreNextP2Resize = true;
    if (typeof window._resetP2ResizeStates === "function") window._resetP2ResizeStates();
    
    // PyWebView's _window.width can be stale on Windows, so we pass the accurate outerWidth from JS
    const isFrameless = _settings && _settings.frameless;
    const currentOuterW = isFrameless ? window.innerWidth : (window.innerWidth + 16);

    if (_CURRENT_SKIN === "4" && window.pywebview?.api?.set_window_size) {
      window.pywebview.api.set_window_size(currentOuterW, isExp ? 466 : 335);
    } else if (_CURRENT_SKIN === "5" && window.pywebview?.api?.set_window_size) {
      window.pywebview.api.set_window_size(currentOuterW, isExp ? 272 : 170);
      document.documentElement.style.zoom = isExp ? 0.75 : 0.75;
    } else if (_CURRENT_SKIN === "6" && window.pywebview?.api?.set_window_size) {
      window.pywebview.api.set_window_size(currentOuterW, isExp ? 297 : 211);
      document.documentElement.style.zoom = isExp ? 0.73 : 0.73;
    } else if (_CURRENT_SKIN === "8" && window.pywebview?.api?.set_window_size) {
      window.pywebview.api.set_window_size(594, isExp ? 234 : 138);
      document.documentElement.style.zoom = 0.94;
    }
    return;
  }

  const idx = _LAYOUT_MODES.indexOf(_layoutMode);
  _layoutMode = _LAYOUT_MODES[(idx + 1) % _LAYOUT_MODES.length];
  _settings.layout = _layoutMode;
  void _saveSettings();
  _applyLayoutMode(false);
  const labels = { complete: "Layout: Full ◱", simplified: "Layout: Simplified ◇", compact: "Layout: Compact ▪" };
  if (typeof showToast === "function") showToast(labels[_layoutMode], 1600);
}

function isKeybind(action, e) {
  if (e.metaKey) return false;
  const kb = _settings.keybinds[action] || _DEFAULT_KEYBINDS[action];
  if (!kb) return false;
  return e.key.toLowerCase() === kb.key.toLowerCase() &&
    !!e.ctrlKey === !!kb.ctrl &&
    !!e.altKey === !!kb.alt;
}

function _cfgIsOpen() {
  return document.getElementById("cfgOverlay")?.classList.contains("is-open") === true;
}

// ── Scoring mode: "reform" (default) or "celestial" ───────────────────────────
let _scoringMode = "reform";
// LN auto-override: true when current map is LN-routed, reverts on next rice map
let _lnOverrideActive = false;
// LN manual pin: when true, LN Course mode stays forced regardless of pipeline
let _lnModePinned = false;
// Cache of the last received analysis payload so we can re-render when
// the user toggles mode without waiting for a new analysis result.
let _lastAnalysisPayload = null;

function _updateScoringModeBadge() {
  const badge = document.getElementById("scoringModeBadge");
  if (!badge) return;
  if (_lnOverrideActive) {
    badge.textContent = "♬ Mode: LN Course";
    badge.dataset.mode = "ln_course";
  } else if (_scoringMode === "celestial") {
    badge.textContent = "✦ Mode: Celestial";
    badge.dataset.mode = "celestial";
  } else if (_scoringMode === "signicial") {
    badge.textContent = "◆ Mode: Signicial";
    badge.dataset.mode = "signicial";
  } else if (_scoringMode === "shoegazer") {
    badge.textContent = "♫ Mode: Shoegazer";
    badge.dataset.mode = "shoegazer";
  } else {
    badge.textContent = "◇ Mode: Reform";
    badge.dataset.mode = "reform";
  }
}
let mapTitleSyncRaf = 0;

function modeToLabel(modeValue) {
  if (modeValue == null) {
    return "Unknown";
  }

  if (typeof modeValue === "number" || /^\d+$/.test(String(modeValue))) {
    const modeNum = Number(modeValue);
    if (modeNum === 0) return "osu!standard";
    if (modeNum === 1) return "osu!taiko";
    if (modeNum === 2) return "osu!catch";
    if (modeNum === 3) return "osu!mania";
    return `mode ${modeNum}`;
  }

  const text = String(modeValue).trim();
  if (!text) return "Unknown";
  if (/mania/i.test(text)) return "osu!mania";
  return text;
}

function extractMapSupportInfo(payload) {
  const modeCandidates = [
    safeGet(payload, "menu.gameMode", null),
    safeGet(payload, "menu.bm.mode", null),
    safeGet(payload, "menu.bm.metadata.mode", null)
  ];
  const modeRaw = modeCandidates.find((value) => value != null && String(value).trim() !== "");

  const modeNum = Number(modeRaw);
  const modeText = String(modeRaw || "").toLowerCase();
  const isMania = (!Number.isNaN(modeNum) && modeNum === 3) || modeText.includes("mania");

  const keyCandidates = [
    safeGet(payload, "menu.bm.stats.keys", null),
    safeGet(payload, "menu.bm.stats.keyCount", null),
    safeGet(payload, "menu.bm.metadata.keyCount", null),
    safeGet(payload, "menu.bm.metadata.keys", null)
  ];
  const keyRaw = keyCandidates.find((value) => value != null && String(value).trim() !== "");
  const keyCount = Number.isFinite(Number(keyRaw)) ? Number(keyRaw) : null;

  let supported = true;
  let reason = "";

  if (!isMania) {
    supported = false;
    reason = `Unsupported mode: ${modeToLabel(modeRaw)}. Please select an osu!mania 4K map.`;
  } else if (keyCount != null && keyCount !== 4) {
    supported = false;
    reason = `Unsupported key mode: ${keyCount}K. Please select an osu!mania 4K map.`;
  }

  return {
    supported,
    reason,
    modeLabel: modeToLabel(modeRaw),
    keyCount
  };
}

function applyUnsupportedMapWarning(info) {
  finishMapTransition();
  ui.panel.classList.remove("is-loading");
  setChartButtonReady(false);
  setAnimatedText(ui.badgeLeft, "WARNING");
  setAnimatedText(ui.badgeCenter, "UNSUPPORTED MAP");
  setAnimatedText(ui.badgeRight, "MANIA 4K ONLY");

  setAnimatedText(ui.danName, "---");
  setAnimatedText(ui.danSub, info.keyCount != null ? `${info.keyCount}K` : info.modeLabel);
  if (ui.chartFamily) { ui.chartFamily.textContent = ""; ui.chartFamily.removeAttribute("data-family"); }
  if (ui.metrics) ui.metrics.textContent = "--.-";
  setOptionalText(ui.details, "Unsupported map type");
  setOptionalText(ui.bands, `Mode: ${info.modeLabel}${info.keyCount != null ? ` · Keys: ${info.keyCount}K` : ""}`);

  // Update compact-bar left column with the warning message
  if (ui.mapTitle) ui.mapTitle.textContent = `${info.modeLabel}${info.keyCount != null ? ` ${info.keyCount}K` : ""} — Unsupported`;
  if (ui.mapArtist) ui.mapArtist.textContent = "Please select an osu!mania 4K map";

  if (ui.progressWrap) {
    ui.progressWrap.classList.remove("showing", "paused", "finished");
  }
}


function safeGet(obj, path, fallback = undefined) {
  try {
    return path.split(".").reduce((acc, key) => (acc == null ? undefined : acc[key]), obj) ?? fallback;
  } catch (_err) {
    return fallback;
  }
}

function normalizeText(text) {
  const compact = String(text || "").replace(/\s+/g, " ").trim();
  return compact || "Waiting for data...";
}

function withEnterAnimation(el) {
  el.classList.remove("entering");
  // Force reflow for restart.
  void el.offsetWidth;
  el.classList.add("entering");
}

function setAnimatedText(el, text) {
  const value = normalizeText(text);
  if (el.dataset.lastText === value) {
    return;
  }
  el.dataset.lastText = value;
  el.textContent = value;
  withEnterAnimation(el);
}

function setOptionalText(el, text) {
  if (!el || text == null) {
    return;
  }

  const value = String(text).replace(/\s+/g, " ").trim();
  if (!value) {
    el.dataset.lastText = "";
    el.textContent = "";
    return;
  }

  setAnimatedText(el, value);
}

let _chartReady = false;

function setChartButtonReady(isReady) {
  _chartReady = !!isReady;
}

function setChartGenerating(isGenerating) {
  chartGenerating = !!isGenerating;
}

function setChartDone() {
  chartGenerating = false;
  showToast("✓ Chart generated", 2000);
}

function setTickerText(tickerEl, text) {
  const value = normalizeText(text);
  if (tickerEl.dataset.lastText === value) {
    return;
  }
  tickerEl.dataset.lastText = value;

  const track = tickerEl.querySelector(".marquee-track");
  const spans = track.querySelectorAll("span");
  const repeated = `${value}     •     ${value}     •     `;
  spans[0].textContent = repeated;
  spans[1].textContent = repeated;

  const approxPixels = Math.max(460, value.length * 18);
  const duration = Math.max(9, approxPixels / 78);
  track.style.setProperty("--duration", `${duration.toFixed(2)}s`);

  tickerEl.classList.remove("enter");
  void tickerEl.offsetWidth;
  tickerEl.classList.add("enter");
}

function bpmToString(bpmObj) {
  if (typeof bpmObj === "number") {
    return `${Math.round(bpmObj)}`;
  }
  if (!bpmObj || typeof bpmObj !== "object") {
    return "--";
  }
  const min = Math.round(Number(bpmObj.min || 0));
  const max = Math.round(Number(bpmObj.max || 0));
  const common = Math.round(Number(bpmObj.common || min || 0));
  if (!min && !max && !common) {
    return "--";
  }
  if (min && max && min !== max) {
    return `${min}-${max} (${common})`;
  }
  return `${common || min || max}`;
}

function msToClock(ms) {
  const value = Number(ms || 0);
  if (!value || Number.isNaN(value)) {
    return "--:--";
  }
  const total = Math.floor(value / 1000);
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function buildMapKey(artist, title, version) {
  return [artist || "", title || "", version || ""].join("|");
}

function normalizeMapDurationMs(ms) {
  const value = Number(ms || 0);
  if (!Number.isFinite(value) || value <= 0) {
    return 0;
  }
  return Math.max(1000, Math.round(value / 1000) * 1000);
}

function updateStableMapDuration(rawMs, force = false) {
  const normalized = normalizeMapDurationMs(rawMs);
  if (!normalized) {
    return currentTotalMs;
  }

  if (force || currentTotalMs <= 0) {
    currentTotalMs = normalized;
    return currentTotalMs;
  }

  if (currentPlaybackMs <= 0) {
    currentTotalMs = Math.max(currentTotalMs, normalized);
    return currentTotalMs;
  }

  if (Math.abs(normalized - currentTotalMs) >= 2500) {
    currentTotalMs = normalized;
  }

  return currentTotalMs;
}

function renderMapDuration(currentMs = 0, fullMs = 0, hasPlayback = false) {
  // Bail only when there is nothing to update: skins without #mapDuration
  // (e.g. ui-8) still mirror the timer into #ui-len, and the playback
  // globals (currentPlaybackMs/currentTotalMs) must keep advancing.
  const uiLenEl = document.getElementById("ui-len");
  if (!ui.mapDuration && !uiLenEl) return;

  const newMs = Number(currentMs) || 0;
  const stableTotalMs = updateStableMapDuration(fullMs);

  // Monotonic guard: ignore small backwards jumps (< 2 s) to prevent flicker
  if (newMs >= 0) {
    const delta = newMs - currentPlaybackMs;
    if (delta >= 0 || delta < -2000 || currentPlaybackMs <= 0) {
      currentPlaybackMs = newMs;
    }
  }

  // Sync progress bar
  if (ui.drainBar) {
    if (stableTotalMs > 0) {
      const clampedPlaybackMs = Math.max(0, Math.min(currentPlaybackMs, stableTotalMs));
      const pct = Math.max(0, Math.min(100, (clampedPlaybackMs / stableTotalMs) * 100));
      ui.drainBar.style.width = pct.toFixed(2) + "%";
    } else {
      ui.drainBar.style.width = "0%";
    }
  }

  if (!stableTotalMs) {
    if (ui.mapDuration && ui.mapDuration.textContent !== "--:--") {
      ui.mapDuration.textContent = "--:--";
    }
    const lenEl = document.getElementById("ui-len");
    if (lenEl && lenEl.textContent !== "--:--") {
      lenEl.textContent = "--:--";
    }
    return;
  }

  const left = hasPlayback || currentPlaybackMs > 0
    ? (currentPlaybackMs > 0 ? msToClock(currentPlaybackMs) : "0:00")
    : "0:00";
  const text = left + " / " + msToClock(stableTotalMs);
  if (ui.mapDuration && ui.mapDuration.textContent !== text) {
    ui.mapDuration.textContent = text;
  }
  const lenEl = document.getElementById("ui-len");
  if (lenEl && lenEl.textContent !== text) {
    lenEl.textContent = text;
  }
}

function syncMapTitleMarquee() {
  if (mapTitleSyncRaf) {
    cancelAnimationFrame(mapTitleSyncRaf);
  }

  mapTitleSyncRaf = requestAnimationFrame(() => {
    // 1. Sync main title marquee
    if (ui.mapTitleWrap && ui.mapTitleTrack && ui.mapTitle && ui.mapTitleGhost) {
      syncSingleMarquee(ui.mapTitleWrap, ui.mapTitleTrack, ui.mapTitle, ui.mapTitleGhost);
    }
    // 2. Sync skin drawer title marquee
    if (ui.skinMapTitleWrap && ui.skinMapTitleTrack && ui.skinMapTitle && ui.skinMapTitleGhost) {
      syncSingleMarquee(ui.skinMapTitleWrap, ui.skinMapTitleTrack, ui.skinMapTitle, ui.skinMapTitleGhost);
    }
  });
}

function syncSingleMarquee(wrap, track, title, ghost) {
  const wrapWidth = wrap.clientWidth;
  const titleWidth = title.scrollWidth;
  const gap = 40;

  wrap.classList.remove("has-marquee");
  track.classList.remove("is-marquee");
  track.style.removeProperty("--title-shift");
  track.style.removeProperty("--title-duration");

  if (!wrapWidth || !titleWidth || titleWidth <= wrapWidth + 6) {
    return;
  }

  const shift = titleWidth + gap;
  const duration = Math.max(10, shift / 38);
  track.style.setProperty("--title-shift", `${shift}px`);
  track.style.setProperty("--title-duration", `${duration.toFixed(2)}s`);
  track.classList.add("is-marquee");
  wrap.classList.add("has-marquee");
}

function setMapTitleText(text) {
  const value = String(text || "Waiting for beatmap...").replace(/\s+/g, " ").trim() || "Waiting for beatmap...";
  if (ui.mapTitle) {
    ui.mapTitle.textContent = value;
  }
  if (ui.mapTitleGhost) {
    ui.mapTitleGhost.textContent = value;
  }
  // Mirror to the skinMapTitle used in ui-4/5/6 expanded drawers
  if (ui.skinMapTitle) {
    ui.skinMapTitle.textContent = value;
  }
  if (ui.skinMapTitleGhost) {
    ui.skinMapTitleGhost.textContent = value;
  }
  syncMapTitleMarquee();
}

function hasDanResultOnScreen() {
  return !!String(lastDanRaw || "").trim();
}

function startMapTransition() {
  setChartGenerating(false);
  setChartButtonReady(false);
  clearTimeout(prog_finishTimeout);
  clearTimeout(_transitionSafetyTimer);
  prog_wasPlaying = false;
  prog_lastMs = 0;
  prog_lastAcc = 0;
  prog_isPaused = false;
  prog_lastSeenMs = -1;
  prog_playingAt = 0;
  _cachedBpmRange = null;
  if (ui.pausedOverlay) ui.pausedOverlay.classList.remove("is-visible");
  currentPlaybackMs = 0;
  currentTotalMs = 0;
  ui.panel.classList.remove("is-loading");
  ui.panel.classList.add("is-map-transition");
  if (ui.progressWrap) {
    ui.progressWrap.classList.remove("showing", "paused", "finished");
  }
  if (ui.drainBar) {
    ui.drainBar.style.width = "0%";
  }

  // Only use the full blackout transition when we are replacing an existing
  // dan result. On first load there is nothing stale to hide, so keep the
  // normal loading screen visible instead of masking the whole overlay.
  if (!hasDanResultOnScreen()) {
    isMapTransitioning = false;
    ui.panel.classList.remove("is-loading", "is-map-transition");
    return;
  }

  isMapTransitioning = true;
  ui.panel.classList.remove("is-loading");
  ui.panel.classList.add("is-map-transition");

  // Safety: if no result arrives in 10 s, stop hiding the overlay.
  _transitionSafetyTimer = setTimeout(() => {
    if (isMapTransitioning) {
      finishMapTransition();
      applyLoading("Computing");
    }
  }, 10000);
}

function finishMapTransition() {
  clearTimeout(_transitionSafetyTimer);
  isMapTransitioning = false;
  ui.panel.classList.remove("is-map-transition");
}

function extractTimeState(payload) {
  const currentMs = Number(
    safeGet(payload, "menu.bm.time.current", safeGet(payload, "ms", 0)) || 0
  );
  const fullMs = Number(
    safeGet(
      payload,
      "menu.bm.time.mp3",
      safeGet(payload, "total_ms", safeGet(payload, "menu.bm.time.full", 0))
    ) || 0
  );
  const state = Number(safeGet(payload, "menu.state", safeGet(payload, "game_state", 0)) || 0);
  const playing = state === 2 || !!safeGet(payload, "playing", false);
  return { currentMs, fullMs, state, playing };
}

function parseDanOverlay(raw) {
  const lines = String(raw || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  if (!lines.length) {
    return null;
  }

  // strip the common prefix; allow optional space before colon in case the
  // string is formatted "Est. Dan :" or similar
  const first = lines[0].replace(/^Est\.\s*Dan\s*:\s*/i, "").trim();
  let danName = first;
  let danSuffix = "";

  for (const candidate of DAN_NAMES) {
    if (first.startsWith(candidate)) {
      danName = candidate;
      danSuffix = first
        .slice(candidate.length)
        .replace(/^[\s\u00b7:|\-]+/, "")
        .trim();
      break;
    }
  }

  const metrics = lines[1] || "No metrics available";
  const details = lines[2] || "Chart: - | Mapper: -";
  const bands = lines[3] || "";
  const density = lines[4] || "";

  const chartMatch = details.match(/Chart:\s*([^|\u00b7]+)/i);
  const chart = chartMatch ? chartMatch[1].trim().toUpperCase() : "PATTERN";

  return {
    danName,
    danSuffix,
    metrics,
    details,
    bands,
    density,
    chart
  };
}

function paletteForDan(danName) {
  return DAN_PALETTES[danName] || DAN_PALETTES["4th Dan"];
}

function paletteToGradient(palette) {
  if (!palette || !palette.length) {
    return "linear-gradient(90deg, rgb(120,155,255), rgb(168,205,255))";
  }
  return `linear-gradient(90deg, ${palette.join(", ")})`;
}

function paletteMidColor(palette) {
  if (!palette || !palette.length) {
    return "rgb(120,155,255)";
  }
  return palette[Math.floor(palette.length / 2)];
}

function parseRGB(colorStr) {
  const m = String(colorStr).match(/(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/);
  return m ? [+m[1], +m[2], +m[3]] : [120, 155, 255];
}

// Relative luminance (0 = black, 1 = white) per WCAG formula
function relativeLuminance(rgb) {
  const [r, g, b] = rgb.map(c => {
    c /= 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/* ── Analysis rendering (shared by WS handler + mode toggle) ─────────── */
function _renderAnalysisPayload(payload) {
  if (!payload) return;

  const SKILLSET_LABELS = {
    stream: "STREAM", jumpstream: "JS", handstream: "HS",
    stamina: "STAM", jackspeed: "JACK", chordjack: "CJ", technical: "TECH",
  };
  const SKILLSET_FAMILY = {
    stream: "STREAM", jumpstream: "STREAM",
    handstream: "STAMINA", stamina: "STAMINA",
    jackspeed: "JACK", chordjack: "JACK",
    technical: "TECH",
  };

  // ── Top-2 MinaCalc skillsets for chart type label ──────────────
  const skillsets = payload.skillsets || {};
  const topTwo = Object.entries(skillsets)
    .filter(([, v]) => Number(v) > 0)
    .sort((a, b) => Number(b[1]) - Number(a[1]))
    .slice(0, 2);
  const top1 = topTwo[0];
  const top2 = topTwo[1];
  const lbl1 = top1 ? (SKILLSET_LABELS[top1[0]] || top1[0].toUpperCase()) : "";
  const lbl2 = top2 ? (SKILLSET_LABELS[top2[0]] || top2[0].toUpperCase()) : "";
  const showBoth = top2 && (Number(top2[1]) / Number(top1[1])) > 0.55;
  const familyText = showBoth ? `${lbl1} · ${lbl2}` : (lbl1 || "PATTERN");
  const primaryFamily = top1 ? (SKILLSET_FAMILY[top1[0]] || "HYBRID") : "HYBRID";

  // ── Mod badge ──────────────────────────────────────────────────
  const modLabel = String(payload.mod || "");
  if (ui.modBadge) {
    ui.modBadge.textContent = modLabel;
    ui.modBadge.dataset.mod = modLabel;
    ui.modBadge.classList.remove("recalculating");
  }

  // ── Sunny Rebirth skin (ui-7) ──────────────────────────────────
  // Runs before the LN/7K/mode-specific early returns so the SR badge,
  // strain bars, map title and MANIA 4K/7K badge always update for
  // every map type (4K, 7K, LN) and every scoring mode.
  _updateSunnyRebirthSkin(payload);
  _updateHeroDanLazerSkin(payload);

  // ── Sunny Rebirth skin is SR-only ──────────────────────────────
  // No mode result screens (LN Course, Celestial, Signicial,
  // Shoegazer, 7K tier card) — the skin shows the map's Sunny SR and
  // nothing else.  Keep only the pieces the skin needs: metrics value,
  // chart readiness and map-transition cleanup.
  if (_CURRENT_SKIN === "7") {
    finishMapTransition();
    const metricsEl = document.getElementById("danMetrics");
    if (metricsEl) {
      const msd = Number(payload.overall_msd || 0);
      metricsEl.textContent = msd > 0 ? msd.toFixed(2) : "--.-";
    }
    setChartButtonReady(true);
    if (ui.density) { ui.density.innerHTML = ""; ui.density.classList.remove("has-data"); }
    return;
  }

  // ── LN Course auto-override ─────────────────────────────────────
  // When the pipeline detects an LN map, ln_course takes priority over
  // whatever rice mode the user has selected.
  const lnCourse = payload.ln_course;
  if (_lnOverrideActive && lnCourse && lnCourse.label) {
    const lBeyond = Boolean(lnCourse.beyond);
    const lLabel = String(lnCourse.label);
    const lShort = lBeyond ? "∞" : String(lnCourse.short || "");
    const lKey = String(lnCourse.stage_key || "1st");
    const lDp = Number(lnCourse.dp_ln || 0);
    const lFrac = lDp - Math.floor(lDp);
    const lSublevel = lFrac <= 0.20 ? "Low" : lFrac <= 0.40 ? "Mid-Low" : lFrac <= 0.60 ? "Mid" : lFrac <= 0.80 ? "Mid-High" : "High";
    const displayMsd = Number(payload.overall_msd || 0);

    lastDanRaw = `LN Course: ${lLabel}${lBeyond ? " (Beyond)" : ""}`;
    applyDanResult({
      danName: lLabel,
      danShort: lShort,
      dp: lDp,
      danSuffix: lBeyond ? "Beyond" : lSublevel,
      metrics: displayMsd > 0 ? displayMsd.toFixed(2) : "--.-",
      chart: familyText,
      chartColor: primaryFamily,
      lnCourseMode: true,
      lnCourseStage: lKey,
    });
    setChartButtonReady(true);
    if (ui.density) { ui.density.innerHTML = ""; ui.density.classList.remove("has-data"); }
    return;
  }

  // ── MSD unavailable guard ────────────────────────────────────────
  // Celestial / Signicial / Shoegazer all depend on MinaCalc skillsets.
  // When MSD failed the payload will have null for those fields. Instead of
  // silently falling through and showing Reform dans, show the reform result
  // with an "MSD error" annotation and the correct mode palette/badge.
  const celestial = payload.celestial;
  const _signicialRaw = payload.signicial;
  const _shoegazerRaw = payload.shoegazer;

  if (payload.mode === "7k" && payload.tier_7k) {
      const tDp = Number(payload.dp_7k || 0);
      lastDanRaw = "7K Tier: " + payload.tier_7k;
      applyDanResult({
          danName: payload.tier_7k,
          danShort: payload.tier_7k.substring(0, 3).toUpperCase(),
          dp: tDp,
          danSuffix: payload.sublevel_7k || "-",
          metrics: payload.sr > 0 ? payload.sr.toFixed(2) : "--.-",
          chart: "7K",
          chartColor: "HYBRID",
          mode7k: true,
          tier7k: payload.tier_7k,
      });
      setChartButtonReady(true);
      if (ui.density) { ui.density.innerHTML = ""; ui.density.classList.remove("has-data"); }
      return;
  }

  const _modeNeedsData = _scoringMode === "celestial" || _scoringMode === "signicial" || _scoringMode === "shoegazer";
  const _modeDataMissing =
    (_scoringMode === "celestial" && (!celestial || !celestial.label)) ||
    (_scoringMode === "signicial" && (!_signicialRaw || !_signicialRaw.label)) ||
    (_scoringMode === "shoegazer" && (!_shoegazerRaw || !_shoegazerRaw.label));

  if (_modeNeedsData && _modeDataMissing) {
    const _msdErrResult = {
      danName: String(payload.dan_label || "\u2013"),
      danShort: String(payload.dan_short || ""),
      dp: Number(payload.dp || 0),
      danSuffix: "MSD error",
      metrics: "--.-",
      chart: familyText,
      chartColor: primaryFamily,
    };
    if (_scoringMode === "celestial") {
      _msdErrResult.celestialMode = true;
      _msdErrResult.celestialTier = "Beginner";
    } else if (_scoringMode === "signicial") {
      _msdErrResult.signicialMode = true;
      _msdErrResult.signicialStage = "I";
    } else if (_scoringMode === "shoegazer") {
      _msdErrResult.shoegazerMode = true;
      _msdErrResult.shoegazerStage = "1st";
    }
    lastDanRaw = `Est. Dan: ${_msdErrResult.danName}`;
    applyDanResult(_msdErrResult);
    setChartButtonReady(false);
    if (ui.density) { ui.density.innerHTML = ""; ui.density.classList.remove("has-data"); }
    return;
  }

  // ── Celestial mode override ──────────────────────────────────────
  if (_scoringMode === "celestial" && celestial && celestial.label) {
    const cBeyond = Boolean(celestial.beyond);
    const cLabel = String(celestial.label);
    const cShort = cBeyond ? "∞" : String(celestial.short);
    const cConf = Number(celestial.confidence || 0);
    const confPct = Math.round(cConf * 100);
    const displayMsd = Number(payload.overall_msd || 0);

    const cDp = Number(celestial.dp_celestial || 0);
    const cFrac = cDp - Math.floor(cDp);
    const cSublevel = cFrac <= 0.20 ? "Low" : cFrac <= 0.40 ? "Mid-Low" : cFrac <= 0.60 ? "Mid" : cFrac <= 0.80 ? "Mid-High" : "High";

    lastDanRaw = `Celestial: ${cLabel}${cBeyond ? " (Beyond)" : ""}`;
    applyDanResult({
      danName: cLabel,
      danShort: cShort,
      dp: cDp,
      danSuffix: cBeyond ? "Beyond" : cSublevel,
      metrics: displayMsd > 0 ? displayMsd.toFixed(2) : "--.-",
      chart: familyText,
      chartColor: primaryFamily,
      celestialMode: true,
      celestialTier: String(celestial.tier || ""),
    });
    setChartButtonReady(true);
    if (ui.density) { ui.density.innerHTML = ""; ui.density.classList.remove("has-data"); }
    return;
  }

  // ── Signicial mode override ──────────────────────────────────────
  const signicial = _signicialRaw;
  if (_scoringMode === "signicial" && signicial && signicial.label) {
    const sBeyond = Boolean(signicial.beyond);
    const sLabel = String(signicial.label);
    const sShort = sBeyond ? "∞" : String(signicial.short || "");
    const sKey = String(signicial.stage_key || "");
    const sSubtitle = (typeof SIGNICIAL_SUBTITLES !== "undefined" && SIGNICIAL_SUBTITLES[sKey]) || (signicial && signicial.subtitle) || "";
    const sDp = Number(signicial.dp_signicial || 0);
    const sFrac = sDp - Math.floor(sDp);
    const sSublevel = sFrac <= 0.20 ? "Low" : sFrac <= 0.40 ? "Mid-Low" : sFrac <= 0.60 ? "Mid" : sFrac <= 0.80 ? "Mid-High" : "High";
    const sSuffix = sBeyond ? "Beyond" : sSublevel;
    const displayMsd = Number(payload.overall_msd || 0);

    lastDanRaw = `Signicial: ${sLabel}${sBeyond ? " (Beyond)" : ""}`;
    applyDanResult({
      danName: sLabel,
      danShort: sShort,
      dp: sDp,
      danSuffix: sSuffix,
      metrics: displayMsd > 0 ? displayMsd.toFixed(2) : "--.-",
      chart: familyText,
      chartColor: primaryFamily,
      signicialMode: true,
      signicialStage: sKey,
    });
    setChartButtonReady(true);
    if (ui.density) { ui.density.innerHTML = ""; ui.density.classList.remove("has-data"); }
    return;
  }

  // ── Shoegazer mode override ──────────────────────────────────────
  const shoegazer = _shoegazerRaw;
  if (_scoringMode === "shoegazer" && shoegazer && shoegazer.label) {
    const gBeyond = Boolean(shoegazer.beyond);
    const gLabel = String(shoegazer.label);
    const gShort = gBeyond ? "∞" : String(shoegazer.short || "");
    const gKey = String(shoegazer.stage_key || "");
    const gDp = Number(shoegazer.dp_shoegazer || 0);
    const displayMsd = Number(payload.overall_msd || 0);
    const gFrac = gDp - Math.floor(gDp);
    const gSublevel = gFrac <= 0.20 ? "Low" : gFrac <= 0.40 ? "Mid-Low" : gFrac <= 0.60 ? "Mid" : gFrac <= 0.80 ? "Mid-High" : "High";
    const gSuffix = gBeyond ? "Beyond" : gSublevel;

    lastDanRaw = `Shoegazer: ${gLabel}${gBeyond ? " (Beyond)" : ""}`;
    applyDanResult({
      danName: gLabel,
      danShort: gShort,
      dp: gDp,
      danSuffix: gSuffix,
      metrics: displayMsd > 0 ? displayMsd.toFixed(2) : "--.-",
      chart: familyText,
      chartColor: primaryFamily,
      shoegazerMode: true,
      shoegazerStage: gKey,
    });
    setChartButtonReady(true);
    if (ui.density) { ui.density.innerHTML = ""; ui.density.classList.remove("has-data"); }
    return;
  }

  // ── Reform mode (default) ────────────────────────────────────────
  const label = String(payload.dan_label || "Unknown");
  const sublevel = String(payload.sublevel || "");
  const rBeyond = Boolean(payload.beyond);
  const displayMsd = Number(payload.overall_msd || 0);
  const displayName = label;
  const displaySuffix = rBeyond ? "Beyond" : (sublevel || "-");

  lastDanRaw = `Est. Dan: ${displayName}${rBeyond ? " (Beyond)" : ""}`;
  applyDanResult({
    danName: displayName,
    danShort: String(payload.dan_short || ""),
    dp: Number(payload.dp || 0),
    danSuffix: displaySuffix,
    metrics: displayMsd > 0 ? displayMsd.toFixed(2) : "--.-",
    chart: familyText,
    chartColor: primaryFamily,
  });
  setChartButtonReady(true);
  if (ui.density) { ui.density.innerHTML = ""; ui.density.classList.remove("has-data"); }
}

let _sunnyAnimReqs = {};
let _sunnyDotsInterval = null;

function _startSunnyDotsAnimation() {
  _stopSunnyDotsAnimation();
  let count = 1;
  const updateDots = () => {
    const dots = ".".repeat(count);
    const srEl = document.getElementById("ui-sr-num");
    if (srEl) srEl.textContent = dots;
    ["jbar", "pbar", "xbar", "abar"].forEach(bar => {
      const valEl = document.getElementById("val-" + bar);
      if (valEl) valEl.textContent = dots;
      const fillEl = document.getElementById("fill-" + bar);
      if (fillEl) fillEl.style.width = "0%";
    });
    const skillsetEl = document.getElementById("ui-skillset");
    if (skillsetEl) skillsetEl.textContent = dots;
    const msdEl = document.getElementById("danMetrics");
    if (msdEl) msdEl.textContent = dots;
    const statusEl = document.getElementById("ui-status");
    if (statusEl) {
      statusEl.textContent = "SCANNING" + dots;
      statusEl.style.color = "#aaaaaa";
    }
    count = (count % 3) + 1;
  };
  updateDots();
  _sunnyDotsInterval = setInterval(updateDots, 400);
}

function _stopSunnyDotsAnimation() {
  if (_sunnyDotsInterval) {
    clearInterval(_sunnyDotsInterval);
    _sunnyDotsInterval = null;
  }
}

function _animateSunnyMetric(id, start, end, duration = 800, decimals = 1, isWidth = false) {
  if (_sunnyAnimReqs[id]) window.cancelAnimationFrame(_sunnyAnimReqs[id]);
  let startTimestamp = null;
  const step = (timestamp) => {
    if (!startTimestamp) startTimestamp = timestamp;
    const progress = Math.min((timestamp - startTimestamp) / duration, 1);
    const ease = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
    const current = start + (end - start) * ease;
    const el = document.getElementById(id);
    if (el) {
      if (isWidth) {
        el.style.width = `${Math.min(100, Math.max(0, current))}%`;
      } else {
        el.textContent = current.toFixed(decimals);
      }
    }
    if (progress < 1) {
      _sunnyAnimReqs[id] = window.requestAnimationFrame(step);
    }
  };
  _sunnyAnimReqs[id] = window.requestAnimationFrame(step);
}

function _updateSunnyRebirthSkin(payload) {
  _stopSunnyDotsAnimation();
  const srNumEl = document.getElementById("ui-sr-num");
  const overlay = document.getElementById("overlay");
  if (overlay) overlay.classList.remove("computing-mode");
  if (!srNumEl || !payload) return;

  const srVal = Number(payload.sunny_sr || payload.sr || payload.overall_msd || 0);
  const prevSR = parseFloat(srNumEl.textContent) || 0;

  if (typeof window.__applySunnyPalette === "function") {
    window.__applySunnyPalette(srVal);
  }

  _animateSunnyMetric("ui-sr-num", prevSR, srVal, 800, 2);

  const debugData = payload.debug?.sr_result || payload.debug || {};
  const jbar = Number(payload.jbar_max ?? debugData.jbar_max ?? debugData.jbar ?? 0);
  const pbar = Number(payload.pbar_max ?? debugData.pbar_max ?? debugData.pbar ?? 0);
  const xbar = Number(payload.xbar_max ?? debugData.xbar_max ?? debugData.xbar ?? 0);
  const abar = Number(payload.abar_mean ?? debugData.abar_mean ?? debugData.abar ?? 0);

  const curJ = parseFloat(document.getElementById("val-jbar")?.textContent) || 0;
  const curP = parseFloat(document.getElementById("val-pbar")?.textContent) || 0;
  const curX = parseFloat(document.getElementById("val-xbar")?.textContent) || 0;
  const curA = parseFloat(document.getElementById("val-abar")?.textContent) || 0;

  _animateSunnyMetric("val-jbar", curJ, jbar, 800, 1);
  _animateSunnyMetric("fill-jbar", curJ, jbar, 800, 1, true);

  _animateSunnyMetric("val-pbar", curP, pbar, 800, 1);
  _animateSunnyMetric("fill-pbar", curP, pbar, 800, 1, true);

  _animateSunnyMetric("val-xbar", curX, xbar, 800, 1);
  _animateSunnyMetric("fill-xbar", curX, xbar, 800, 1, true);

  _animateSunnyMetric("val-abar", curA, abar, 800, 1);
  _animateSunnyMetric("fill-abar", curA, abar, 800, 1, true);

  const msdVal = Number(payload.overall_msd || 0);
  const curMsd = parseFloat(document.getElementById("danMetrics")?.textContent) || 0;
  _animateSunnyMetric("danMetrics", curMsd, msdVal, 800, 1);

  const skillsetEl = document.getElementById("ui-skillset");
  if (skillsetEl) {
    const role = (payload.primary_role || payload.family || "RICE / GENERALIST").toUpperCase();
    skillsetEl.textContent = role;
  }

  const statusEl = document.getElementById("ui-status");
  if (statusEl) {
    statusEl.textContent = "READY";
    statusEl.style.color = "var(--star-accent)";
  }

  const mapTitleEl = document.getElementById("skinMapTitle");
  const mapGhostEl = document.getElementById("skinMapTitleGhost");
  if (mapTitleEl && payload) {
    const title = payload.title || payload.artist || "";
    const ver = payload.version ? ` [${payload.version}]` : "";
    if (title) {
      const fullTitle = title + ver;
      mapTitleEl.textContent = fullTitle;
      if (mapGhostEl) mapGhostEl.textContent = fullTitle;
      syncMapTitleMarquee();
    }
  }

  const keyModeEl = document.getElementById("ui-key-mode");
  if (keyModeEl && payload) {
    keyModeEl.textContent = payload.mode === "7k" ? "MANIA 7K" : "MANIA 4K";
  }
}

let _skin8DotsInterval = null;

function _startSkin8DotsAnimation() {
  _stopSkin8DotsAnimation();
  let count = 1;
  const updateDots = () => {
    const dots = ".".repeat(count);
    const danEl = document.getElementById("ui-dan-name");
    if (danEl) danEl.textContent = dots;
    const intEl = document.getElementById("ui-dp-int");
    if (intEl) intEl.textContent = dots;
    const decEl = document.getElementById("ui-dp-dec");
    if (decEl) decEl.textContent = ".";
    const tierEl = document.getElementById("ui-tier");
    if (tierEl) tierEl.textContent = "SYS_PROC";
    const pillsContainer = document.getElementById("ui-pills");
    if (pillsContainer) {
      pillsContainer.innerHTML = "";
      for (let i = 1; i <= 5; i++) {
        const p = document.createElement("div");
        p.className = "pill";
        pillsContainer.appendChild(p);
      }
    }
    const msdEl = document.getElementById("danMetrics");
    if (msdEl) msdEl.textContent = dots;
    const srEl = document.getElementById("ui-sr");
    if (srEl) srEl.textContent = dots;
    const bpmEl = document.getElementById("ui-bpm");
    if (bpmEl) bpmEl.textContent = dots;
    const lenEl = document.getElementById("ui-len");
    if (lenEl) lenEl.textContent = dots;

    count = (count % 3) + 1;
  };
  updateDots();
  _skin8DotsInterval = setInterval(updateDots, 400);
}

function _stopSkin8DotsAnimation() {
  if (_skin8DotsInterval) {
    clearInterval(_skin8DotsInterval);
    _skin8DotsInterval = null;
  }
}

function _animateHeroDP(startDP, endDP, duration = 800) {
  if (_sunnyAnimReqs["hero_dp"]) window.cancelAnimationFrame(_sunnyAnimReqs["hero_dp"]);
  let startTimestamp = null;
  const step = (timestamp) => {
    if (!startTimestamp) startTimestamp = timestamp;
    const progress = Math.min((timestamp - startTimestamp) / duration, 1);
    const ease = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
    const current = startDP + (endDP - startDP) * ease;
    const splitStr = current.toFixed(2).split(".");
    const intEl = document.getElementById("ui-dp-int");
    const decEl = document.getElementById("ui-dp-dec");
    if (intEl) intEl.textContent = splitStr[0];
    if (decEl) decEl.textContent = "." + (splitStr[1] || "00");
    if (progress < 1) {
      _sunnyAnimReqs["hero_dp"] = window.requestAnimationFrame(step);
    }
  };
  _sunnyAnimReqs["hero_dp"] = window.requestAnimationFrame(step);
}

function _updateHeroDanLazerSkin(payload) {
  _stopSkin8DotsAnimation();
  _stopSunnyDotsAnimation();
  const overlay = document.getElementById("overlay");
  if (overlay) overlay.classList.remove("computing-mode");
  const danNameEl = document.getElementById("ui-dan-name");
  if (!danNameEl || !payload) return;

  let category = "REFORM 4K";
  let danName = String(payload.dan_label || "1st Dan").toUpperCase();
  let dpVal = Number(payload.dp || 0);
  let palette = null;

  if (payload.mode === "7k" && payload.tier_7k) {
    category = "7K";
    danName = String(payload.tier_7k).toUpperCase();
    dpVal = Number(payload.dp_7k || 0);
    const tier7k = payload.tier_7k;
    palette = PALETTES_7K[tier7k] || PALETTES_7K[payload.dan_label] || paletteForDan(payload.dan_label) || PALETTES_7K["Gamma"];
  } else if (_lnOverrideActive && payload.ln_course && payload.ln_course.label) {
    category = "LN COURSE";
    danName = String(payload.ln_course.label).toUpperCase();
    dpVal = Number(payload.ln_course.dp_ln || payload.ln_course.dp || 0);
    const stageKey = String(payload.ln_course.stage_key || "1st");
    palette = LN_COURSE_PALETTES[stageKey] || LN_COURSE_PALETTES["1st"];
  } else if (_scoringMode === "celestial" && payload.celestial && payload.celestial.label) {
    category = "CELESTIAL 4K";
    danName = String(payload.celestial.label).toUpperCase();
    dpVal = Number(payload.celestial.dp_celestial || payload.celestial.dp || 0);
    const tierKey = String(payload.celestial.tier || "Beginner");
    palette = CELESTIAL_PALETTES[tierKey] || CELESTIAL_PALETTES["Beginner"];
  } else if (_scoringMode === "signicial" && payload.signicial && payload.signicial.label) {
    category = "SIGNICIAL 4K";
    danName = String(payload.signicial.label).toUpperCase();
    dpVal = Number(payload.signicial.dp_signicial || payload.signicial.dp || 0);
    const stageKey = String(payload.signicial.stage_key || "I");
    palette = SIGNICIAL_PALETTES[stageKey] || SIGNICIAL_PALETTES["I"];
  } else if (_scoringMode === "shoegazer" && payload.shoegazer && payload.shoegazer.label) {
    category = "SHOEGAZER 4K";
    danName = String(payload.shoegazer.label).toUpperCase();
    dpVal = Number(payload.shoegazer.dp_shoegazer || payload.shoegazer.dp || 0);
    const stageKey = String(payload.shoegazer.stage_key || "1st");
    palette = SHOEGAZER_PALETTES[stageKey] || SHOEGAZER_PALETTES["1st"];
  } else {
    category = "REFORM 4K";
    danName = String(payload.dan_label || "1st Dan").toUpperCase();
    dpVal = Number(payload.dp || 0);
    palette = paletteForDan(payload.dan_label || danName) || DAN_PALETTES["1st Dan"];
  }

  window.__currentPalette = palette;

  const catEl = document.getElementById("ui-category");
  if (catEl) catEl.textContent = category;

  danNameEl.textContent = danName;

  const decPart = Math.abs(dpVal % 1);
  let tierName = "LOW";
  let pillCount = 1;
  if (decPart > 0.80) { tierName = "HIGH"; pillCount = 5; }
  else if (decPart > 0.60) { tierName = "MID-HIGH"; pillCount = 4; }
  else if (decPart > 0.40) { tierName = "MID"; pillCount = 3; }
  else if (decPart > 0.20) { tierName = "MID-LOW"; pillCount = 2; }

  const tierEl = document.getElementById("ui-tier");
  if (tierEl) tierEl.textContent = tierName;

  const pillsContainer = document.getElementById("ui-pills");
  if (pillsContainer) {
    pillsContainer.innerHTML = "";
    for (let i = 1; i <= 5; i++) {
      const p = document.createElement("div");
      const isAct = i <= pillCount;
      p.className = `pill ${isAct ? "active" : ""}`;
      if (isAct) {
        const t = pillCount > 1 ? (i - 1) / (pillCount - 1) : 1.0;
        const pColor = palette
          ? (palette.length > 1
              ? palette[Math.min(palette.length - 1, Math.floor(t * (palette.length - 1)))]
              : palette[0])
          : c1;
        const alpha = (0.5 + t * 0.5).toFixed(2);
        p.style.backgroundColor = pColor;
        p.style.opacity = alpha;
        p.style.boxShadow = `0 0 ${Math.round(3 + t * 9)}px ${pColor}`;
      }
      pillsContainer.appendChild(p);
    }
  }

  const curInt = parseInt(document.getElementById("ui-dp-int")?.textContent) || 0;
  const curDecStr = (document.getElementById("ui-dp-dec")?.textContent || ".00").replace(".", "");
  const curDec = parseFloat("0." + curDecStr) || 0;
  const prevDP = curInt + curDec;
  _animateHeroDP(prevDP, dpVal, 800);

  const c1 = palette ? palette[0] : "#f94d79";
  const c2 = palette ? (palette[palette.length - 1] || palette[0]) : "#3080f0";
  const pillarGrad = palette
    ? `linear-gradient(180deg, ${[...palette, palette[0]].join(", ")})`
    : "linear-gradient(180deg, var(--c1), var(--c2), var(--c1))";
  document.documentElement.style.setProperty("--c1", c1);
  document.documentElement.style.setProperty("--c2", c2);
  document.documentElement.style.setProperty("--c-pillar-grad", pillarGrad);

  const mapTitleEl = document.getElementById("skinMapTitle");
  const mapGhostEl = document.getElementById("skinMapTitleGhost");
  if (mapTitleEl && payload) {
    const title = payload.title || payload.artist || "";
    const ver = payload.version ? ` [${payload.version}]` : "";
    if (title) {
      const fullTitle = title + ver;
      mapTitleEl.textContent = fullTitle;
      if (mapGhostEl) mapGhostEl.textContent = fullTitle;
      syncMapTitleMarquee();
    }
  }

  const msdVal = Number(payload.overall_msd || 0);
  const curMsd = parseFloat(document.getElementById("danMetrics")?.textContent) || 0;
  _animateSunnyMetric("danMetrics", curMsd, msdVal, 800, 1);

  const srVal = Number(payload.osu_sr || payload.sr || 0);
  const curSr = parseFloat(document.getElementById("ui-sr")?.textContent) || 0;
  _animateSunnyMetric("ui-sr", curSr, srVal, 800, 2);

  const bpmEl = document.getElementById("ui-bpm");
  if (bpmEl) bpmEl.textContent = payload.bpm ? Math.round(Number(payload.bpm)) : "--";

  const lenEl = document.getElementById("ui-len");
  if (lenEl) {
    const totalMs = payload.duration_s ? payload.duration_s * 1000 : (stableTotalMs || 0);
    const leftMs = (currentPlaybackMs > 0) ? currentPlaybackMs : 0;
    if (totalMs > 0) {
      const leftStr = msToClock(leftMs);
      const totalStr = msToClock(totalMs);
      lenEl.textContent = `${leftStr} / ${totalStr}`;
    } else {
      lenEl.textContent = "--:--";
    }
  }
}

function applyDanResult(result) {
  finishMapTransition();
  // Palette: Celestial → per-tier; Signicial → per-stage; Shoegazer → per-stage; LN Course → per-stage; Reform → per-dan
  let palette;
  if (result.lnCourseMode) {
    palette = LN_COURSE_PALETTES[result.lnCourseStage] || LN_COURSE_PALETTES["1st"];
  } else if (result.celestialMode) {
    palette = CELESTIAL_PALETTES[result.celestialTier] || CELESTIAL_PALETTES["Beginner"];
  } else if (result.signicialMode) {
    palette = SIGNICIAL_PALETTES[result.signicialStage] || SIGNICIAL_PALETTES["I"];
  } else if (result.shoegazerMode) {
    palette = SHOEGAZER_PALETTES[result.shoegazerStage] || SHOEGAZER_PALETTES["1st"];
  } else if (result.mode7k) {
    palette = PALETTES_7K[result.tier7k] || PALETTES_7K["Gamma"];
  } else {
    palette = paletteForDan(result.danName);
  }
  const gradient = paletteToGradient(palette);
  const lineColor = paletteMidColor(palette);

  // Extract individual colors for theming the entire overlay
  const primary = parseRGB(palette[0]);
  const isSkin4or5or6 = (_CURRENT_SKIN === "4" || _CURRENT_SKIN === "5" || _CURRENT_SKIN === "6");
  const secondaryIdx = (isSkin4or5or6 && palette.length >= 3) ? 1 : (palette.length - 1);
  const secondary = parseRGB(palette[secondaryIdx]);

  // Check if the dan colors are dark; if so, the ticker panels need a
  // lighter background so the text remains readable.
  const avgLum = (relativeLuminance(primary) + relativeLuminance(secondary)) / 2;
  const isDark = avgLum < 0.18;

  const root = document.documentElement.style;
  root.setProperty("--dan-gradient", gradient);
  // Looping gradient: palette doubled + close → background-position 0%→100% is seamless
  // At 0%: shows first full cycle; at 100% (offset = 1×element): shows second full cycle
  // (identical visual pattern) so the loop restarts invisibly.
  const loopGradient = `linear-gradient(90deg, ${[...palette, ...palette, palette[0]].join(", ")})`;
  root.setProperty("--dan-gradient-anim", loopGradient);
  root.setProperty("--line-color", lineColor);
  root.setProperty("--dan-primary", `rgb(${primary.join(",")})`);
  root.setProperty("--dan-secondary", `rgb(${secondary.join(",")})`);
  root.setProperty("--dan-primary-raw", primary.join(","));
  root.setProperty("--dan-secondary-raw", secondary.join(","));
  root.setProperty("--dan-glow", `rgba(${primary.join(",")}, 0.45)`);
  root.setProperty("--dan-border", `rgba(${primary.join(",")}, 0.35)`);
  root.setProperty("--dan-bg-tint", `rgba(${primary.join(",")}, 0.08)`);
  
  const midRGB = parseRGB(lineColor);
  const solidColor = midRGB.map(c => Math.min(255, Math.round(c * 1.3)));
  root.setProperty("--dan-solid", `rgb(${solidColor.join(",")})`);
  vizPrimary = `rgb(${primary.join(",")})`;
  vizSecondary = `rgb(${secondary.join(",")})`;
  vizGradient = null;

  // ── Skin 4/5/6 dynamic elements ──────────────────────────────────
  // SVG ring gradient stops (ui-4 Vertical Monolith)
  const ringStop1 = document.getElementById("p1-stop-1");
  const ringStop2 = document.getElementById("p1-stop-2");
  if (ringStop1) ringStop1.setAttribute("stop-color", `rgb(${primary.join(",")})`);
  if (ringStop2) ringStop2.setAttribute("stop-color", `rgb(${secondary.join(",")})`);

  // Update ring fill glow
  const ringFill = document.getElementById("intensityFill");
  if (ringFill && ringFill.tagName === "circle") {
    ringFill.style.filter = `drop-shadow(0 0 15px rgba(${primary.join(",")}, 0.8))`;
  }

  // Colored sub-bars for skins 4/5/6 — progressive lighting based on DP fraction
  // Thresholds match the sublevel text labels (Low/Mid-Low/Mid/Mid-High/High)
  const subBarSelectors = [".p1-bar", ".p2-sbar", ".p3-sbar", ".sbar"];
  const dp = Number(result.dp || 0);
  const dpFrac = dp - Math.floor(dp);
  let subCount = 1;                       // Low:      dpFrac <= 0.20 → 1 bar
  if (dpFrac > 0.80) subCount = 5;        // High:     dpFrac > 0.80  → 5 bars
  else if (dpFrac > 0.60) subCount = 4;   // Mid-High: dpFrac > 0.60  → 4 bars
  else if (dpFrac > 0.40) subCount = 3;   // Mid:      dpFrac > 0.40  → 3 bars
  else if (dpFrac > 0.20) subCount = 2;   // Mid-Low:  dpFrac > 0.20  → 2 bars

  let subBarColor = primary;
  if (relativeLuminance(primary) < 0.15) {
    let maxLum = -1;
    let brightest = primary;
    palette.forEach(cStr => {
      const rgb = parseRGB(cStr);
      const lum = relativeLuminance(rgb);
      if (lum > maxLum) {
        maxLum = lum;
        brightest = rgb;
      }
    });
    subBarColor = brightest;
  }

  subBarSelectors.forEach(selector => {
    document.querySelectorAll(selector).forEach((bar, idx) => {
      if (idx < subCount) {
        bar.style.backgroundColor = `rgb(${subBarColor.join(",")})`;
        bar.style.boxShadow = `0 0 15px rgba(${subBarColor.join(",")}, 0.8)`;
      } else {
        if (_settings.skin === "6" && _settings.ui6_simple_mode) {
          bar.style.backgroundColor = "rgba(0,0,0,0.6)";
        } else {
          bar.style.backgroundColor = "rgba(255,255,255,0.08)";
        }
        bar.style.boxShadow = "none";
      }
    });
  });

  // Skin 5 (Broadcast Bar) — left panel gradient background
  const leftPanel = document.querySelector(".left-panel");
  if (leftPanel) {
    leftPanel.style.background = `linear-gradient(135deg, rgb(${primary.join(",")}), rgb(${secondary.join(",")}))`;
  }


  // Toggle dark-dan mode for ticker readability
  const overlay = document.getElementById("overlay");
  if (isDark) {
    overlay.classList.add("dan-dark");
    root.setProperty("--ticker-bg", "rgba(200, 210, 230, 0.18)");
  } else {
    overlay.classList.remove("dan-dark");
    root.setProperty("--ticker-bg", "var(--bg-panel-alt)");
  }

  ui.panel.classList.remove("is-loading");

  // Trigger sweep-reveal animation on new data
  ui.panel.classList.remove("revealing");
  void ui.panel.offsetWidth;
  ui.panel.classList.add("revealing");
  ui.panel.addEventListener("animationend", () => {
    ui.panel.classList.remove("revealing");
  }, { once: true });

  setAnimatedText(ui.badgeLeft, "PRONOSTICO");
  setAnimatedText(ui.badgeCenter, "DAN OVERLAY");
  setAnimatedText(ui.badgeRight, result.chart || "LIVE");

  const stageMap = { "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10 };
  const _sigImgBase = (_CURRENT_SKIN !== "1") ? "../" : "";
  const useTextOnly = (_CURRENT_SKIN === "3" || _CURRENT_SKIN === "4" || _CURRENT_SKIN === "5");
  if (result.signicialMode && stageMap[result.signicialStage] && !useTextOnly) {
    if (ui.danImage) {
      ui.danImage.style.display = "block";
      ui.danImage.src = `${_sigImgBase}signicial_images/Stage${stageMap[result.signicialStage]}icon.png`;
    }
    if (ui.danName) ui.danName.style.display = "none";
  } else {
    if (ui.danImage) ui.danImage.style.display = "none";
    if (ui.danName) {
      ui.danName.style.display = "";
      setAnimatedText(ui.danName, result.danName);
    }
  }
  setAnimatedText(ui.danSub, result.danSuffix || "-");
  ui.danSub?.classList.toggle("is-beyond", result.danSuffix === "Beyond");

  if (ui.chartFamily) {
    const famText = result.chart || "";
    const famColor = (result.chartColor || famText).toUpperCase();
    ui.chartFamily.textContent = famText;
    ui.chartFamily.setAttribute("data-family", famColor);
  }

  if ("metrics" in result) {
    setOptionalText(ui.metrics, result.metrics);
  }
  if ("details" in result) {
    setOptionalText(ui.details, result.details);
  }
  if ("bands" in result) {
    setOptionalText(ui.bands, result.bands);
  }

  // Background image: Celestial tier PNG, Reform greek letter, or hidden for Signicial/Shoegazer
  // Paths are relative to the HTML document: sub-skins (ui-2/, ui-3/) need ../ prefix.
  const _imgBase = (_CURRENT_SKIN !== "1") ? "../" : "";
  if (ui.danGreekBg) {
    if (result.celestialMode) {
      const celFile = CELESTIAL_PNG[result.celestialTier || ""];
      ui.danGreekBg.src = celFile ? `${_imgBase}celestial_images/${celFile}.png` : "";
      ui.danGreekBg.style.opacity = celFile ? "" : "0";
    } else if (result.signicialMode) {
      const sigFile = SIGNICIAL_PNG[result.signicialStage || ""];
      ui.danGreekBg.src = sigFile ? `${_imgBase}signicial_images/${sigFile}.png` : "";
      ui.danGreekBg.style.opacity = sigFile ? "" : "0";
    } else if (result.shoegazerMode || result.lnCourseMode) {
      ui.danGreekBg.src = "";
      ui.danGreekBg.style.opacity = "0";
    } else {
      const greekFile = GREEK_PNG[result.danShort || ""];
      ui.danGreekBg.src = greekFile ? `${_imgBase}images/${greekFile}.png` : "";
      ui.danGreekBg.style.opacity = greekFile ? "" : "0";
    }
  }

  // Toggle class so CSS can shrink the name for long Celestial tier words
  if (ui.danName) ui.danName.classList.toggle("is-celestial", !!result.celestialMode);

  // DP tooltip + intensity bar — hidden in Shoegazer mode
  if (result.shoegazerMode) {
    if (ui.dpTooltip) { ui.dpTooltip.textContent = ""; }
    if (ui.danDpRow) { ui.danDpRow.style.display = "none"; }
    if (ui.intensityBar) { ui.intensityBar.style.display = "none"; }
  } else {
    if (ui.intensityBar) { ui.intensityBar.style.display = ""; }
    if (ui.danDpRow) { ui.danDpRow.style.display = ""; }
    if (ui.dpTooltip) {
      const dpVal = typeof result.dp === "number" ? result.dp : 0;
      ui.dpTooltip.textContent = dpVal > 0 ? `DP ${dpVal.toFixed(2)}` : "";
    }
    if (ui.danDpValue) {
      const dpVal = typeof result.dp === "number" ? result.dp : 0;
      if (dpVal > 0 && ui.danDpDec) {
        // Split DP into integer + decimal for skins 4/5/6
        const parts = dpVal.toFixed(2).split(".");
        ui.danDpValue.textContent = parts[0];
        ui.danDpDec.textContent = "." + parts[1];
      } else if (dpVal > 0) {
        ui.danDpValue.textContent = dpVal.toFixed(2);
      } else {
        ui.danDpValue.textContent = "--";
        if (ui.danDpDec) ui.danDpDec.textContent = "";
      }
    }
    // SVG ring (ui-4 Monolith): update always — ring has no intensityThumb element
    if (ui.intensityFill && ui.intensityFill.tagName.toLowerCase() === "circle") {
      const dpVal = typeof result.dp === "number" ? result.dp : 0;
      const frac = dpVal > 0 ? Math.min(1, Math.max(0, dpVal - Math.floor(dpVal))) : 0;
      const circumference = 816.8; // 2π × 130
      ui.intensityFill.style.strokeDashoffset = String(circumference - frac * circumference);
    }
    // Div-based intensity bar + thumb (skins 1/2/3/5/6)
    if (ui.intensityThumb) {
      const dpVal = typeof result.dp === "number" ? result.dp : 0;
      const frac = dpVal > 0 ? Math.min(1, Math.max(0, dpVal - Math.floor(dpVal))) : 0;
      const pct = `${frac * 100}%`;
      ui.intensityThumb.style.left = pct;
      if (ui.intensityFill && ui.intensityFill.tagName.toLowerCase() !== "circle") {
        ui.intensityFill.style.width = pct;
      }
    }
  }

}


function applyLoading(message = "Computing") {
  if (!isMapTransitioning) {
    ui.panel.classList.add("is-loading");
  } else {
    ui.panel.classList.remove("is-loading");
  }
  const overlayEl = document.getElementById("overlay");
  if (overlayEl) {
    overlayEl.classList.add("computing-mode");
    const root = document.documentElement;
    root.style.setProperty("--star-bg", "rgb(45, 45, 45)");
    root.style.setProperty("--star-text", "#ffffff");
    root.style.setProperty("--star-accent", "rgb(140, 140, 140)");
    root.style.setProperty("--c1", "#555555");
    root.style.setProperty("--c2", "#333333");
    _startSunnyDotsAnimation();
    _startSkin8DotsAnimation();
    const uiContent = document.getElementById("ui-content");
    if (uiContent) {
      uiContent.classList.remove("glitch-active");
      void uiContent.offsetWidth;
      uiContent.classList.add("glitch-active");
    }
  }
  setChartButtonReady(false);
  setAnimatedText(ui.badgeLeft, "SYNC");
  setAnimatedText(ui.badgeCenter, "DAN OVERLAY");
  setAnimatedText(ui.badgeRight, "WAIT");
  if (ui.chartFamily) { ui.chartFamily.textContent = ""; ui.chartFamily.removeAttribute("data-family"); }
  if (ui.modBadge) ui.modBadge.classList.remove("recalculating");
  setAnimatedText(ui.loadingText, message.replace(/\.+$/, "") || "Computing");
  if (ui.density) {
    ui.density.innerHTML = "";
    ui.density.classList.remove("has-data");
  }
}

// ── MSD Skill Bars ────────────────────────────────────────────────────
const MSD_ROLE_LABELS = {
  stream: "STREAM",
  jumpstream: "JS",
  handstream: "HS",
  stamina: "STAM",
  jackspeed: "JACK",
  chordjack: "CJ",
  technical: "TECH",
};

function renderMsdBars(estimates, overallMsd) {
  if (!ui.density) return;

  const entries = Object.entries(estimates || {})
    .filter(([, v]) => Number(v) > 0)
    .sort((a, b) => Number(b[1]) - Number(a[1]))
    .slice(0, 4);

  if (!entries.length || !overallMsd) {
    ui.density.innerHTML = "";
    ui.density.classList.remove("has-data");
    return;
  }

  const maxVal = Number(entries[0][1]) || 1;
  ui.density.innerHTML = entries.map(([key, val]) => {
    const v = Number(val);
    const pct = Math.min(100, (v / maxVal) * 100).toFixed(1);
    const lbl = MSD_ROLE_LABELS[key] || key.toUpperCase().slice(0, 5);
    return `<div class="msd-row">` +
      `<span class="msd-label">${lbl}</span>` +
      `<div class="msd-track"><div class="msd-fill" style="width:${pct}%"></div></div>` +
      `<span class="msd-val">${v.toFixed(1)}</span>` +
      `</div>`;
  }).join("");
  ui.density.classList.add("has-data");
}

function findDanOverlay(payload) {
  if (!payload || typeof payload !== "object") {
    return "";
  }

  const directCandidates = [
    payload.danOverlay,
    safeGet(payload, "overlay.danOverlay"),
    safeGet(payload, "menu.danOverlay"),
    safeGet(payload, "gameplay.danOverlay"),
    safeGet(payload, "results.danOverlay")
  ];

  for (const candidate of directCandidates) {
    if (typeof candidate === "string" && candidate.trim()) {
      return candidate;
    }
  }

  return "";
}

// Fades the BG out, waits for the image to load AND the fade to finish,
// then sets the new image and fades it back in. On rapid map changes only
// the latest generation actually reveals — stale ones are discarded.
function crossfadeBackground(url) {
  // In green-screen mode the background is always #00ff00 — skip image loads.
  if (_settings.greenScreen) return;

  const gen = ++_bgGeneration;
  const bg = ui.bg;

  // Kick off the fade-out. If the element is already at opacity 0 (initial
  // boot state), skip the 520ms wait — there is nothing to fade out, and
  // the delay creates a race window where an incoming "no background" clear
  // increments _bgGeneration and silently cancels this crossfade.
  const alreadyHidden = !bg.style.opacity || bg.style.opacity === "0";
  bg.style.opacity = "0";

  const imagePromise = new Promise((resolve) => {
    const img = new Image();
    img.onload = img.onerror = () => resolve();
    img.src = url;
  });

  // Wait at least as long as the CSS fade-out transition (500ms), but skip
  // that wait entirely if there was nothing visible to fade out.
  const fadePromise = alreadyHidden
    ? Promise.resolve()
    : new Promise((resolve) => setTimeout(resolve, 520));

  Promise.all([imagePromise, fadePromise]).then(() => {
    if (gen !== _bgGeneration) return; // superseded by a newer map change
    bg.style.backgroundImage = `url("${url}")`;
    // rAF ensures the browser has committed the image change at opacity:0
    // before we trigger the fade-in transition
    requestAnimationFrame(() => {
      if (gen === _bgGeneration) bg.style.opacity = "1";
    });
  });
}

function resolveBackgroundUrl(payload) {
  // Use tosu's built-in HTTP endpoint to serve the beatmap background.
  // This avoids all issues with file:/// URLs, special characters in paths,
  // and browser security restrictions.
  const bgRaw = safeGet(payload, "menu.bm.path.bg", "");
  if (!bgRaw || !String(bgRaw).trim()) {
    return "";
  }

  // tosu serves the current beatmap's background image at this endpoint
  return "http://localhost:24050/files/beatmap/background";
}

function applyProgressData(payload) {
  if (!ui.progressWrap) return;

  const { currentMs, fullMs: rawFullMs, state, playing } = extractTimeState(payload);
  const fullMs = rawFullMs > 0 ? rawFullMs : currentTotalMs;

  if (fullMs > 0 || currentMs > 0) {
    renderMapDuration(currentMs, fullMs, playing || currentMs > 0);
  }

  if (!fullMs) {
    if (!ui.progressWrap.classList.contains("finished")) {
      ui.progressWrap.classList.remove("showing", "paused");
    }
    return;
  }

  // Track accuracy during gameplay. When on results screen (state 7) also read
  // resultsScreen.accuracy which is the definitive final value.
  if (state === 2) {
    const gAcc = payload.gameplay_accuracy;
    if (gAcc != null && Number.isFinite(Number(gAcc))) {
      const normalized = Number(gAcc);
      // Ignore values that are exactly 1.0 (100 %) — tosu sometimes sends
      // this as a default/placeholder at the start of a play, and it's not
      // a real accuracy reading.  Wait for the results screen instead.
      if (normalized !== 1.0) {
        prog_lastAcc = normalized;
      }
    } else {
      const fallback = Number(safeGet(payload, "gameplay.accuracy", 0));
      if (fallback !== 1.0 && Number.isFinite(fallback)) {
        prog_lastAcc = fallback;
      }
    }
  } else if (state === 7) {
    // Only update from results screen if we don't have a real accuracy
    // value from gameplay (e.g. tosu sent placeholder 1.0 which we skipped,
    // or no accuracy was received at all).
    const trackedDuringPlay = prog_lastAcc > 0 && prog_lastAcc < 1.0;
    if (!trackedDuringPlay) {
      const rAcc = payload.results_accuracy ?? payload.gameplay_accuracy;
      if (rAcc != null && Number.isFinite(Number(rAcc))) {
        prog_lastAcc = Number(rAcc);
      } else {
        const resultAcc = Number(safeGet(payload, "resultsScreen.accuracy", -1));
        if (resultAcc >= 0) {
          prog_lastAcc = resultAcc;
        }
      }
    }
  }

  // ── Stall-based in-game pause detection ─────────────────────────
  // tosu keeps game_state=2 while the player is in the pause menu;
  // the only observable signal is that currentMs stops advancing.
  if (currentMs !== prog_lastSeenMs) {
    prog_lastSeenMs = currentMs;
    prog_playingAt = performance.now();
  }
  const isStalled = state === 2
    && prog_wasPlaying
    && currentMs > 0
    && (performance.now() - prog_playingAt) > PAUSE_STALL_MS;

  const isPlaying = playing && !isStalled;

  if (isPlaying) {
    clearTimeout(prog_finishTimeout);
    if (!prog_wasPlaying) {
      prog_wasPlaying = true;
      prog_lastAcc = 0; // Reset accuracy at the start of a new play
    }
    prog_lastMs = currentMs;
    // Resume from pause → hide the paused overlay
    if (prog_isPaused) {
      prog_isPaused = false;
      if (ui.pausedOverlay) ui.pausedOverlay.classList.remove("is-visible");
    }
    // During active play: no overlay — drain bar + timer show progress
    if (!ui.progressWrap.classList.contains("finished")) {
      ui.progressWrap.classList.remove("showing", "paused");
    }
  } else if (isStalled) {
    // Player paused mid-song!
    // Since they are still in the session, we DO NOT set prog_wasPlaying to false.
    prog_isPaused = true;
    if (ui.pausedOverlay) ui.pausedOverlay.classList.add("is-visible");
    ui.progressWrap.classList.remove("showing", "finished");
    ui.progressResult.classList.remove("failed");
  } else {
    // Not playing and not stalled -> Game exited, finished, or failed
    if (prog_wasPlaying) {
      prog_wasPlaying = false;
      const remainingMs = Math.max(0, fullMs - currentMs);
      const isFinished = (state === 7 || remainingMs <= 1000);
      const isFailed = (state === 3);

      if (isFinished || isFailed) {
        prog_isPaused = false;
        if (ui.pausedOverlay) ui.pausedOverlay.classList.remove("is-visible");
        let resultText = "Pass!";
        let resultColor = "#b7c8e6";

        ui.progressResult.classList.remove("failed");

        if (isFailed) {
          resultText = "FAILED!";
          resultColor = "#ff3333";
          ui.progressResult.classList.add("failed");
        } else {
          // Normalise: tosu sometimes sends accuracy as fraction (0.00-1.00)
          // and sometimes as percentage (0.00-100.00).
          let acc = prog_lastAcc;
          if (acc > 1 && acc <= 100) {
            // already a percentage
          } else if (acc > 0 && acc <= 1) {
            acc *= 100;   // fraction -> percentage
          } else {
            acc = 0;      // invalid / unset -> fall back to "Pass!"
          }

          if (acc >= 100) {
            resultText = "Perfect!";
            resultColor = "#ffeb3b";
          } else if (acc >= 98) {
            resultText = "Hard Clear!";
            resultColor = "#ff9800";
          } else if (acc >= 97) {
            resultText = "Over Clear!";
            resultColor = "#4caf50";
          } else if (acc >= 96) {
            resultText = "Clear!";
            resultColor = "#8bc34a";
          }
        }

        ui.progressResult.innerText = resultText;
        ui.progressResult.style.color = resultColor;

        ui.progressWrap.classList.remove("paused");
        ui.progressWrap.classList.add("finished");
        ui.progressWrap.classList.add("showing");

        prog_finishTimeout = setTimeout(() => {
          ui.progressWrap.classList.remove("showing");
          setTimeout(() => ui.progressResult.classList.remove("failed"), 1000);
        }, isFailed ? 3000 : 4000);
      } else {
        // Player exited the song (went to menu, edit, etc)
        prog_isPaused = false;
        if (ui.pausedOverlay) ui.pausedOverlay.classList.remove("is-visible");
      }
    } else if (prog_isPaused) {
      // If we left gameplay entirely (menu / edit), clear the paused overlay.
      if (state !== 2) {
        prog_isPaused = false;
        if (ui.pausedOverlay) ui.pausedOverlay.classList.remove("is-visible");
      }
    } else if (!ui.progressWrap.classList.contains("finished")) {
      ui.progressWrap.classList.remove("showing", "paused");
    }
  }

}

function applyBeatmapData(payload) {
  const artist = safeGet(payload, "menu.bm.metadata.artist", "Unknown Artist");
  const title = safeGet(payload, "menu.bm.metadata.title", "Unknown Title");
  // prefer 'version' (same field Python reads) then 'difficulty' as fallback
  const diff = safeGet(payload, "menu.bm.metadata.version",
    safeGet(payload, "menu.bm.metadata.difficulty", "Unknown Diff"));

  // Use md5 as the primary map key — it is unambiguous and always matches the
  // Python bridge key (which also receives md5 from tosu).  Fall back to the
  // string combo only when md5 is absent (e.g. no map loaded).
  const md5 = safeGet(payload, "menu.bm.md5", "");
  const mapKey = md5 || buildMapKey(artist, title, diff);
  if (mapKey !== lastMapKey) {
    lastMapKey = mapKey;
    lastDanRaw = "";
    startMapTransition();
  }

  setTickerText(ui.mapTicker, `${artist} - ${title} [${diff}]`);

  const sr = Number(safeGet(payload, "menu.bm.stats.fullSR", safeGet(payload, "menu.bm.stats.SR", 0)) || 0);
  const od = Number(safeGet(payload, "menu.bm.stats.OD", 0) || 0);
  const hp = Number(safeGet(payload, "menu.bm.stats.HP", 0) || 0);
  const bpmRaw = safeGet(payload, "menu.bm.stats.BPM", null);
  if (bpmRaw && typeof bpmRaw === "object") {
    _cachedBpmRange = bpmRaw; // cache the full range for later
  }
  // tosu sometimes sends a plain number (instantaneous / rate-adjusted BPM)
  // instead of the range object; fall back to the cached range when that happens.
  const bpmForDisplay = (typeof bpmRaw === "number" && _cachedBpmRange) ? _cachedBpmRange : bpmRaw;
  const bpm = bpmToString(bpmForDisplay);
  const currentMs = Number(safeGet(payload, "menu.bm.time.current", 0) || 0);
  const totalMs = Number(safeGet(payload, "menu.bm.time.mp3", safeGet(payload, "menu.bm.time.full", 0)) || 0);
  const duration = msToClock(totalMs);
  const circles = Number(safeGet(payload, "menu.bm.stats.circles", 0) || 0);
  const holds = Number(safeGet(payload, "menu.bm.stats.holds", 0) || 0);
  const total = circles + holds;
  const mapper = safeGet(payload, "menu.bm.metadata.mapper", "-");
  const supportInfo = extractMapSupportInfo(payload);

  const statsLine = [
    `BPM ${bpm}`,
    `TIME ${duration}`,
    `NOTES ${total || "--"}`,
    `LN ${holds || 0}`,
    `OD ${od ? od.toFixed(1) : "--"}`,
    `HP ${hp ? hp.toFixed(1) : "--"}`,
    `MAPPER ${mapper}`
  ].join("   ·   ");

  setTickerText(ui.statsTicker, statsLine);
  setOptionalText(ui.details, `BPM ${bpm} · ${duration} · ${total || "--"} notes · ${holds || 0} LN`);
  setOptionalText(ui.bands, `Mapper ${mapper} · Base SR ${sr ? sr.toFixed(2) : "--"} · OD ${od ? od.toFixed(1) : "--"} · HP ${hp ? hp.toFixed(1) : "--"}`);

  // Populate compact-bar left column and right duration
  let titleText = `${artist} — ${title}`;
  if (diff && diff !== "Unknown Diff") {
    const dTrim = diff.trim();
    if (dTrim.startsWith("[") && dTrim.endsWith("]")) {
      titleText += ` ${dTrim}`;
    } else {
      titleText += ` [${dTrim}]`;
    }
  }
  setMapTitleText(titleText);
  if (ui.mapArtist) ui.mapArtist.textContent = `Mapped by ${mapper}`;
  if (ui.mapBpm) ui.mapBpm.textContent = bpm ? `${bpm} BPM` : "-- BPM";
  if (ui.mapOd) ui.mapOd.textContent = od ? `OD ${od.toFixed(1)}` : "OD --";
  renderMapDuration(currentMs, totalMs, currentMs > 0);

  const bgUrl = resolveBackgroundUrl(payload);
  if (bgUrl) {
    // Compare against mapKey (not bgUrl) because the tosu endpoint URL is
    // always the same; append a cache-busting timestamp so the browser
    // actually fetches the new image when the map changes.
    if (ui.bg && ui.bg.dataset && ui.bg.dataset.mapKey !== mapKey) {
      ui.bg.dataset.mapKey = mapKey;
      const cacheBust = `${bgUrl}?t=${Date.now()}`;
      crossfadeBackground(cacheBust);
      // when an actual background is shown, mute the panel's own fill so the
      // art comes through more clearly; the scrim will still provide shade.
      ui.panel.style.background = "rgba(7, 14, 26, 0.3)";
    }
  } else {
    // no background available → restore default panel color
    ui.panel.style.background = "var(--bg-panel)";
  }

  return supportInfo;
}

function applyFromPythonBridge(payload) {
  try {
    if (!payload || typeof payload !== "object") {
      return;
    }

    if (payload.type === "bridge-init") {
      bridgeMode = true;
      if (!_pythonBridgeReady) {
        _pythonBridgeReady = true;
        // In bridge mode we KEEP the connect screen visible and show a
        // "Waiting for tosu" spinner. The screen will advance to "Connected"
        // (green check) only when the first real state/data arrives from tosu.
        // This gives the user proper visual feedback instead of a blank overlay.
        if (introStage === "connecting") {
          _showSearching();                     // ensure spinner + download btn visible
          if (connectEl) connectEl.classList.remove("hidden", "fading");
          _startOsuCheck();                     // start polling osu! status
        }
        // Re-load settings from Python file now that the API is reachable.
        _loadSettings().then(() => {
          _applySettings();
          const savedLayout = _settings.layout || "complete";
          if (savedLayout !== _layoutMode) {
            _layoutMode = savedLayout;
            _applyLayoutMode(true);
          }
          // Apply saved window size OR skin defaults safely inside the .then block
          // once the python settings have been loaded and the API is guaranteed ready.
          let w = _settings.windowWidth;
          let h = _settings.windowHeight;
          const isLegacyDefault = (w === 700 && h === 320) || (w === 860 && h === 320);
          if (isLegacyDefault && (_CURRENT_SKIN === "4" || _CURRENT_SKIN === "5" || _CURRENT_SKIN === "6" || _CURRENT_SKIN === "8")) {
            w = null;
            h = null;
          }
          if (_CURRENT_SKIN === "4") {
            document.documentElement.style.zoom = 0.61;
          } else if (_CURRENT_SKIN === "5") {
            document.documentElement.style.zoom = 0.75;
          } else if (_CURRENT_SKIN === "6") {
            document.documentElement.style.zoom = 0.73;
          } else if (_CURRENT_SKIN === "8") {
            document.documentElement.style.zoom = 0.94;
          }
          if (w && h && window.pywebview?.api?.set_window_size) {
            window.pywebview.api.set_window_size(w, h);
          } else if (!w && !h && window.pywebview?.api?.set_window_size) {
            if (_CURRENT_SKIN === "4") {
              window.pywebview.api.set_window_size(284, 335);
            } else if (_CURRENT_SKIN === "5") {
              window.pywebview.api.set_window_size(589, 170);
            } else if (_CURRENT_SKIN === "6") {
              window.pywebview.api.set_window_size(645, 211);
            } else if (_CURRENT_SKIN === "8") {
              window.pywebview.api.set_window_size(594, 234);
            } else {
              window.pywebview.api.set_window_size(700, 320);
            }
          }
        });
      }
      return;
    }

    if (payload.type === "notification") {
      showToast(payload.message || "Done", 3500);
      setChartDone();
      return;
    }

    if (payload.type === "visualizer") {
      vizActive = !!payload.active;
      if (payload.bands && Array.isArray(payload.bands)) {
        for (let i = 0; i < vizTarget.length; i++) {
          vizTarget[i] = payload.bands[i] || 0;
        }
      }
      if (!vizActive) vizTarget.fill(0);
      return;
    }

    // When real tosu data arrives while still on the connect screen in bridge
    // mode, we record that tosu is connected and check if osu! is also running.
    if (_pythonBridgeReady && introStage === "connecting") {
      const incomingState = (payload.type === "state") ? (payload.state || "") : "";
      // Only advance on real connection — not on waiting_tosu state
      const isRealData = payload.type !== "state" || (incomingState !== "waiting_tosu" && incomingState !== "");
      if (isRealData) {
        _tosuConnected = true;
      } else if (incomingState === "waiting_tosu") {
        _tosuConnected = false;
      }
      _checkAndAdvanceConnection();
    }

    // ── Overlay state changes (waiting_tosu, analyzing, ready, error) ──
    if (payload.type === "state") {
      const state = payload.state || "";
      const msg = payload.message || "";
      if (state === "analyzing") {
        if (isMapTransitioning) {
          setAnimatedText(ui.loadingText, msg || "Computing");
        } else if (lastDanRaw) {
          // Mod change on already-analyzed map: keep display, show pulse on badge
          if (ui.modBadge) ui.modBadge.classList.add("recalculating");
        } else {
          applyLoading(msg || "Computing");
        }
      } else if (state === "idle") {
        if (!lastDanRaw && !isMapTransitioning) {
          applyLoading(msg || "Waiting for a map");
        }
      } else if (state === "waiting_tosu") {
        finishMapTransition();
        applyLoading(msg || "Waiting for tosu...");
        // If we were past the connect screen and tosu dropped, go back to searching
        if (introStage === "done" || introStage === "hint") {
          // Don't re-show the full connect screen mid-session; just update the loading text
        }
      } else if (state === "error") {
        finishMapTransition();
        applyLoading(msg || "Error");
      }
      // "idle" and "ready" don't change the display (ready comes via "analysis")
      return;
    }

    // ── Map metadata (ticker update) ─────────────────────────────────
    if (payload.type === "map_info") {
      lastDanRaw = "";
      // Use md5 as primary key so this always agrees with applyBeatmapData
      const mapKey = payload.md5 || buildMapKey(payload.artist, payload.title, payload.version);
      if (mapKey !== lastMapKey) {
        lastMapKey = mapKey;
        startMapTransition();
      }
      const mapText = [
        payload.artist, payload.title, payload.version, payload.mapper
      ].filter(Boolean).join(" — ") || "Waiting for beatmap...";
      setTickerText(ui.mapTicker, mapText);
      // Update compact-bar left column
      let titleLine = [payload.artist, payload.title].filter(Boolean).join(" — ") || "Waiting for beatmap...";
      if (payload.version) {
        const vTrim = payload.version.trim();
        if (vTrim.startsWith("[") && vTrim.endsWith("]")) {
          titleLine += ` ${vTrim}`;
        } else {
          titleLine += ` [${vTrim}]`;
        }
      }
      setMapTitleText(titleLine);
      if (ui.mapArtist && payload.mapper) ui.mapArtist.textContent = `Mapped by ${payload.mapper}`;
      renderMapDuration(Number(payload.current_ms || 0), Number(payload.total_ms || 0), Number(payload.current_ms || 0) > 0);
      if (ui.modBadge) {
        const modLbl = String(payload.mod_label || "");
        ui.modBadge.textContent = modLbl;
        ui.modBadge.dataset.mod = modLbl;
        ui.modBadge.classList.remove("recalculating");
      }
      // Load beatmap background. Primary path: base64 data URI (avoids
      // file:// mixed-content issues). Fallback: tosu HTTP endpoint when the
      // file was too large to inline (has_bg=true but bg_data empty).
      if (payload.bg_data && mapKey && ui.bg.dataset.mapKey !== mapKey) {
        ui.bg.dataset.mapKey = mapKey;
        crossfadeBackground(payload.bg_data);
        ui.panel.style.background = "rgba(7, 14, 26, 0.3)";
      } else if (!payload.bg_data && payload.has_bg && mapKey && ui.bg.dataset.mapKey !== mapKey) {
        // File existed but was too large — load via tosu's local HTTP endpoint.
        ui.bg.dataset.mapKey = mapKey;
        crossfadeBackground(`http://localhost:24050/files/beatmap/background?t=${Date.now()}`);
        ui.panel.style.background = "rgba(7, 14, 26, 0.3)";
      } else if (!payload.bg_data && !payload.has_bg && ui.bg.dataset.mapKey) {
        // Map genuinely has no background art — clear the old image.
        ++_bgGeneration;
        ui.bg.dataset.mapKey = "";
        ui.bg.style.opacity = "0";
        const _gen = _bgGeneration;
        setTimeout(() => {
          if (_bgGeneration === _gen) ui.bg.style.backgroundImage = "";
        }, 520);
        ui.panel.style.background = "var(--bg-panel)";
      } else if (!payload.bg_data && !payload.has_bg) {
        ui.panel.style.background = "var(--bg-panel)";
      }
      return;
    }

    // ── Music time (progress bar) ────────────────────────────────────
    if (payload.type === "music_time") {
      applyProgressData(payload);
      _updateDensityProgress(payload.ms || 0);
      return;
    }

    // ── Structured analysis result ───────────────────────────────────
    if (payload.type === "analysis") {
      // LN auto-override: activate/deactivate based on pipeline ln_route.
      // When _lnModePinned is true the user pressed Ctrl+5 to prefer LN Course;
      // still respect whether the map actually has LN Course data — if the
      // pipeline returns rice (ln_course == null) the badge must show the rice
      // mode so the display matches what is actually being scored.
      const lnRoute = String(payload.ln_route || "rice");
      const wasLn = _lnOverrideActive;
      _lnOverrideActive = (lnRoute === "ln" && payload.ln_course != null);
      if (_lnOverrideActive !== wasLn) {
        _updateScoringModeBadge();
        if (_lnOverrideActive) {
          showModeAnnounce(_lnModePinned ? "LN Course \u25C8" : "LN Course", "ln_course");
        } else {
          // Reverted to rice mode — announce the user's preferred mode
          const restoreName = _scoringMode === "celestial" ? "Celestial"
            : _scoringMode === "signicial" ? "Signicial"
              : _scoringMode === "shoegazer" ? "Shoegazer"
                : "Reform";
          showModeAnnounce(restoreName, _scoringMode);
        }
      }
      _lastAnalysisPayload = payload;
      _renderAnalysisPayload(payload);
      setChartButtonReady(true);
      // ── Density graph (ui-3 skin) ───────────────────────────────────
      if (payload.strain_graph && payload.strain_graph.values) {
        _storeStrainData(payload.strain_graph, payload.duration_s || 0);
      }
      // Populate BPM / OD / SR spans from pipeline-parsed .osu stats
      if (ui.mapBpm) {
        const bMin = payload.bpm_min || 0;
        const bMax = payload.bpm_max || 0;
        const bCommon = payload.bpm_common || Math.round(payload.bpm || 0);
        const bpmStr = bpmToString({ min: bMin || bCommon, max: bMax || bCommon, common: bCommon });
        ui.mapBpm.textContent = bpmStr ? `${bpmStr} BPM` : "-- BPM";
      }
      if (ui.mapOd) ui.mapOd.textContent = (payload.od > 0) ? `OD ${Number(payload.od).toFixed(1)}` : "OD --";
      if (ui.mapSr) ui.mapSr.textContent = (payload.osu_sr > 0) ? `${Number(payload.osu_sr).toFixed(2)}★` : "--★";
      return;
    }
  } catch (err) {
    finishMapTransition();
    applyLoading(`Bridge error: ${err && err.message ? err.message : err}`);
    showToast(`Bridge error: ${err && err.message ? err.message : err}`, 5000);
  }

  // ── Legacy structured DP result (backwards compat) ────────────────
  if (payload.type === "dan_result") {
    const dp = Number(payload.dp || 0);
    const label = String(payload.label || "Unknown");
    const subLabel = String(payload.sub_label || "");
    const chart = String(payload.chart_type || "PATTERN").toUpperCase();
    const mod = payload.mod ? `[${payload.mod}]` : "";
    const sr = Number(payload.sunny_sr || 0);
    const nps = Number(payload.nps || 0);
    const peak = Number(payload.peak_nps || 0);

    lastDanRaw = `Est. Dan: ${label}${subLabel ? ` · ${subLabel}` : ""}`;
    applyDanResult({
      danName: label,
      danSuffix: subLabel || "-",
      metrics: sr > 0 ? sr.toFixed(2) : nps > 0 ? nps.toFixed(1) : "--.-",
      details: `Chart: ${chart} · DP: ${dp.toFixed(2)} / 20`,
      bands: `${mod ? `${mod} · ` : ""}Low ━━━ Mid ━━━ High`,
      density: "",
      chart: chart,
    });
    return;
  }

  // ── Export Chart Rendering ───────────────────────────────────────────────
  if (payload.type === "render_export_chart") {
    renderExportChart(payload);
    return;
  }

  // ── Legacy text payloads (backwards compat with old observer) ─────
  if (payload.type !== "text") {
    return;
  }

  if (payload.target === "map") {
    lastDanRaw = "";
    setTickerText(ui.mapTicker, payload.value || "Waiting for beatmap...");
    setMapTitleText(payload.value || "Waiting for beatmap...");
    return;
  }

  if (payload.target === "stats") {
    setTickerText(ui.statsTicker, payload.value || "No stats available");
    return;
  }

  if (payload.target === "dan") {
    const raw = String(payload.value || "");
    if (raw.trim().startsWith("Est. Dan:")) {
      lastDanRaw = raw;
      const parsed = parseDanOverlay(raw);
      if (parsed) {
        applyDanResult(parsed);
      }
      return;
    }

    if (!lastDanRaw) {
      applyLoading(raw || "Computing");
    }
  }
}

// (old renderExportChart removed — see bottom of file for current version)

// Expose the Python bridge callback as soon as the script loads so startup
// events that arrive before boot() do not kill the bridge.
window.__overlayFromPython = applyFromPythonBridge;

function connect() {
  clearTimeout(reconnectTimer);

  try {
    ws = new WebSocket(WS_URL);
  } catch (_err) {
    scheduleReconnect();
    return;
  }

  ws.addEventListener("open", () => {
    if (introStage === "splash" || introStage === "tutorial_prompt" ||
      introStage === "whats_new" || introStage === "hint" || introStage === "hint2" ||
      introStage === "hint3" || introStage === "hint4" || introStage === "hint_settings" || introStage === "hint_settings") {
      _wsOpenedEarly = true;              // intro screens will skip connecting on exit
    } else if (introStage === "connecting") {
      setIntroStage("connected");
    } else if (!_pythonBridgeReady) {
      // Only update display on reconnect when Python bridge isn't the real source.
      // In bridge mode the WS is used by Python-side; JS side silently reconnects.
      applyLoading("Computing");
    }
  });

  ws.addEventListener("message", (event) => {
    let payload;
    try {
      payload = JSON.parse(event.data);
    } catch (_err) {
      return;
    }

    const supportInfo = applyBeatmapData(payload);
    if (!supportInfo.supported) {
      lastDanRaw = "";
      applyUnsupportedMapWarning(supportInfo);
      return;
    }

    applyProgressData(payload);

    // In bridge mode the Python pipeline is the authoritative dan source.
    // The `danOverlay` field in tosu's JSON belongs to a DIFFERENT overlay
    // (e.g. ManiaMapAnalyser) installed in tosu; honouring it here would
    // overwrite our correct result with theirs.  Skip it entirely.
    const danRaw = _pythonBridgeReady ? "" : findDanOverlay(payload);
    if (danRaw) {
      // remember what we got so later updates without the property don't
      // overwrite the result with a loading state.
      lastDanRaw = danRaw;

      const parsed = parseDanOverlay(danRaw);
      if (parsed) {
        applyDanResult(parsed);
        return;
      }
    }

    // only show a loading state if we haven't received any dan result yet; once
    // we have one we keep showing it until the map changes (handled above).
    if (!lastDanRaw && !isMapTransitioning) {
      const menuState = Number(safeGet(payload, "menu.state", 0));
      const loadingText = menuState === 2 ? "Playing" : "Computing";
      applyLoading(loadingText);
    }
  });

  ws.addEventListener("close", () => {
    _wsOpenedEarly = false;
    if (introStage === "done") {
      if (!_pythonBridgeReady) {
        // Only show reconnecting screen when Python bridge isn't handling the data.
        finishMapTransition();
        applyLoading("Reconnecting");
      }
      scheduleReconnect();
    } else if (introStage === "hint" || introStage === "hint2" ||
      introStage === "hint3" || introStage === "hint4" || introStage === "hint_settings" ||
      introStage === "whats_new" || introStage === "tutorial_prompt") {
      // WS dropped while intro screen is showing — keep the screen, just retry in background
      scheduleReconnect();
    } else {
      // Dropped during intro (splash/connecting/connected)
      if (_pythonBridgeReady) {
        // Python bridge is the real data source — never reset the intro state machine.
        // Just retry WS silently in background.
        scheduleReconnect();
      } else {
        if (introStage === "connecting" || introStage === "connected") {
          setIntroStage("connecting");
        }
        scheduleReconnect();
      }
    }
  });

  ws.addEventListener("error", () => {
    if (introStage === "done") {
      if (!_pythonBridgeReady) {
        finishMapTransition();
        applyLoading("tosu offline");
      }
    }
    // In intro stages the close event fires next and handles reconnect
  });
}

function scheduleReconnect() {
  clearTimeout(reconnectTimer);
  reconnectTimer = setTimeout(connect, 1300);
}

/* ── Toast notification ──────────────────────────────────────────── */

let toastTimer = null;

function showToast(message, duration = 3000) {
  if (!ui.toast) return;
  ui.toast.textContent = message;
  ui.toast.classList.add("visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    ui.toast.classList.remove("visible");
  }, duration);
}

let _modeAnnounceTimer = 0;
function showModeAnnounce(displayName, modeKey) {
  const el = document.getElementById("modeAnnounce");
  if (!el) return;
  const nameEl = document.getElementById("modeAnnounceName");
  if (nameEl) nameEl.textContent = displayName;
  el.dataset.mode = modeKey;
  el.classList.remove("is-visible");
  void el.offsetWidth; // force reflow to restart animation
  el.classList.add("is-visible");
  clearTimeout(_modeAnnounceTimer);
  _modeAnnounceTimer = setTimeout(() => el.classList.remove("is-visible"), 1600);
}

/* ── Chart generation button ────────────────────────────────────── */

let chartGenerating = false;

// G key — generate chart PNG
document.addEventListener("keydown", async (e) => {
  if (_cfgIsOpen()) return;
  if (!isKeybind("generate_chart", e)) return;
  console.log("[CHART] G pressed. _chartReady:", _chartReady, "chartGenerating:", chartGenerating, "introStage:", introStage);
  if (chartGenerating || (!_chartReady && introStage === "done")) {
    showToast(chartGenerating ? "Already generating..." : "Waiting for data...", 1800);
    return;
  }
  if (!window.pywebview || !window.pywebview.api ||
    typeof window.pywebview.api.on_generate_chart !== "function") {
    console.log("[CHART] Bridge not available");
    showToast("Bridge not available", 2500);
    return;
  }
  setChartGenerating(true);
  showToast("Generating chart...", 2500);
  try {
    // Python computes the data and pushes renderExportChart() via evaluate_js
    // from a background thread. We just need to trigger the process here.
    const result = await window.pywebview.api.on_generate_chart();
    if (!result || result.status !== "ok") {
      showToast(result?.message || "Error generating chart", 3000);
      setChartGenerating(false);
    }
    // If status is "ok", Python will call renderExportChart() via evaluate_js shortly.
    // renderExportChart handles setChartGenerating(false) and save_chart internally.
  } catch (_err) {
    console.error("[CHART] Error:", _err);
    showToast("Error generating chart: " + (_err.message || _err), 3000);
    setChartGenerating(false);
  }
});
/* ── Intro sequence state machine ───────────────────────────────── */

let introStage = "connecting"; // "connecting" | "connected" | "splash" | "whats_new" | "hint" | "hint2" | "hint3" | "hint4" | "hint_settings" | "tutorial_prompt" | "done"
let _wsOpenedEarly = false;    // WS connected while still in splash
let _pythonBridgeReady = false;  // Python bridge sent bridge-init; never reset by WS events

const _SPLASH_EXIT_MS = 3500;  // fade-out starts this many ms after boot
const _SPLASH_FADE_MS = 700;   // duration of the splash fade
const _HINT_FADE_MS = 500;   // duration of hint fade-out
const _HINT_BTN_DELAY = 3500;  // ms after pressing R before the Next button appears
const _HINT2_BTN_DELAY = 1000;  // ms after first Ctrl+# press before Done appears
const _CONNECTED_HOLD = 1400;  // ms to show "Connected" before advancing

const splashEl = document.getElementById("splashScreen");
const whatsNewEl = document.getElementById("whatsNewScreen");
const hintEl = document.getElementById("hintScreen");
const hintEl2 = document.getElementById("hintScreen2");
const hintEl3 = document.getElementById("hintScreen3");
const hintEl4 = document.getElementById("hintScreen4");
const connectEl = document.getElementById("connectScreen");
const connIcon = document.getElementById("connectIcon");
const connLabel = document.getElementById("connectLabel");
const connSub = document.getElementById("connectSub");

let _osuRunning = false;
let _tosuConnected = false;
let _osuCheckInterval = null;

function _checkAndAdvanceConnection() {
  if (introStage !== "connecting") return;

  if (_tosuConnected && _osuRunning) {
    setIntroStage("connected");
  } else {
    // Update subtext to indicate what we are waiting for
    if (connSub) {
      if (_tosuConnected && !_osuRunning) {
        connSub.textContent = "Tosu connected. Waiting for osu!...";
      } else if (!_tosuConnected && _osuRunning) {
        connSub.textContent = "osu! found. Waiting for tosu...";
      } else {
          connSub.textContent = "Connect tosu and open osu! to start";
      }
    }
  }
}

function _updateOsuStatus() {
  const osuEl = document.getElementById("connectOsu");
  const osuIcon = document.getElementById("connectOsuIcon");
  const osuText = document.getElementById("connectOsuText");
  if (!osuEl) return;
  osuEl.classList.remove("hidden");
  if (_osuRunning) {
    osuEl.classList.add("is-running");
    if (osuText) osuText.textContent = "osu! detected";
  } else {
    osuEl.classList.remove("is-running");
    if (osuText) osuText.textContent = "osu! not found";
  }
}

async function _checkOsuRunning() {
  try {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.check_osu_running) {
      _osuRunning = await window.pywebview.api.check_osu_running();
    } else {
      _osuRunning = false;
    }
  } catch (_e) {
    _osuRunning = false;
  }
  _updateOsuStatus();
  _checkAndAdvanceConnection();
}

function _startOsuCheck() {
  if (_osuCheckInterval) return;
  _checkOsuRunning();
  _osuCheckInterval = setInterval(_checkOsuRunning, 3000);
}

function _stopOsuCheck() {
  if (_osuCheckInterval) {
    clearInterval(_osuCheckInterval);
    _osuCheckInterval = null;
  }
}

function _showSearching() {
  if (connIcon) connIcon.innerHTML = '<div class="conn-ring"></div>';
  if (connLabel) connLabel.textContent = "WAITING FOR CONNECTION";
  if (connLabel) connLabel.style.color = "";   // reset any inline color from connected
  if (connectEl) connectEl.classList.remove("is-connected");
  const dl = document.getElementById("connectDownload");
  // Show download hint after 2 s — gives tosu a moment to connect first
  if (dl) dl.classList.add("hidden");
  setTimeout(() => {
    if (introStage !== "connecting") return;   // already advanced, skip
    if (dl) dl.classList.remove("hidden");
  }, 2000);
  _updateOsuStatus();
  _checkAndAdvanceConnection();
}

function _showConnected() {
  if (connIcon) connIcon.innerHTML = '<div class="conn-check"><svg viewBox="0 0 24 24" fill="none" stroke="rgb(55,220,130)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 12 10 16 18 8"/></svg></div>';
  if (connLabel) connLabel.textContent = "CONNECTED";
  if (connLabel) connLabel.style.color = "rgb(55, 220, 130)";
  if (connSub) connSub.textContent = "Tosu found — starting overlay";
  if (connectEl) connectEl.classList.add("is-connected");
  const dl = document.getElementById("connectDownload");
  if (dl) dl.classList.add("hidden");
  // Keep showing osu status even when connected
  _updateOsuStatus();
}

function setIntroStage(stage) {
  // If leaving an intro-only stage forcibly (e.g. WS drops), hide it immediately.
  if (introStage === "tutorial_prompt" && stage !== "tutorial_prompt") {
    const tutEl = document.getElementById("tutorialPromptScreen");
    if (tutEl) { tutEl.classList.add("hidden"); tutEl.classList.remove("fading"); }
  }
  if (introStage === "whats_new" && stage !== "whats_new") {
    if (whatsNewEl) { whatsNewEl.classList.add("hidden"); whatsNewEl.classList.remove("fading"); }
  }
  if (introStage === "hint" && stage !== "hint") {
    if (hintEl) { hintEl.classList.add("hidden"); hintEl.classList.remove("fading"); }
  }
  if (introStage === "hint2" && stage !== "hint2") {
    if (hintEl2) { hintEl2.classList.add("hidden"); hintEl2.classList.remove("fading"); }
  }
  if (introStage === "hint3" && stage !== "hint3") {
    if (hintEl3) { hintEl3.classList.add("hidden"); hintEl3.classList.remove("fading"); }
  }
  if (introStage === "hint4" && stage !== "hint4") {
    if (hintEl4) { hintEl4.classList.add("hidden"); hintEl4.classList.remove("fading"); }
  }
  if (introStage === "hint_settings" && stage !== "hint_settings") {
    const hintSEl = document.getElementById("hintScreenSettings");
    if (hintSEl) { hintSEl.classList.add("hidden"); hintSEl.classList.remove("fading"); }
  }
  introStage = stage;

  switch (stage) {
    case "splash": {
      // Splash screen was removed. Advance to tutorial_prompt immediately.
      setIntroStage("tutorial_prompt");
      break;
    }

    case "tutorial_prompt": {
      const tutPromptEl = document.getElementById("tutorialPromptScreen");
      if (!tutPromptEl) { setIntroStage("whats_new"); break; }

      // Increment how many times this prompt has been shown
      const tutCount = parseInt(localStorage.getItem("danOverlay_tutCount") || "0", 10);
      localStorage.setItem("danOverlay_tutCount", String(tutCount + 1));

      tutPromptEl.classList.remove("hidden", "fading");

      const yesBtn = document.getElementById("tutYesBtn");
      const noBtn = document.getElementById("tutNoBtn");
      const neverBtn = document.getElementById("tutNeverBtn");

      function _hideTutPrompt(nextStage) {
        if (introStage !== "tutorial_prompt") return;
        if (yesBtn) yesBtn.removeEventListener("click", _onYes);
        if (noBtn) noBtn.removeEventListener("click", _onNo);
        if (neverBtn) neverBtn.removeEventListener("click", _onNever);
        tutPromptEl.classList.add("fading");
        setTimeout(() => {
          tutPromptEl.classList.add("hidden");
          setIntroStage(nextStage);
        }, _HINT_FADE_MS);
      }

      function _onYes() { _hideTutPrompt("whats_new"); }
      function _onNo() { _hideTutPrompt("hint_settings"); }
      function _onNever() {
        _settings.neverShowTutorial = true;
        void _saveSettings();
        _hideTutPrompt("done");
      }

      if (yesBtn) yesBtn.addEventListener("click", _onYes);
      if (noBtn) noBtn.addEventListener("click", _onNo);
      if (neverBtn) neverBtn.addEventListener("click", _onNever);
      break;
    }

    case "whats_new": {
      if (!whatsNewEl) { setIntroStage("hint"); break; }
      whatsNewEl.classList.remove("hidden", "fading");
      const wnBtn = document.getElementById("whatsNewBtn");
      // Show button after a short delay — user must click to advance (no auto-advance)
      setTimeout(() => {
        if (introStage !== "whats_new") return;
        if (wnBtn) wnBtn.classList.remove("hidden");
      }, 1000);
      function _advanceFromWhatsNew() {
        if (introStage !== "whats_new") return;
        if (wnBtn) wnBtn.removeEventListener("click", _advanceFromWhatsNew);
        whatsNewEl.classList.add("fading");
        setTimeout(() => {
          whatsNewEl.classList.add("hidden");
          setIntroStage("hint");
        }, _HINT_FADE_MS);
      }
      if (wnBtn) wnBtn.addEventListener("click", _advanceFromWhatsNew);
      break;
    }

    case "hint": {
      if (!hintEl) {
        setIntroStage("hint2");
        break;
      }
      hintEl.classList.remove("hidden", "fading");
      _runHintWalkthrough();
      break;
    }

    case "hint2": {
      if (!hintEl2) {
        setIntroStage("hint3");
        break;
      }
      hintEl2.classList.remove("hidden", "fading");
      _runHintScoringModes();
      break;
    }

    case "hint3": {
      if (!hintEl3) {
        setIntroStage("hint4");
        break;
      }
      hintEl3.classList.remove("hidden", "fading");
      _runHintLayoutModes();
      break;
    }

    case "hint4": {
      if (!hintEl4) {
        setIntroStage("hint_settings");
        break;
      }
      hintEl4.classList.remove("hidden", "fading");
      _runHintReference();
      break;
    }

    case "hint_settings": {
      const hintSEl = document.getElementById("hintScreenSettings");
      if (!hintSEl) {
        setIntroStage("done");
        break;
      }
      hintSEl.classList.remove("hidden", "fading");
      setTimeout(() => {
        if (introStage !== "hint_settings") return;
        hintSEl.classList.add("fading");
        setTimeout(() => {
          hintSEl.classList.add("hidden");
          setIntroStage("done");
        }, _HINT_FADE_MS);
      }, 2000);
      break;
    }

    case "connecting": {
      if (splashEl) splashEl.classList.add("hidden");
      _showSearching();
      if (connectEl) connectEl.classList.remove("hidden", "fading");
      _startOsuCheck();
      break;
    }

    case "connected": {
      if (connectEl) connectEl.classList.remove("hidden", "fading");
      _showConnected();
      setTimeout(() => {
        if (introStage !== "connected") return;
        if (connectEl) connectEl.classList.add("fading");
        setTimeout(() => {
          if (introStage !== "connected") return;
          if (connectEl) connectEl.classList.add("hidden");
          // Show tutorial prompt for first-timers unless they opted out.
          const tutCount = parseInt(localStorage.getItem("danOverlay_tutCount") || "0", 10);
          const showTut = !_settings.neverShowTutorial && tutCount < 2;
          setIntroStage(showTut ? "tutorial_prompt" : "done");
        }, 600);
      }, _CONNECTED_HOLD);
      break;
    }

    case "done": {
      _stopOsuCheck();
      break;
    }
  }
}

/* ── Boot ────────────────────────────────────────────────────────── */

function boot() {
  const isPythonBridge = typeof window.__overlayFromPython === 'function';
  if (!isPythonBridge) {
    window.__overlayFromPython = applyFromPythonBridge;
  }
  bridgeMode = typeof window.__overlayFromPython === 'function';

  setTickerText(ui.mapTicker, "Waiting for beatmap from tosu...");
  setTickerText(ui.statsTicker, "BPM -- · TIME --:-- · NOTES -- · LN -- · OD -- · HP -- · MAPPER --");

  // If we reloaded (e.g. after a skin switch), skip all intro screens.
  const skipIntro = localStorage.getItem("danOverlay_skipIntro") === "1";
  if (skipIntro) {
    localStorage.removeItem("danOverlay_skipIntro");
    if (splashEl) splashEl.classList.add("hidden");
    // Hide connect screen on reload — bridge will already be live.
    if (connectEl) connectEl.classList.add("hidden");
    introStage = "connecting";
    // Clear the cached mapKey so the first map_info after reload triggers
    // a fresh background crossfade. Without this, the _bgGeneration race
    // during boot can silently cancel the crossfade, leaving the skin with
    // a black background until the user switches skins and returns.
    if (ui.bg) ui.bg.dataset.mapKey = "";
  } else {
    // Initialize the connect screen visuals before the bridge-init arrives.
    _showSearching();
    setIntroStage("connecting");
  }

  // WS connects in parallel with the intro. The intro state machine in the
  // ws.open / ws.close handlers manages the transition to the live overlay.
  connect();

  initVisualizer();
  initMiniViz();
  setChartButtonReady(false);
}

/* ── Resize mode toggle (R key) ─────────────────────────────────── */
let _resizeMode = "free";  // "free" | "locked" — starts as free

function _updateHintLabel() {
  const el = document.getElementById("hintCurrentMode");
  if (el) el.textContent = _resizeMode === "locked" ? "Locked" : "Free";
}

/* Single-step hint: R key toggles Free ↔ Locked, indicator reacts live */
function _runHintWalkthrough() {
  _resizeMode = "free"; // always start in Free

  const btn = document.getElementById("hintBtn");
  const modeFree = document.getElementById("hintModeFree");
  const modeLock = document.getElementById("hintModeLocked");
  const rIndicator = document.getElementById("hintRIndicator");
  const rLabel = document.getElementById("hintRLabel");

  let _everPressed = false;  // first R press starts the Done-button timer
  let _btnTimer = null;

  // Initial UI state — Free mode, key grey + pulsing
  if (rIndicator) { rIndicator.classList.remove("hint-locked", "hint-free-interacted"); }
  if (rLabel) rLabel.textContent = "press to try";
  if (modeFree) modeFree.classList.add("hint-mode-active");
  if (modeLock) modeLock.classList.remove("hint-mode-active");
  if (btn) { btn.textContent = "Done"; btn.classList.add("hidden"); }
  _updateHintLabel();

  function _updateIndicator() {
    if (!rIndicator) return;
    if (_resizeMode === "locked") {
      rIndicator.classList.add("hint-locked");
      rIndicator.classList.remove("hint-free-interacted");
      if (rLabel) rLabel.textContent = "◈ Locked";
    } else {
      rIndicator.classList.remove("hint-locked");
      if (_everPressed) rIndicator.classList.add("hint-free-interacted");
      if (rLabel) rLabel.textContent = "◱ Free";
    }
    // Keep mode rows in sync
    if (modeFree) modeFree.classList.toggle("hint-mode-active", _resizeMode === "free");
    if (modeLock) modeLock.classList.toggle("hint-mode-active", _resizeMode === "locked");
  }

  // Fires AFTER the global keydown handler already toggled _resizeMode
  function _hintKeydown(e) {
    if (e.key !== "r" && e.key !== "R") return;
    if (e.ctrlKey || e.altKey || e.metaKey) return;
    if (introStage !== "hint") return;
    _updateIndicator();
    if (!_everPressed) {
      _everPressed = true;
      _btnTimer = setTimeout(() => {
        if (introStage !== "hint") return;
        if (btn) btn.classList.remove("hidden");
      }, _HINT_BTN_DELAY);
    }
  }
  document.addEventListener("keydown", _hintKeydown);

  function _onBtnClick() {
    if (introStage !== "hint") return;
    document.removeEventListener("keydown", _hintKeydown);
    btn.removeEventListener("click", _onBtnClick);
    if (_btnTimer) clearTimeout(_btnTimer);
    if (hintEl) hintEl.classList.add("fading");
    setTimeout(() => {
      if (hintEl) hintEl.classList.add("hidden");
      setIntroStage("hint2");  // proceed to scoring modes hint
    }, _HINT_FADE_MS);
  }

  if (btn) btn.addEventListener("click", _onBtnClick);
}

function _runHintScoringModes() {
  const btn2 = document.getElementById("hintBtn2");
  const items = [
    { id: "smItem1", key: "1" },
    { id: "smItem2", key: "2" },
    { id: "smItem3", key: "3" },
    { id: "smItem4", key: "4" },
  ];

  // Start all items dimmed — light up on interaction
  items.forEach(({ id }) => {
    const el = document.getElementById(id);
    if (el) el.classList.remove("hint-mode-active");
  });

  let _everPressed = false;
  let _btnTimer = null;

  function _hintKeydown2(e) {
    if (!e.ctrlKey || e.altKey || e.metaKey) return;
    if (introStage !== "hint2") return;
    const idx = ["1", "2", "3", "4"].indexOf(e.key);
    if (idx === -1) return;
    e.preventDefault();

    const el = document.getElementById(items[idx].id);
    if (el) {
      el.classList.add("hint-mode-active", "hint-mode-pressed");
      // Remove press flash class after animation
      setTimeout(() => el.classList.remove("hint-mode-pressed"), 400);
    }

    if (!_everPressed) {
      _everPressed = true;
      _btnTimer = setTimeout(() => {
        if (introStage !== "hint2") return;
        if (btn2) btn2.classList.remove("hidden");
      }, _HINT2_BTN_DELAY);
    }
  }
  document.addEventListener("keydown", _hintKeydown2);

  function _onDone() {
    if (introStage !== "hint2") return;
    clearTimeout(_btnTimer);
    document.removeEventListener("keydown", _hintKeydown2);
    btn2.removeEventListener("click", _onDone);
    if (hintEl2) hintEl2.classList.add("fading");
    setTimeout(() => {
      if (hintEl2) hintEl2.classList.add("hidden");
      setIntroStage("hint3");
    }, _HINT_FADE_MS);
  }
  if (btn2) btn2.addEventListener("click", _onDone);
}

function _runHintLayoutModes() {
  const btn3 = document.getElementById("hintBtn3");
  const items = [
    document.getElementById("lmItem1"),
    document.getElementById("lmItem2"),
    document.getElementById("lmItem3"),
  ];
  const layoutOrder = ["complete", "simplified", "compact"];
  let _presses = 0;

  // Sync to current layout
  function _syncItems() {
    const cur = layoutOrder.indexOf(_layoutMode);
    items.forEach((el, i) => {
      if (!el) return;
      el.classList.toggle("hint-mode-active", i === cur);
    });
  }
  _syncItems();

  // Show button after the first L press
  function _hintKeydownL(e) {
    if (introStage !== "hint3") return;
    if ((e.key !== "l" && e.key !== "L") || e.ctrlKey || e.altKey || e.metaKey) return;
    // The global L handler will update _layoutMode; let it run first.
    requestAnimationFrame(() => {
      _syncItems();
      _presses++;
      if (_presses === 1) {
        setTimeout(() => {
          if (introStage !== "hint3") return;
          if (btn3) btn3.classList.remove("hidden");
        }, 600);
      }
    });
  }
  document.addEventListener("keydown", _hintKeydownL);

  function _onNext3() {
    if (introStage !== "hint3") return;
    document.removeEventListener("keydown", _hintKeydownL);
    btn3.removeEventListener("click", _onNext3);
    if (hintEl3) hintEl3.classList.add("fading");
    setTimeout(() => {
      if (hintEl3) hintEl3.classList.add("hidden");
      setIntroStage("hint4");
    }, _HINT_FADE_MS);
  }
  if (btn3) btn3.addEventListener("click", _onNext3);

  // Also show button after 1.5 s so user doesn't get stuck if L doesn't land
  setTimeout(() => {
    if (introStage !== "hint3") return;
    if (btn3) btn3.classList.remove("hidden");
  }, 1500);
}

function _runHintReference() {
  const btn4 = document.getElementById("hintBtn4");
  // All items are already visible and active — just show the button after a beat.
  setTimeout(() => {
    if (introStage !== "hint4") return;
    if (btn4) btn4.classList.remove("hidden");
  }, 800);

  function _onDone4() {
    if (introStage !== "hint4") return;
    btn4.removeEventListener("click", _onDone4);
    if (hintEl4) hintEl4.classList.add("fading");
    setTimeout(() => {
      if (hintEl4) hintEl4.classList.add("hidden");
      setIntroStage("hint_settings");
    }, _HINT_FADE_MS);
  }
  if (btn4) btn4.addEventListener("click", _onDone4);
}

document.addEventListener("keydown", (e) => {
  if (_cfgIsOpen()) return;
  if (!isKeybind("resize_toggle", e) && !isKeybind("resize_reset", e)) return;

  if (isKeybind("resize_reset", e)) {
    // Ctrl+R (default) — reset window to default 700×320 and clear zoom
    e.preventDefault();
    _resizeMode = "free";
    _resetZoom();
    _updateHintLabel();
    const panel = document.getElementById("danPanel") || document.getElementById("overlay");
    const isExpanded = panel && (panel.classList.contains("is-expanded") || panel.classList.contains("expanded"));
    if (_CURRENT_SKIN === "4") {
      if (window.pywebview?.api?.set_window_size) {
        window.pywebview.api.set_window_size(284, isExpanded ? 466 : 335);
      }
      document.documentElement.style.zoom = 0.61;
      if (typeof showToast === "function") showToast(isExpanded ? "Reset: 284×466 ◱" : "Reset: 284×335 ◱");
    } else if (_CURRENT_SKIN === "5") {
      if (window.pywebview?.api?.set_window_size) {
        window.pywebview.api.set_window_size(589, isExpanded ? 272 : 170);
      }
      document.documentElement.style.zoom = 0.75;
      if (typeof window._resetP2ResizeStates === "function") {
        window._resetP2ResizeStates();
      }
      if (typeof showToast === "function") showToast(isExpanded ? "Reset: 589×272 ◱" : "Reset: 589×170 ◱");
    } else if (_CURRENT_SKIN === "6") {
      if (window.pywebview?.api?.set_window_size) {
        window.pywebview.api.set_window_size(645, isExpanded ? 297 : 211);
      }
      document.documentElement.style.zoom = 0.73;
      if (typeof showToast === "function") showToast(isExpanded ? "Reset: 645×297 ◱" : "Reset: 645×211 ◱");
    } else if (_CURRENT_SKIN === "8") {
      if (window.pywebview?.api?.set_window_size) {
        window.pywebview.api.set_window_size(594, isExpanded ? 234 : 138);
      }
      document.documentElement.style.zoom = 0.94;
      if (typeof showToast === "function") showToast(isExpanded ? "Reset: 594×234 ◱" : "Reset: 594×138 ◱");
    } else {
      if (window.pywebview?.api?.reset_window_size) {
        window.pywebview.api.reset_window_size();
      }
      if (typeof showToast === "function") showToast("Reset: 700×320 ◱");
    }
    // Also reset layout to full (for skins that use classic layout modes)
    _layoutMode = "complete";
    _settings.layout = "complete";
    document.getElementById("danPanel")?.classList.remove("layout-simplified", "layout-compact");
    return;
  }

  // resize_toggle — toggle free ↔ locked
  const nextMode = _resizeMode === "free" ? "locked" : "free";
  if (nextMode === "locked") {
    _lockedBaseWidth = Math.max(1, window.innerWidth);
    _lockedBaseHeight = Math.max(1, window.innerHeight);
    _lockedBaseZoom = _currentZoomFactor();
  }
  _resizeMode = nextMode;
  _updateHintLabel();
  adaptZoom();

  if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.set_resize_mode === "function") {
    window.pywebview.api.set_resize_mode(_resizeMode);
  }

  const label = _resizeMode === "locked"
    ? "Resize: Locked ◈ (proportional)"
    : "Resize: Free ◱";
  if (typeof showToast === "function") showToast(label);
});

// Ctrl+1 — Reform (default mode)
document.addEventListener("keydown", (e) => {
  if (_cfgIsOpen()) return;
  if (!isKeybind("mode_reform", e)) return;
  e.preventDefault();
  _scoringMode = "reform";
  _lnModePinned = false;
  _lnOverrideActive = false;
  _updateScoringModeBadge();
  showModeAnnounce("Reform", "reform");
  if (_lastAnalysisPayload) _renderAnalysisPayload(_lastAnalysisPayload);
});

// Ctrl+2 — Celestial
document.addEventListener("keydown", (e) => {
  if (_cfgIsOpen()) return;
  if (!isKeybind("mode_celestial", e)) return;
  e.preventDefault();
  _scoringMode = "celestial";
  _lnModePinned = false;
  _lnOverrideActive = false;
  _updateScoringModeBadge();
  showModeAnnounce("Celestial", "celestial");
  if (_lastAnalysisPayload) _renderAnalysisPayload(_lastAnalysisPayload);
});

// Ctrl+3 — Signicial
document.addEventListener("keydown", (e) => {
  if (_cfgIsOpen()) return;
  if (!isKeybind("mode_signicial", e)) return;
  e.preventDefault();
  _scoringMode = "signicial";
  _lnModePinned = false;
  _lnOverrideActive = false;
  _updateScoringModeBadge();
  showModeAnnounce("Signicial", "signicial");
  if (_lastAnalysisPayload) _renderAnalysisPayload(_lastAnalysisPayload);
});

// Ctrl+4 — Shoegazer
document.addEventListener("keydown", (e) => {
  if (_cfgIsOpen()) return;
  if (!isKeybind("mode_shoegazer", e)) return;
  e.preventDefault();
  _scoringMode = "shoegazer";
  _lnModePinned = false;
  _lnOverrideActive = false;
  _updateScoringModeBadge();
  showModeAnnounce("Shoegazer", "shoegazer");
  if (_lastAnalysisPayload) _renderAnalysisPayload(_lastAnalysisPayload);
});

// Ctrl+5 — LN Course (manual pin / unpin)
document.addEventListener("keydown", (e) => {
  if (_cfgIsOpen()) return;
  if (!isKeybind("mode_ln_course", e)) return;
  e.preventDefault();
  if (_lnModePinned) {
    // Unpin: revert to pipeline control
    _lnModePinned = false;
    _lnOverrideActive = false;
    _updateScoringModeBadge();
    const restoreName = _scoringMode === "celestial" ? "Celestial"
      : _scoringMode === "signicial" ? "Signicial"
        : _scoringMode === "shoegazer" ? "Shoegazer"
          : "Reform";
    showModeAnnounce(restoreName, _scoringMode);
  } else {
    // Pin: force LN Course mode regardless of pipeline
    _lnModePinned = true;
    _lnOverrideActive = true;
    _updateScoringModeBadge();
    showModeAnnounce("LN Course \u25C8", "ln_course");
  }
  if (_lastAnalysisPayload) _renderAnalysisPayload(_lastAnalysisPayload);
});

// Tab — toggle whether the overlay stays pinned above osu
document.addEventListener("keydown", (e) => {
  if (_cfgIsOpen()) return;
  if (!isKeybind("overlay_pin", e)) return;
  e.preventDefault();
  if (window.pywebview?.api?.toggle_overlay_pin) {
    window.pywebview.api.toggle_overlay_pin().then((isPinned) => {
      if (typeof showToast === "function") {
        showToast(isPinned
          ? "Overlay pin ON — stays above osu ◈"
          : "Overlay pin OFF — normal window order ◱"
        );
      }
    });
  }
});

/* Responsive Zooming and Performance Scaling for High Resolutions */
// Base dimensions the overlay was designed at.
const _BASE_W = 700;
const _BASE_H = 320;
let _lockedBaseWidth = _BASE_W;
let _lockedBaseHeight = _BASE_H;
let _lockedBaseZoom = 1;

function _currentZoomFactor() {
  const raw = parseFloat(document.documentElement.style.zoom || "1");
  return Number.isFinite(raw) && raw > 0 ? raw : 1;
}

function _applyZoom(zoomFactor) {
  if (!Number.isFinite(zoomFactor) || zoomFactor <= 0 || Math.abs(zoomFactor - 1) < 0.001) {
    document.documentElement.style.zoom = "";
    return;
  }

  document.documentElement.style.zoom = zoomFactor.toFixed(4);
}

function adaptZoom() {
  const w = window.innerWidth;
  const h = window.innerHeight;
  const isLarge = w >= 900;

  document.documentElement.style.setProperty(
    "--glass-blur",
    isLarge ? "blur(12px) saturate(140%)" : "blur(24px) saturate(160%)"
  );

  if (_resizeMode === "locked") {
    // Locked mode keeps the current Free-mode visual scale on entry, then
    // scales proportionally from that exact window/zoom state on future resizes.
    const widthRatio = w / Math.max(1, _lockedBaseWidth);
    const heightRatio = h / Math.max(1, _lockedBaseHeight);
    const zoomFactor = Math.max(0.5, _lockedBaseZoom * Math.min(widthRatio, heightRatio));
    _applyZoom(zoomFactor);
  }
  // Free mode: leave zoom as-is so any scale set in locked mode is preserved.
  // Call _resetZoom() explicitly only when you want to go back to default.

  syncMapTitleMarquee();
  // _updateResolutionIndicator();
}

/*
function _updateResolutionIndicator() {
  let badge = document.getElementById("tempResIndicator");
  if (!badge) {
    badge = document.createElement("div");
    badge.id = "tempResIndicator";
    badge.style.position = "fixed";
    badge.style.top = "12px";
    badge.style.right = "12px";
    badge.style.backgroundColor = "rgba(10, 10, 12, 0.9)";
    badge.style.backdropFilter = "blur(12px)";
    badge.style.webkitBackdropFilter = "blur(12px)";
    badge.style.color = "#ffffff";
    badge.style.fontFamily = "monospace";
    badge.style.fontSize = "10px";
    badge.style.lineHeight = "1.4";
    badge.style.padding = "8px 12px";
    badge.style.borderRadius = "12px";
    badge.style.border = "1px solid rgba(255, 255, 255, 0.08)";
    badge.style.zIndex = "99999";
    badge.style.pointerEvents = "auto";
    badge.style.cursor = "pointer";
    badge.style.boxShadow = "0 8px 24px rgba(0, 0, 0, 0.6)";
    badge.style.transition = "border-color 0.3s ease, background-color 0.3s ease";
    badge.title = "Click to copy dimensions to clipboard";

    badge.addEventListener("mouseenter", () => {
      badge.style.borderColor = "var(--dan-primary, #5ddfb0)";
      badge.style.backgroundColor = "rgba(20, 20, 24, 0.95)";
    });
    badge.addEventListener("mouseleave", () => {
      badge.style.borderColor = "rgba(255, 255, 255, 0.08)";
      badge.style.backgroundColor = "rgba(10, 10, 12, 0.9)";
    });

    badge.addEventListener("click", () => {
      const isFrameless = _settings.frameless;
      const innerW = window.innerWidth;
      const innerH = window.innerHeight;
      const outerW = isFrameless ? innerW : (innerW + 16);
      const outerH = isFrameless ? innerH : (innerH + 39);
      const zoomPct = Math.round(_currentZoomFactor() * 100);
      const panel = document.getElementById("danPanel") || document.getElementById("overlay");
      const isExpanded = panel && (panel.classList.contains("is-expanded") || panel.classList.contains("expanded"));
      const layout = isExpanded ? "Expanded" : "Collapsed";

      const copyText = `[DanOverlay Dimensions]
Skin: ${_CURRENT_SKIN} (${_CURRENT_SKIN === "8" ? "Hero-Dan Lazer" : _CURRENT_SKIN === "7" ? "Sunny Rebirth" : _CURRENT_SKIN === "5" ? "Broadcast Bar" : _CURRENT_SKIN === "4" ? "Vertical Monolith" : _CURRENT_SKIN === "3" ? "Graph" : _CURRENT_SKIN === "2" ? "Classic" : "Modern"})
Inner (Viewport): ${innerW} × ${innerH}
Outer (Window): ${outerW} × ${outerH}
Zoom: ${zoomPct}%
Resize Mode: ${_resizeMode.toUpperCase()}
Layout: ${layout}`;

      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(copyText).then(() => {
          showToast("Copied HUD dimensions! 📋", 1800);
        }).catch(() => {
          _fallbackCopyText(copyText);
        });
      } else {
        _fallbackCopyText(copyText);
      }
    });

    document.body.appendChild(badge);
  }

  const isFrameless = _settings.frameless;
  const innerW = window.innerWidth;
  const innerH = window.innerHeight;
  // Estimate outer dimensions based on border frame offsets (16px width, 39px height)
  const outerW = isFrameless ? innerW : (innerW + 16);
  const outerH = isFrameless ? innerH : (innerH + 39);
  const zoomPct = Math.round(_currentZoomFactor() * 100);

  badge.innerHTML = `
    <div style="color:var(--dan-primary, #5ddfb0);font-weight:bold;margin-bottom:4px;letter-spacing:1px;font-family:'Inter',sans-serif;font-size:9px;text-transform:uppercase">HUD Medidor (Copiar)</div>
    <div style="display:grid;grid-template-columns:auto auto;gap:4px 12px;opacity:0.9">
      <span>Viewport (Inner):</span><span style="color:#5ddfb0;font-weight:bold">${innerW} × ${innerH}</span>
      <span>Window (Outer):</span><span style="color:#ffb627">${outerW} × ${outerH}</span>
      <span>Zoom Actual:</span><span style="color:#b48cff">${zoomPct}%</span>
      <span>Redimensionar:</span><span style="color:#59f">${_resizeMode.toUpperCase()}</span>
    </div>
  `;
}

function _fallbackCopyText(text) {
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.style.position = "fixed";
  ta.style.left = "-9999px";
  document.body.appendChild(ta);
  ta.focus();
  ta.select();
  try {
    document.execCommand("copy");
    showToast("Copied HUD dimensions! 📋", 1800);
  } catch (_) {
    showToast("Failed to copy", 1800);
  }
  document.body.removeChild(ta);
}
*/

function _resetZoom() {
  document.documentElement.style.zoom = "";
}
window.addEventListener('resize', adaptZoom);
adaptZoom();

// L key — cycle layout density
document.addEventListener("keydown", (e) => {
  if (_cfgIsOpen()) return;
  if (!isKeybind("layout_cycle", e)) return;
  e.preventDefault();
  _cycleLayout();
});

// Ctrl+, — open settings panel
document.addEventListener("keydown", (e) => {
  if (_cfgIsOpen()) return;
  if (!isKeybind("open_settings", e)) return;
  e.preventDefault();
  _openSettings();
});

/* ── Settings panel ─────────────────────────────────────────────────── */
let _cfgPendingAction = null;
let _cfgCaptureBadge = null;
let _cfgCaptureBtn = null;

function _formatKeybind(kb) {
  const parts = [];
  if (kb.ctrl) parts.push("Ctrl");
  if (kb.alt) parts.push("Alt");
  const key = kb.key === " " ? "Space"
    : kb.key.length === 1 ? kb.key.toUpperCase()
      : kb.key;
  parts.push(key);
  return parts.join("+");
}

let _cfgPrevHeight = null;
let _cfgPrevWidth = null;
const _CFG_OPEN_HEIGHT = 620;
let _isOpeningSettings = false;

async function _openSettings() {
  if (_isOpeningSettings) return;
  const overlay = document.getElementById("cfgOverlay");
  if (!overlay) return;
  _isOpeningSettings = true;
  // Capture the *actual* window dimensions before expanding, so we can restore
  // them exactly and show the real values in the Window Size fields.
  // PyWebView window dimensions can be stale/cached on Windows.
  // Use JS layout outer calculations instead.
  const isFrameless = _settings && _settings.frameless;
  _cfgPrevWidth = isFrameless ? window.innerWidth : (window.innerWidth + 16);
  _cfgPrevHeight = isFrameless ? window.innerHeight : (window.innerHeight + 39);

  // Expand window dimensions to comfortably fit settings panel if narrow or short
  if (window.pywebview?.api?.set_window_size) {
    const curH = _cfgPrevHeight ?? 0;
    const curW = _cfgPrevWidth ?? 0;

    let targetW = -1;
    let targetH = -1;

    if (curW > 0 && curW < 580) {
      targetW = 580;
    } else {
      _cfgPrevWidth = null; // No need to restore width if we didn't expand it
    }

    if (curH > 0 && curH < _CFG_OPEN_HEIGHT) {
      targetH = _CFG_OPEN_HEIGHT;
    } else {
      _cfgPrevHeight = null; // No need to restore height if we didn't expand it
    }

    if (targetW !== -1 || targetH !== -1) {
      window.pywebview.api.set_window_size(targetW, targetH);
    }
  }

  _renderCfgPanel();
  overlay.classList.add("is-open");
  overlay.setAttribute("aria-hidden", "false");
  _isOpeningSettings = false;
}

function _closeSettings() {
  const overlay = document.getElementById("cfgOverlay");
  if (!overlay || !overlay.classList.contains("is-open")) return;
  _cancelKeybindCapture();
  overlay.classList.remove("is-open");
  overlay.setAttribute("aria-hidden", "true");

  // Restore window to pre-settings dimensions if we expanded them.
  const targetW = (_cfgPrevWidth !== null) ? _cfgPrevWidth : -1;
  const targetH = (_cfgPrevHeight !== null) ? _cfgPrevHeight : -1;

  if ((targetW !== -1 || targetH !== -1) && window.pywebview?.api?.set_window_size) {
    window.pywebview.api.set_window_size(targetW, targetH);
  }
  _cfgPrevHeight = null;
  _cfgPrevWidth = null;
}

function _renderCfgPanel() {
  const blurSlider = document.getElementById("cfgBlurSlider");
  const blurNum = document.getElementById("cfgBlurNum");
  const darkSlider = document.getElementById("cfgBrightSlider");
  const darkNum = document.getElementById("cfgBrightNum");
  if (blurSlider) blurSlider.value = _settings.blur;
  if (blurNum) blurNum.value = _settings.blur.toFixed(2);
  if (darkSlider) darkSlider.value = _settings.brightness;
  if (darkNum) darkNum.value = _settings.brightness.toFixed(2);
  const logoSizeSlider = document.getElementById("cfgLogoSizeSlider");
  const logoSizeNum = document.getElementById("cfgLogoSizeNum");
  const logoOpacitySlider = document.getElementById("cfgLogoOpacitySlider");
  const logoOpacityNum = document.getElementById("cfgLogoOpacityNum");
  if (logoSizeSlider) logoSizeSlider.value = _settings.logoSize;
  if (logoSizeNum) logoSizeNum.value = _settings.logoSize;
  if (logoOpacitySlider) logoOpacitySlider.value = _settings.logoOpacity;
  if (logoOpacityNum) logoOpacityNum.value = _settings.logoOpacity;
  const danScaleSlider = document.getElementById("cfgDanScaleSlider");
  const danScaleNum = document.getElementById("cfgDanScaleNum");
  if (danScaleSlider) danScaleSlider.value = _settings.danScale;
  if (danScaleNum) danScaleNum.value = _settings.danScale;
  
  const bcastBrightSlider = document.getElementById("cfgBorderBrightSlider");
  const bcastBrightNum = document.getElementById("cfgBorderBrightNum");
  if (bcastBrightSlider) bcastBrightSlider.value = _settings.broadcastBorderBright ?? 75;
  if (bcastBrightNum) bcastBrightNum.value = _settings.broadcastBorderBright ?? 75;

  const bcastThickSlider = document.getElementById("cfgBorderThickSlider");
  const bcastThickNum = document.getElementById("cfgBorderThickNum");
  if (bcastThickSlider) bcastThickSlider.value = _settings.broadcastBorderThick ?? 1;
  if (bcastThickNum) bcastThickNum.value = _settings.broadcastBorderThick ?? 1;

  const greenScreenChk = document.getElementById("cfgGreenScreenChk");
  if (greenScreenChk) greenScreenChk.checked = _settings.greenScreen;
  const framelessChk = document.getElementById("cfgFramelessChk");
  if (framelessChk) framelessChk.checked = _settings.frameless;
  const skinSel = document.getElementById("cfgSkinSelect");
  if (skinSel) skinSel.value = _settings.skin;
  
  const ui6SettingsWrap = document.getElementById("cfgUi6Settings");
  if (ui6SettingsWrap) {
    ui6SettingsWrap.style.display = _settings.skin === "6" ? "block" : "none";
  }
  const ui6NoVignetteChk = document.getElementById("cfgUi6NoVignetteChk");
  if (ui6NoVignetteChk) ui6NoVignetteChk.checked = _settings.ui6_no_vignette;
  const ui6SimpleModeChk = document.getElementById("cfgUi6SimpleModeChk");
  if (ui6SimpleModeChk) ui6SimpleModeChk.checked = _settings.ui6_simple_mode;
  const ui6OutlinesChk = document.getElementById("cfgUi6OutlinesChk");
  if (ui6OutlinesChk) ui6OutlinesChk.checked = _settings.ui6_outlines;
  
  // Window size inputs — populate with current dimensions from Python
  _populateWindowSizeInputs();
  _renderKeybindRows();
}

async function _populateWindowSizeInputs() {
  const wEl = document.getElementById("cfgWinWidth");
  const hEl = document.getElementById("cfgWinHeight");
  if (!wEl || !hEl) return;
  // Use captured dimensions from before settings panel expansion,
  // or fall back to saved settings, then to Python API, then to defaults.
  const savedW = _settings.windowWidth;
  const savedH = _settings.windowHeight;

  if (savedW) {
    wEl.value = savedW;
  } else if (_cfgPrevWidth) {
    wEl.value = _cfgPrevWidth;
  } else {
    if (_CURRENT_SKIN === "4") wEl.value = 284;
    else if (_CURRENT_SKIN === "5") wEl.value = 589;
    else if (_CURRENT_SKIN === "6") wEl.value = 645;
    else wEl.value = 700;
  }

  if (savedH) {
    hEl.value = savedH;
  } else if (_cfgPrevHeight) {
    hEl.value = _cfgPrevHeight;
  } else {
    if (_CURRENT_SKIN === "4") {
      const isExp = document.getElementById("danPanel")?.classList.contains("is-expanded");
      hEl.value = isExp ? 466 : 335;
    } else if (_CURRENT_SKIN === "5") {
      const isExp = document.getElementById("danPanel")?.classList.contains("is-expanded");
      hEl.value = isExp ? 272 : 170;
    } else if (_CURRENT_SKIN === "6") {
      const isExp = document.getElementById("danPanel")?.classList.contains("is-expanded");
      hEl.value = isExp ? 297 : 211;
    } else {
      hEl.value = 320;
    }
  }
}

function _setKeybindButtonIdle(action, badge, btn) {
  if (!btn) return;
  btn.classList.remove("listening");
  btn.textContent = "Edit";
  btn.onclick = () => _startKeybindCapture(action, badge, btn);
}

function _renderKeybindRows() {
  const container = document.getElementById("cfgKeybinds");
  if (!container) return;
  container.innerHTML = "";
  for (const [action, label] of Object.entries(_KEYBIND_LABELS)) {
    const kb = _settings.keybinds[action];
    const row = document.createElement("div");
    row.className = "cfg-keybind-row";
    row.dataset.action = action;

    const lbl = document.createElement("span");
    lbl.className = "cfg-keybind-label";
    lbl.textContent = label;

    const badge = document.createElement("span");
    badge.className = "cfg-key-badge";
    badge.textContent = _formatKeybind(kb);

    const btn = document.createElement("button");
    btn.className = "cfg-edit-btn";
    btn.type = "button";
    _setKeybindButtonIdle(action, badge, btn);

    row.append(lbl, badge, btn);
    container.appendChild(row);
  }
}

function _startKeybindCapture(action, badge, btn) {
  _cancelKeybindCapture();
  _cfgPendingAction = action;
  _cfgCaptureBadge = badge;
  _cfgCaptureBtn = btn;
  badge.classList.add("listening");
  badge.textContent = "Press...";
  btn.classList.add("listening");
  btn.textContent = "Cancel";
  btn.onclick = () => _cancelKeybindCapture();
}

function _cancelKeybindCapture() {
  if (!_cfgPendingAction) return;
  if (_cfgCaptureBadge) {
    _cfgCaptureBadge.classList.remove("listening");
    _cfgCaptureBadge.textContent = _formatKeybind(_settings.keybinds[_cfgPendingAction]);
  }
  if (_cfgCaptureBtn) {
    _setKeybindButtonIdle(_cfgPendingAction, _cfgCaptureBadge, _cfgCaptureBtn);
  }
  _cfgPendingAction = null;
  _cfgCaptureBadge = null;
  _cfgCaptureBtn = null;
}

// Capture-phase listener: intercepts keypresses while a keybind is being recorded
document.addEventListener("keydown", (e) => {
  if (!_cfgPendingAction) return;
  if (["Control", "Alt", "Shift", "Meta"].includes(e.key)) return;
  if (e.key === "Escape") { _cancelKeybindCapture(); return; }

  e.preventDefault();
  e.stopPropagation();

  // Enforce max 2 keys: Ctrl+Alt+key counts as 3 — reject it
  if (e.ctrlKey && e.altKey) {
    if (_cfgCaptureBadge) {
      _cfgCaptureBadge.textContent = "Max 2 keys";
      _cfgCaptureBadge.style.color = "#ff6060";
      setTimeout(() => {
        if (_cfgCaptureBadge) {
          _cfgCaptureBadge.textContent = "Press...";
          _cfgCaptureBadge.style.color = "";
        }
      }, 900);
    }
    return;
  }

  const newKb = { key: e.key, ctrl: e.ctrlKey, alt: e.altKey };
  _settings.keybinds[_cfgPendingAction] = newKb;

  if (_cfgCaptureBadge) {
    _cfgCaptureBadge.classList.remove("listening");
    _cfgCaptureBadge.textContent = _formatKeybind(newKb);
  }
  if (_cfgCaptureBtn) {
    _setKeybindButtonIdle(_cfgPendingAction, _cfgCaptureBadge, _cfgCaptureBtn);
  }
  _cfgPendingAction = null;
  _cfgCaptureBadge = null;
  _cfgCaptureBtn = null;
}, true); // capture phase so it fires before normal handlers

function _cfgSliderClamp(v) {
  const n = parseFloat(v);
  return Number.isFinite(n) ? Math.min(100, Math.max(0, Math.round(n * 100) / 100)) : 0;
}

function _initCfgListeners() {
  // Right-click anywhere → open settings
  document.addEventListener("contextmenu", (e) => {
    e.preventDefault();
    _openSettings();
  });

  // Close / Cancel / Save
  document.getElementById("cfgClose")?.addEventListener("click", _closeSettings);
  document.getElementById("cfgCancel")?.addEventListener("click", async () => {
    await _loadSettings();   // revert any unsaved slider changes
    _applySettings();
    _closeSettings();
  });
  document.getElementById("cfgSave")?.addEventListener("click", async () => {
    const skinChanged = _settings.skin !== _CURRENT_SKIN;
    // Read window size directly from DOM (change event may not have fired yet)
    const winW = document.getElementById("cfgWinWidth");
    const winH = document.getElementById("cfgWinHeight");
    const newW = winW ? parseInt(winW.value) : null;
    const newH = winH ? parseInt(winH.value) : null;
    if (newW && newH) { _settings.windowWidth = newW; _settings.windowHeight = newH; }
    await _saveSettings();
    // Apply window size (null = use default 700x320)
    if (newW && newH && window.pywebview?.api?.set_window_size) {
      window.pywebview.api.set_window_size(newW, newH);
      // Prevent _closeSettings from restoring the pre-settings height
      // since the user explicitly chose a new window size.
      _cfgPrevHeight = null;
    }
    _closeSettings();
    if (skinChanged) {
      // Ask Python to navigate the webview to the correct skin HTML.
      // Using pywebview.load_url() ensures the bridge is re-established.
      localStorage.setItem("danOverlay_skipIntro", "1");
      showToast("Reloading with new skin\u2026", 1500);
      setTimeout(() => {
        if (window.pywebview?.api?.switch_skin) {
          window.pywebview.api.switch_skin(_settings.skin);
        } else {
          // Fallback for dev mode (no Python)
          const base = window.location.href
            .replace(/\/ui-\d+\/index\.html([?#].*)?$/, '')
            .replace(/\/index\.html([?#].*)?$/, '');
          const newUrl = _settings.skin !== "1"
            ? base + "/ui-" + _settings.skin + "/index.html"
            : base + "/index.html";
          window.location.href = newUrl;
        }
      }, 1600);
    } else {
      showToast("Settings saved \u2713", 2000);
    }
  });

  // Click on backdrop → close
  document.getElementById("cfgOverlay")?.addEventListener("click", (e) => {
    if (e.target === e.currentTarget) _closeSettings();
  });

  // Escape: cancel capture first, then close panel
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape" || !_cfgIsOpen()) return;
    if (_cfgPendingAction) { _cancelKeybindCapture(); return; }
    _closeSettings();
  });

  // Blur slider ↔ number input (live preview)
  const blurSlider = document.getElementById("cfgBlurSlider");
  const blurNum = document.getElementById("cfgBlurNum");
  if (blurSlider && blurNum) {
    blurSlider.addEventListener("input", () => {
      const v = _cfgSliderClamp(blurSlider.value);
      blurNum.value = v.toFixed(2);
      _settings.blur = v;
      _applySettings();
    });
    blurNum.addEventListener("change", () => {
      const v = _cfgSliderClamp(blurNum.value);
      blurNum.value = v.toFixed(2);
      blurSlider.value = v;
      _settings.blur = v;
      _applySettings();
    });
    blurNum.addEventListener("focus", () => blurNum.select());
  }

  // Brightness slider ↔ number input (live preview)
  const darkSlider = document.getElementById("cfgBrightSlider");
  const darkNum = document.getElementById("cfgBrightNum");
  if (darkSlider && darkNum) {
    darkSlider.addEventListener("input", () => {
      const v = _cfgSliderClamp(darkSlider.value);
      darkNum.value = v.toFixed(2);
      _settings.brightness = v;
      _applySettings();
    });
    darkNum.addEventListener("change", () => {
      const v = _cfgSliderClamp(darkNum.value);
      darkNum.value = v.toFixed(2);
      darkSlider.value = v;
      _settings.brightness = v;
      _applySettings();
    });
    darkNum.addEventListener("focus", () => darkNum.select());
  }

  // Logo Size slider ↔ number input (live preview)
  const logoSizeSlider = document.getElementById("cfgLogoSizeSlider");
  const logoSizeNum = document.getElementById("cfgLogoSizeNum");
  if (logoSizeSlider && logoSizeNum) {
    logoSizeSlider.addEventListener("input", () => {
      const v = Math.max(0, Math.min(100, Math.round(Number(logoSizeSlider.value))));
      logoSizeNum.value = v;
      _settings.logoSize = v;
      _applySettings();
    });
    logoSizeNum.addEventListener("change", () => {
      const v = Math.max(0, Math.min(100, Math.round(Number(logoSizeNum.value))));
      logoSizeNum.value = v;
      logoSizeSlider.value = v;
      _settings.logoSize = v;
      _applySettings();
    });
    logoSizeNum.addEventListener("focus", () => logoSizeNum.select());
  }

  // Broadcast Border Brightness slider
  const bcastBrightSlider = document.getElementById("cfgBorderBrightSlider");
  const bcastBrightNum = document.getElementById("cfgBorderBrightNum");
  if (bcastBrightSlider && bcastBrightNum) {
    bcastBrightSlider.addEventListener("input", () => {
      const v = Math.max(0, Math.min(100, Math.round(Number(bcastBrightSlider.value))));
      bcastBrightNum.value = v;
      _settings.broadcastBorderBright = v;
      _applySettings();
    });
    bcastBrightNum.addEventListener("change", () => {
      const v = Math.max(0, Math.min(100, Math.round(Number(bcastBrightNum.value))));
      bcastBrightNum.value = v;
      bcastBrightSlider.value = v;
      _settings.broadcastBorderBright = v;
      _applySettings();
    });
    bcastBrightNum.addEventListener("focus", () => bcastBrightNum.select());
  }

  // Broadcast Border Thickness slider
  const bcastThickSlider = document.getElementById("cfgBorderThickSlider");
  const bcastThickNum = document.getElementById("cfgBorderThickNum");
  if (bcastThickSlider && bcastThickNum) {
    bcastThickSlider.addEventListener("input", () => {
      const v = Math.max(0, Math.min(20, Math.round(Number(bcastThickSlider.value))));
      bcastThickNum.value = v;
      _settings.broadcastBorderThick = v;
      _applySettings();
    });
    bcastThickNum.addEventListener("change", () => {
      const v = Math.max(0, Math.min(20, Math.round(Number(bcastThickNum.value))));
      bcastThickNum.value = v;
      bcastThickSlider.value = v;
      _settings.broadcastBorderThick = v;
      _applySettings();
    });
    bcastThickNum.addEventListener("focus", () => bcastThickNum.select());
  }

  // Logo Opacity slider ↔ number input (live preview)
  const logoOpacitySlider = document.getElementById("cfgLogoOpacitySlider");
  const logoOpacityNum = document.getElementById("cfgLogoOpacityNum");
  if (logoOpacitySlider && logoOpacityNum) {
    logoOpacitySlider.addEventListener("input", () => {
      const v = Math.max(0, Math.min(100, Math.round(Number(logoOpacitySlider.value))));
      logoOpacityNum.value = v;
      _settings.logoOpacity = v;
      _applySettings();
    });
    logoOpacityNum.addEventListener("change", () => {
      const v = Math.max(0, Math.min(100, Math.round(Number(logoOpacityNum.value))));
      logoOpacityNum.value = v;
      logoOpacitySlider.value = v;
      _settings.logoOpacity = v;
      _applySettings();
    });
    logoOpacityNum.addEventListener("focus", () => logoOpacityNum.select());
  }

  // Dan Display Scale slider ↔ number input (live preview)
  const danScaleSlider = document.getElementById("cfgDanScaleSlider");
  const danScaleNum = document.getElementById("cfgDanScaleNum");
  if (danScaleSlider && danScaleNum) {
    danScaleSlider.addEventListener("input", () => {
      const v = Math.max(0, Math.min(100, Math.round(Number(danScaleSlider.value))));
      danScaleNum.value = v;
      _settings.danScale = v;
      _applySettings();
    });
    danScaleNum.addEventListener("change", () => {
      const v = Math.max(0, Math.min(100, Math.round(Number(danScaleNum.value))));
      danScaleNum.value = v;
      danScaleSlider.value = v;
      _settings.danScale = v;
      _applySettings();
    });
    danScaleNum.addEventListener("focus", () => danScaleNum.select());
  }
  const skinSel = document.getElementById("cfgSkinSelect");
  if (skinSel) {
    skinSel.addEventListener("change", () => {
      _settings.skin = skinSel.value;

      // Automatically update the window size inputs in settings panel to the new skin's defaults
      let defaultW = 700;
      let defaultH = 320;
      if (_settings.skin === "4") {
        const isExp = document.getElementById("danPanel")?.classList.contains("is-expanded");
        defaultW = 284;
        defaultH = isExp ? 466 : 335;
      } else if (_settings.skin === "5") {
        const isExp = document.getElementById("danPanel")?.classList.contains("is-expanded");
        defaultW = 589;
        defaultH = isExp ? 272 : 170;
      } else if (_settings.skin === "6") {
        const isExp = document.getElementById("danPanel")?.classList.contains("is-expanded");
        defaultW = 645;
        defaultH = isExp ? 297 : 211;
      }

      const winW = document.getElementById("cfgWinWidth");
      const winH = document.getElementById("cfgWinHeight");
      if (winW) winW.value = defaultW;
      if (winH) winH.value = defaultH;

      // Clear custom dimensions so the new skin uses its native defaults/zoom on reload
      _settings.windowWidth = null;
      _settings.windowHeight = null;
      
      const ui6SettingsWrap = document.getElementById("cfgUi6Settings");
      if (ui6SettingsWrap) {
        ui6SettingsWrap.style.display = _settings.skin === "6" ? "block" : "none";
      }
    });
  }

  // Window size inputs — store values on change, apply on Save
  const winW = document.getElementById("cfgWinWidth");
  const winH = document.getElementById("cfgWinHeight");
  if (winW) winW.addEventListener("change", () => {
    _settings.windowWidth = Math.max(300, parseInt(winW.value) || 700);
  });
  if (winH) winH.addEventListener("change", () => {
    _settings.windowHeight = Math.max(80, parseInt(winH.value) || 320);
  });
  // Reset button — restore default window size
  const resetWinBtn = document.getElementById("cfgResetWinSize");
  if (resetWinBtn) resetWinBtn.addEventListener("click", () => {
    let defaultW = 700;
    let defaultH = 320;
    if (_CURRENT_SKIN === "4") {
      const isExp = document.getElementById("danPanel")?.classList.contains("is-expanded");
      defaultW = 284;
      defaultH = isExp ? 466 : 335;
    } else if (_CURRENT_SKIN === "5") {
      const isExp = document.getElementById("danPanel")?.classList.contains("is-expanded");
      defaultW = 589;
      defaultH = isExp ? 272 : 170;
      if (typeof window._resetP2ResizeStates === "function") {
        window._resetP2ResizeStates();
      }
    } else if (_CURRENT_SKIN === "6") {
      const isExp = document.getElementById("danPanel")?.classList.contains("is-expanded");
      defaultW = 645;
      defaultH = isExp ? 297 : 211;
    } else if (_CURRENT_SKIN === "8") {
      const overlayEl = document.getElementById("overlay");
      const isExp = overlayEl && (overlayEl.classList.contains("expanded") || overlayEl.classList.contains("is-expanded"));
      defaultW = 594;
      defaultH = isExp ? 234 : 138;
      document.documentElement.style.zoom = 0.94;
    }
    if (winW) winW.value = defaultW;
    if (winH) winH.value = defaultH;
    _settings.windowWidth = null;
    _settings.windowHeight = null;
    showToast(`Window size reset to default (${defaultW}×${defaultH}). Press Save to apply.`, 2500);
  });

  // Green screen toggle
  const greenScreenChk = document.getElementById("cfgGreenScreenChk");
  if (greenScreenChk) {
    greenScreenChk.addEventListener("change", () => {
      _settings.greenScreen = greenScreenChk.checked;
      _applySettings();
      void _saveSettings();
    });
  }

  // Frameless window toggle (takes effect on next restart)
  const framelessChk = document.getElementById("cfgFramelessChk");
  if (framelessChk) {
    framelessChk.addEventListener("change", () => {
      _settings.frameless = framelessChk.checked;
      void _saveSettings();
      showToast(
        framelessChk.checked
          ? "Frameless ON — restart the overlay to apply ↺"
          : "Frameless OFF — restart the overlay to apply ↺",
        3000
      );
    });
  }

  // UI 6 (Dark Vignette) specific toggles
  const ui6NoVignetteChk = document.getElementById("cfgUi6NoVignetteChk");
  if (ui6NoVignetteChk) {
    ui6NoVignetteChk.checked = _settings.ui6_no_vignette;
    ui6NoVignetteChk.addEventListener("change", () => {
      _settings.ui6_no_vignette = ui6NoVignetteChk.checked;
      _applySettings();
      void _saveSettings();
    });
  }
  const ui6SimpleModeChk = document.getElementById("cfgUi6SimpleModeChk");
  if (ui6SimpleModeChk) {
    ui6SimpleModeChk.checked = _settings.ui6_simple_mode;
    ui6SimpleModeChk.addEventListener("change", () => {
      _settings.ui6_simple_mode = ui6SimpleModeChk.checked;
      _applySettings();
      void _saveSettings();
    });
  }
  const ui6OutlinesChk = document.getElementById("cfgUi6OutlinesChk");
  if (ui6OutlinesChk) {
    ui6OutlinesChk.checked = _settings.ui6_outlines;
    ui6OutlinesChk.addEventListener("change", () => {
      _settings.ui6_outlines = ui6OutlinesChk.checked;
      _applySettings();
      void _saveSettings();
    });
  }

  if (framelessChk) framelessChk.checked = _settings.frameless;
  if (greenScreenChk) greenScreenChk.checked = _settings.greenScreen;

  // Help: Start Tutorial button
  document.getElementById("cfgTutorialBtn")?.addEventListener("click", () => {
    _closeSettings();
    setIntroStage("whats_new");
  });
}

/* ── Start ───────────────────────────────────────────────────────── */

// ── Density Graph (ui-3 skin) ──────────────────────────────────────────

let _strainValues = null;
let _strainTimes = null;
let _strainDurationMs = 0;
let _strainLastProgressPx = -1;
let _strainPreRendered = null;

function _storeStrainData(strainGraph, durationS) {
  _strainValues = strainGraph.values || null;
  _strainTimes = strainGraph.times || null;
  _strainDurationMs = Math.max(durationS * 1000, (_strainTimes && _strainTimes.length ? _strainTimes[_strainTimes.length - 1] : 0));
  _strainLastProgressPx = -1;
  _strainPreRendered = null;
  _preRenderDensityGraph();
}

function _preRenderDensityGraph() {
  const canvas = document.getElementById("densityGraph");
  if (!canvas || !_strainValues || !_strainValues.length) return;

  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  const W = Math.round(rect.width * dpr);
  const H = Math.round(rect.height * dpr);
  if (W <= 0 || H <= 0) return;

  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, W, H);

  // Read dan color from CSS variable (set by _applyDanTheme)
  const style = getComputedStyle(document.documentElement);
  const primary = style.getPropertyValue("--dan-primary").trim() || "rgb(100,160,255)";
  // Convert "rgb(r,g,b)" → components for alpha variants
  const rgbMatch = primary.match(/(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/);
  const [r, g, b] = rgbMatch ? [rgbMatch[1], rgbMatch[2], rgbMatch[3]] : ["100", "160", "255"];

  // Background
  ctx.fillStyle = "rgba(0,0,0,0)";
  ctx.fillRect(0, 0, W, H);

  const vals = _strainValues;
  const maxVal = Math.max(...vals, 1);
  const padX = 4;
  const padY = 2;
  const plotW = W - padX * 2;
  const plotH = H - padY * 2;

  // Build polygon points
  const n = vals.length;
  const pts = [];
  for (let i = 0; i < n; i++) {
    const x = padX + (i / (n - 1)) * plotW;
    const y = H - padY - (vals[i] / maxVal) * plotH;
    pts.push([x, y]);
  }

  // Store pre-rendered state (includes color components for progress redraws)
  _strainPreRendered = { W, H, pts, ctx, r, g, b };

  // Draw unplayed version: very subtle fill + dim line using dan color
  ctx.fillStyle = `rgba(${r},${g},${b},0.05)`;
  ctx.strokeStyle = `rgba(${r},${g},${b},0.18)`;
  ctx.lineWidth = 1.5 * dpr;
  ctx.beginPath();
  ctx.moveTo(padX, H - padY);
  for (let i = 0; i < n; i++) {
    ctx.lineTo(pts[i][0], pts[i][1]);
  }
  ctx.lineTo(pts[n - 1][0], H - padY);
  ctx.closePath();
  ctx.fill();
  ctx.beginPath();
  for (let i = 0; i < n; i++) {
    if (i === 0) ctx.moveTo(pts[i][0], pts[i][1]);
    else ctx.lineTo(pts[i][0], pts[i][1]);
  }
  ctx.stroke();

  _strainLastProgressPx = -1;
}

function _updateDensityProgress(currentMs) {
  if (!_strainPreRendered || !_strainValues || !_strainDurationMs) return;

  const canvas = document.getElementById("densityGraph");
  if (!canvas) return;

  const { W, H, pts, ctx, r, g, b } = _strainPreRendered;
  const frac = _strainDurationMs > 0 ? Math.min(1, Math.max(0, currentMs / _strainDurationMs)) : 0;
  const splitX = Math.round(pts[0][0] + frac * (pts[pts.length - 1][0] - pts[0][0]));
  if (splitX === _strainLastProgressPx) return;
  _strainLastProgressPx = splitX;

  // Clear and redraw base (unplayed — subtle)
  ctx.clearRect(0, 0, W, H);

  ctx.fillStyle = `rgba(${r},${g},${b},0.05)`;
  ctx.strokeStyle = `rgba(${r},${g},${b},0.18)`;
  ctx.lineWidth = 1.5 * (window.devicePixelRatio || 1);
  ctx.beginPath();
  ctx.moveTo(pts[0][0], H - 2);
  for (let i = 0; i < pts.length; i++) {
    ctx.lineTo(pts[i][0], pts[i][1]);
  }
  ctx.lineTo(pts[pts.length - 1][0], H - 2);
  ctx.closePath();
  ctx.fill();
  ctx.beginPath();
  for (let i = 0; i < pts.length; i++) {
    if (i === 0) ctx.moveTo(pts[i][0], pts[i][1]);
    else ctx.lineTo(pts[i][0], pts[i][1]);
  }
  ctx.stroke();

  // Played overlay (left of split) — bright dan color with gradient fill
  if (splitX > pts[0][0]) {
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, 0, splitX, H);
    ctx.clip();

    // Vertical gradient fill: bright at top, fades to transparent at bottom
    const grad = ctx.createLinearGradient(0, 0, 0, H);
    grad.addColorStop(0, `rgba(${r},${g},${b},0.55)`);
    grad.addColorStop(1, `rgba(${r},${g},${b},0.04)`);

    ctx.fillStyle = grad;
    ctx.strokeStyle = `rgba(${r},${g},${b},0.8)`;
    ctx.lineWidth = 2 * (window.devicePixelRatio || 1);

    ctx.beginPath();
    ctx.moveTo(pts[0][0], H - 2);
    for (let i = 0; i < pts.length; i++) {
      ctx.lineTo(pts[i][0], pts[i][1]);
    }
    ctx.lineTo(pts[pts.length - 1][0], H - 2);
    ctx.closePath();
    ctx.fill();

    ctx.beginPath();
    for (let i = 0; i < pts.length; i++) {
      if (i === 0) ctx.moveTo(pts[i][0], pts[i][1]);
      else ctx.lineTo(pts[i][0], pts[i][1]);
    }
    ctx.stroke();
    ctx.restore();
  }

  // Progress line — white with a subtle dan-color glow
  if (splitX > pts[0][0]) {
    ctx.save();
    ctx.shadowColor = `rgba(${r},${g},${b},0.8)`;
    ctx.shadowBlur = 6 * (window.devicePixelRatio || 1);
    ctx.strokeStyle = "rgba(255,255,255,0.75)";
    ctx.lineWidth = 1.5 * (window.devicePixelRatio || 1);
    ctx.beginPath();
    ctx.moveTo(splitX, 2);
    ctx.lineTo(splitX, H - 2);
    ctx.stroke();
    ctx.restore();
  }
}


(async () => {
  await _loadSettings();
  _layoutMode = _settings.layout || "complete";
  _applySettings();
  let w = _settings.windowWidth;
  let h = _settings.windowHeight;
  const isLegacyDefault = (w === 700 && h === 320) || (w === 860 && h === 320);
  if (isLegacyDefault && (_CURRENT_SKIN === "4" || _CURRENT_SKIN === "5" || _CURRENT_SKIN === "6" || _CURRENT_SKIN === "8")) {
    w = null;
    h = null;
  }
  if (_CURRENT_SKIN === "4") {
    document.documentElement.style.zoom = 0.61;
  } else if (_CURRENT_SKIN === "5") {
    document.documentElement.style.zoom = 0.75;
  } else if (_CURRENT_SKIN === "6") {
    document.documentElement.style.zoom = 0.73;
  } else if (_CURRENT_SKIN === "8") {
    document.documentElement.style.zoom = 0.94;
  }
  if (w && h && window.pywebview?.api?.set_window_size) {
    window.pywebview.api.set_window_size(w, h);
  } else if (!w && !h && window.pywebview?.api?.set_window_size) {
    if (_CURRENT_SKIN === "4") {
      window.pywebview.api.set_window_size(284, 335);
    } else if (_CURRENT_SKIN === "5") {
      window.pywebview.api.set_window_size(589, 170);
    } else if (_CURRENT_SKIN === "6") {
      window.pywebview.api.set_window_size(645, 211);
    } else if (_CURRENT_SKIN === "8") {
      window.pywebview.api.set_window_size(594, 234);
    } else {
      window.pywebview.api.set_window_size(700, 320);
    }
  }
  _applyLayoutMode(true);
  _initCfgListeners();
  boot();

  // Dynamic resize intelligence for Skin 5 (Broadcast Bar)
  if (_CURRENT_SKIN === "5") {
    document.documentElement.style.setProperty("--p2-left-width", "220px");
    document.documentElement.style.setProperty("--p2-bar-height", "131px");
    document.documentElement.style.setProperty("--p2-drawer-height", "180px");
  }

  let _p2PrevWidth = window.innerWidth;
  let _p2PrevHeight = window.innerHeight;
  let _p2PrevScreenX = window.screenX ?? window.screenLeft ?? 0;
  let _p2PrevScreenY = window.screenY ?? window.screenTop ?? 0;

  let _p2LeftWidth = 220;
  let _p2BarHeight = 131;
  let _p2DrawerHeight = 180;

  window._resetP2ResizeStates = () => {
    _p2LeftWidth = 220;
    _p2BarHeight = 131;
    _p2DrawerHeight = 180;
    document.documentElement.style.setProperty("--p2-left-width", "220px");
    document.documentElement.style.setProperty("--p2-bar-height", "131px");
    document.documentElement.style.setProperty("--p2-drawer-height", "180px");
  };

  window.addEventListener("resize", () => {
    if (_CURRENT_SKIN !== "5") return;
    
    const curW = window.innerWidth;
    const curH = window.innerHeight;
    const curX = window.screenX ?? window.screenLeft ?? 0;
    const curY = window.screenY ?? window.screenTop ?? 0;

    if (window._ignoreNextP2Resize) {
      window._ignoreNextP2Resize = false;
      _p2PrevWidth = curW;
      _p2PrevHeight = curH;
      _p2PrevScreenX = curX;
      _p2PrevScreenY = curY;
      return;
    }

    const panel = document.getElementById("danPanel");
    const isExpanded = panel && panel.classList.contains("is-expanded");

    const wDiff = curW - _p2PrevWidth;
    const hDiff = curH - _p2PrevHeight;
    const xDiff = curX - _p2PrevScreenX;
    const yDiff = curY - _p2PrevScreenY;

    // 1. Horizontal resize
    if (wDiff !== 0) {
      if (Math.abs(xDiff) > 1) {
        // Dragging left border -> resize left panel only
        _p2LeftWidth = Math.max(120, _p2LeftWidth + wDiff);
        document.documentElement.style.setProperty("--p2-left-width", _p2LeftWidth + "px");
      }
      // Dragging right border -> right panel stretches/shrinks automatically due to flex: 1!
    }

    // 2. Vertical resize
    if (hDiff !== 0) {
      if (isExpanded) {
        if (Math.abs(yDiff) > 1) {
          // Dragging top border -> resize top bar only
          _p2BarHeight = Math.max(80, _p2BarHeight + hDiff);
          document.documentElement.style.setProperty("--p2-bar-height", _p2BarHeight + "px");
        } else {
          // Dragging bottom border -> resize expanded drawer only
          _p2DrawerHeight = Math.max(60, _p2DrawerHeight + hDiff);
          document.documentElement.style.setProperty("--p2-drawer-height", _p2DrawerHeight + "px");
        }
      }
      // Collapsed mode -> standard auto-scaling handles height changes!
    }

    _p2PrevWidth = curW;
    _p2PrevHeight = curH;
    _p2PrevScreenX = curX;
    _p2PrevScreenY = curY;
  });
})();

// ── Export Chart Logic ───────────────────────────────────────────────────────

