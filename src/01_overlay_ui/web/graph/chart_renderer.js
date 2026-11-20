function renderExportChart(payload) {
  try {
    console.log("[CHART] renderExportChart called");
    const canvas = document.createElement("canvas");
    canvas.width = 1800;
    canvas.height = 980;
    const ctx = canvas.getContext("2d");
    const W = canvas.width, H = canvas.height;

    function runDraw(bgImg, bannerImg) {
      try {
        ctx.clearRect(0, 0, W, H);

        // ── Visual & Logical Helpers ─────────────────────────────────────────
        function pRgb(s) {
          const m = s.match(/(\d+),\s*(\d+),\s*(\d+)/);
          return m ? [+m[1], +m[2], +m[3]] : [120, 160, 255];
        }

        function fmtT(s) {
          const sec = Math.max(0, Math.floor(s || 0));
          return `${Math.floor(sec / 60).toString().padStart(2, "0")}:${(sec % 60).toString().padStart(2, "0")}`;
        }

        function fmtInt(n) {
          return Math.round(n || 0).toLocaleString("en-US");
        }

        function chamferRect(c, x, y, w, h, cut) {
          const rad = Math.min(cut, w / 2, h / 2);
          c.beginPath();
          c.moveTo(x + rad, y);
          c.lineTo(x + w - rad, y);
          c.lineTo(x + w, y + rad);
          c.lineTo(x + w, y + h - rad);
          c.lineTo(x + w - rad, y + h);
          c.lineTo(x + rad, y + h);
          c.lineTo(x, y + h - rad);
          c.lineTo(x, y + rad);
          c.closePath();
        }

        function drawCornerTicks(c, x, y, w, h, len, color, lineW = 1.5) {
          c.save();
          c.strokeStyle = color;
          c.lineWidth = lineW;
          c.beginPath();
          c.moveTo(x, y + len); c.lineTo(x, y); c.lineTo(x + len, y);
          c.moveTo(x + w - len, y); c.lineTo(x + w, y); c.lineTo(x + w, y + len);
          c.moveTo(x + w, y + h - len); c.lineTo(x + w, y + h); c.lineTo(x + w - len, y + h);
          c.moveTo(x + len, y + h); c.lineTo(x, y + h); c.lineTo(x, y + h - len);
          c.stroke();
          c.restore();
        }

        function truncateText(c, text, maxWidth) {
          const strIn = String(text || "");
          if (maxWidth <= 0) return "";
          if (c.measureText(strIn).width <= maxWidth) return strIn;
          let str = strIn;
          while (str.length > 0 && c.measureText(str + "...").width > maxWidth) {
            str = str.slice(0, -1);
          }
          return str + "...";
        }

        const FONT_DISPLAY = "'Bahnschrift', 'DIN Alternate', 'Franklin Gothic Medium', 'Arial Narrow', sans-serif";
        const FONT_MONO = "'JetBrains Mono', 'Consolas', 'Lucida Console', monospace";
        const FONT_UI = "'Segoe UI', 'Helvetica Neue', sans-serif";

        const COL_BG = "#080A0E";
        const COL_BORDER = "rgba(255, 255, 255, 0.16)";
        const COL_HAIRLINE = "rgba(255, 255, 255, 0.08)";
        const COL_INK = "#F4F6F8";
        const COL_MUTED = "#94A3B8";
        const COL_DIM = "#5A6578";
        const COL_AMBER = "#F5A623";
        const COL_CYAN = "#00E5CC";
        const COL_CRIMSON = "#FF334B";

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
          "Alpha": ["rgb(70,60,180)", "rgb(220,65,80)", "rgb(245,225,45)"],
          "Beta": ["rgb(255,245,180)", "rgb(255,165,0)"],
          "Gamma": ["rgb(255,0,0)", "rgb(0,60,255)", "rgb(0,255,90)"],
          "Delta": ["rgb(95,60,125)", "rgb(215,130,50)"],
          "Epsilon": ["rgb(215,45,95)", "rgb(30,80,150)", "rgb(245,240,215)"],
          "Zeta": ["rgb(240,130,105)", "rgb(130,190,225)"],
          "Eta": ["rgb(145,0,0)", "rgb(200,80,70)"],
          "Theta": ["rgb(105,5,5)", "rgb(170,65,55)"],
          "Iota": ["rgb(75,10,10)", "rgb(145,50,50)"],
          "Kappa": ["rgb(125,125,125)", "rgb(190,190,200)"]
        };

        const GREEK_SYMBOLS = {
          "Alpha": "α", "Beta": "β", "Gamma": "γ", "Delta": "δ",
          "Epsilon": "ε", "Zeta": "ζ", "Eta": "η", "Theta": "θ",
          "Iota": "ι", "Kappa": "κ",
          "1st": "1", "2nd": "2", "3rd": "3", "4th": "4", "5th": "5",
          "6th": "6", "7th": "7", "8th": "8", "9th": "9", "10th": "10"
        };

        function getDanPalette(danShort) {
          if (!danShort) return ["rgb(245,166,35)", "rgb(245,196,28)"];
          const clean = danShort.trim();
          for (const [k, pal] of Object.entries(DAN_PALETTES)) {
            if (clean.toLowerCase() === k.toLowerCase() || clean.toLowerCase().startsWith(k.toLowerCase())) {
              return pal;
            }
          }
          return ["rgb(245,166,35)", "rgb(245,196,28)"];
        }

        function getDanSymbol(danShort) {
          if (!danShort) return "";
          const clean = danShort.trim();
          for (const [k, sym] of Object.entries(GREEK_SYMBOLS)) {
            if (clean.toLowerCase() === k.toLowerCase() || clean.toLowerCase().startsWith(k.toLowerCase())) {
              return sym;
            }
          }
          const matchNum = clean.match(/^(\d+)/);
          if (matchNum) return matchNum[1];
          return clean.slice(0, 2).toUpperCase();
        }

        function drawCard(x, y, w, h, cornerTickCol = null) {
          ctx.save();
          ctx.shadowColor = "rgba(0, 0, 0, 0.40)";
          ctx.shadowBlur = 18;
          ctx.shadowOffsetY = 4;
          chamferRect(ctx, x, y, w, h, 6);
          ctx.fillStyle = "rgba(10, 13, 19, 0.82)";
          ctx.fill();
          ctx.restore();

          chamferRect(ctx, x, y, w, h, 6);
          ctx.strokeStyle = COL_BORDER;
          ctx.lineWidth = 1;
          ctx.stroke();

          if (cornerTickCol) {
            drawCornerTicks(ctx, x, y, w, h, 8, cornerTickCol, 1.2);
          }
        }

        const CS = [
          [0, [24, 92, 122]],
          [4, [16, 152, 173]],
          [8, [0, 210, 190]],
          [12, [64, 212, 110]],
          [16, [168, 224, 48]],
          [20, [245, 196, 28]],
          [24, [250, 140, 22]],
          [30, [245, 78, 32]],
          [38, [235, 28, 62]],
          [48, [255, 85, 115]],
          [60, [255, 230, 215]]
        ];

        function mapColor(v, a) {
          v = Math.max(0, v);
          for (let i = 0; i < CS.length - 1; i++) {
            if (v <= CS[i + 1][0]) {
              const t = (v - CS[i][0]) / Math.max(1e-6, CS[i + 1][0] - CS[i][0]);
              const r = Math.round(CS[i][1][0] + (CS[i + 1][1][0] - CS[i][1][0]) * t);
              const g = Math.round(CS[i][1][1] + (CS[i + 1][1][1] - CS[i][1][1]) * t);
              const b = Math.round(CS[i][1][2] + (CS[i + 1][1][2] - CS[i][1][2]) * t);
              return a !== undefined ? `rgba(${r},${g},${b},${a})` : `rgb(${r},${g},${b})`;
            }
          }
          const last = CS[CS.length - 1][1];
          return a !== undefined ? `rgba(${last[0]},${last[1]},${last[2]},${a})` : `rgb(${last[0]},${last[1]},${last[2]})`;
        }

        function buildPixelProfile(npsData, width) {
          if (!npsData.length || width <= 0) return [];
          const tS = npsData[0][0], tE = npsData[npsData.length - 1][0], span = Math.max(1, tE - tS);
          const prof = new Float64Array(width), seen = new Uint8Array(width);
          for (const [t, nps] of npsData) {
            let x = Math.round(((t - tS) / span) * (width - 1));
            x = Math.max(0, Math.min(width - 1, x));
            if (!seen[x] || nps > prof[x]) { prof[x] = nps; seen[x] = 1; }
          }
          let last = 0; for (let i = 0; i < width; i++) { if (seen[i]) last = prof[i]; else prof[i] = last; }
          let nxt = 0; for (let i = width - 1; i >= 0; i--) { if (seen[i]) nxt = prof[i]; else if (prof[i] <= 0) prof[i] = nxt; }
          return prof;
        }

        function smoothProfile(vals, radius) {
          if (!vals.length) return [];
          radius = Math.max(1, radius);
          const n = vals.length, out = new Float64Array(n);
          const pfx = new Float64Array(n + 1);
          for (let i = 0; i < n; i++) pfx[i + 1] = pfx[i] + vals[i];
          for (let i = 0; i < n; i++) {
            const lo = Math.max(0, i - radius), hi = Math.min(n, i + radius + 1);
            out[i] = (pfx[hi] - pfx[lo]) / (hi - lo);
          }
          return out;
        }

        function resolveModifiers(payload, meta, isEtterna) {
          const rawRate = String(payload.rate_label || meta.rate_label || "").trim();
          const rawMods = payload.mods || meta.mods || [];
          const modArray = Array.isArray(rawMods)
            ? rawMods.map(m => String(m).toUpperCase())
            : String(rawMods).split(/[,+\s]+/).filter(Boolean).map(m => m.toUpperCase());

          const rateMatch = rawRate.match(/(\d+(?:\.\d+)?)/);
          const rateNum = rateMatch ? parseFloat(rateMatch[1]) : 1.0;
          const chips = [];

          if (isEtterna) {
            if (Math.abs(rateNum - 1.0) > 0.005 || (rawRate && !rawRate.includes("1.00"))) {
              const lbl = rawRate ? rawRate.toUpperCase() : `${rateNum.toFixed(2)}X`;
              chips.push({
                code: lbl.includes("RATE") ? lbl : `${lbl} RATE`,
                bg: "#F5A623", fg: "#080A0D", border: "#F5A623", bold: true
              });
            }
          } else {
            const hasNC = modArray.includes("NC") || rawRate.toUpperCase().includes("NC");
            const hasExplicitModPrefix = /^(DT|NC|HT)\b/i.test(rawRate);

            if (hasExplicitModPrefix) {
              const isHT = /^HT/i.test(rawRate);
              chips.push({
                code: rawRate.toUpperCase(),
                bg: isHT ? "#00E5CC" : "#F5A623",
                fg: "#080A0D",
                border: isHT ? "#00E5CC" : "#F5A623",
                bold: true
              });
            } else if (rateNum > 1.005) {
              const prefix = hasNC ? "NC" : "DT";
              chips.push({
                code: `${prefix} ${rateNum.toFixed(2)}X`,
                bg: "#F5A623", fg: "#080A0D", border: "#F5A623", bold: true
              });
            } else if (rateNum < 0.995) {
              chips.push({
                code: `HT ${rateNum.toFixed(2)}X`,
                bg: "#00E5CC", fg: "#080A0D", border: "#00E5CC", bold: true
              });
            }

            modArray.forEach(m => {
              if (m === "NC" || m === "DT" || m === "HT" || m === "NM") return;
              if (m === "EZ") chips.push({ code: "EZ", bg: "rgba(64, 212, 110, 0.20)", fg: "#40D46E", border: "#40D46E", bold: true });
              else if (m === "HD") chips.push({ code: "HD", bg: "rgba(245, 196, 28, 0.20)", fg: "#F5C41C", border: "#F5C41C", bold: true });
              else if (m === "HR") chips.push({ code: "HR", bg: "rgba(255, 51, 75, 0.20)", fg: "#FF334B", border: "#FF334B", bold: true });
              else chips.push({ code: m, bg: "rgba(255, 255, 255, 0.10)", fg: "#FFFFFF", border: "rgba(255, 255, 255, 0.28)" });
            });
          }
          return { chips, rateNum };
        }

        // ── 1. Fondo Atmosférico de Alto Contraste + Micro-Rejilla 30px ─────
        ctx.fillStyle = COL_BG;
        ctx.fillRect(0, 0, W, H);

        const hasBg = !!(bgImg && (bgImg.naturalWidth > 0 || bgImg.width > 0));
        if (hasBg) {
          const imgW = bgImg.naturalWidth || bgImg.width;
          const imgH = bgImg.naturalHeight || bgImg.height;
          const scale = Math.max(W / imgW, H / imgH);
          const sw = W / scale, sh = H / scale;
          const sx = (imgW - sw) / 2, sy = (imgH - sh) / 2;

          ctx.drawImage(bgImg, sx, sy, sw, sh, 0, 0, W, H);

          const darkOverlay = ctx.createLinearGradient(0, 0, 0, H);
          darkOverlay.addColorStop(0, "rgba(7, 9, 14, 0.58)");
          darkOverlay.addColorStop(0.45, "rgba(8, 11, 16, 0.66)");
          darkOverlay.addColorStop(1, "rgba(6, 8, 12, 0.80)");
          ctx.fillStyle = darkOverlay;
          ctx.fillRect(0, 0, W, H);

          const vig = ctx.createRadialGradient(W / 2, H * 0.4, W * 0.2, W / 2, H * 0.5, W * 0.75);
          vig.addColorStop(0, "rgba(0, 0, 0, 0)");
          vig.addColorStop(1, "rgba(0, 0, 0, 0.48)");
          ctx.fillStyle = vig;
          ctx.fillRect(0, 0, W, H);
        }

        // Micro-rejilla arquitectónica de 30px
        ctx.save();
        ctx.strokeStyle = "rgba(255, 255, 255, 0.025)";
        ctx.lineWidth = 1;
        for (let gx = 24; gx < W; gx += 30) {
          ctx.beginPath(); ctx.moveTo(gx, 0); ctx.lineTo(gx, H); ctx.stroke();
        }
        for (let gy = 24; gy < H; gy += 30) {
          ctx.beginPath(); ctx.moveTo(0, gy); ctx.lineTo(W, gy); ctx.stroke();
        }
        ctx.restore();

        // ── 2. Recepción de Datos ────────────────────────────────────────────
        const meta = payload.parsed_meta || {};
        const bpm = Math.round(meta.bpm || 0);
        const od = meta.od ? meta.od.toFixed(1) : "0.0";
        const kc = 4;
        const { nps_data, density_meta = {} } = payload;
        if (!nps_data || !nps_data.length) return;

        let maxY = 10.0, pkY = 0.0;
        let sumY = 0.0, sumY2 = 0.0;
        let pkTime = nps_data[0][0];

        nps_data.forEach(d => {
          if (d[1] > pkY) { pkY = d[1]; pkTime = d[0]; }
          sumY += d[1];
          sumY2 += d[1] * d[1];
          if (d[1] > maxY) maxY = d[1];
        });

        let dominantNps = payload.dominant_nps || 0;
        if (!dominantNps || dominantNps <= 0) {
          dominantNps = sumY > 0 ? (sumY2 / sumY) : 0;
        }
        const avgNps = nps_data.length > 0 ? (sumY / nps_data.length) : 0;

        const rawMaxY = Math.max(10, pkY * 1.10);
        const yStep = rawMaxY > 30 ? 10 : 5;
        maxY = Math.ceil(rawMaxY / yStep) * yStep;

        const { artist = "", title = "", version = "", creator = "", format = "" } = meta;
        const pack = (payload.pack || meta.pack || "").trim();
        const notes = meta.note_count || 0, lns = meta.ln_count || 0, drT = meta.drain_time_s || 0;
        const durSec = meta.total_time_ms ? Math.round(meta.total_time_ms / 1000) : drT;
        const isEtterna = !!(payload.is_etterna || format === "sm" || format === "ssc");

        const danShort = payload.dan_short || "";
        const danSub = payload.dan_sublevel || "";
        const fam = payload.family || "";
        const overall_msd = payload.overall_msd || 0.0;

        const { chips: modChips } = resolveModifiers(payload, meta, isEtterna);

        // ── 3. Geometría Simétrica Limpia (1800 x 980) ───────────────────────
        const MX = 36, MY = 32, GAP = 20;
        const TOP_Y = MY;                      // 32
        const TOP_H = 336;

        const LEFT_X = MX;                     // 36
        const LEFT_W = 1120;
        const RIGHT_X = LEFT_X + LEFT_W + GAP; // 1176
        const RIGHT_W = W - MX - RIGHT_X;      // 588

        const GRAPH_X = MX;                    // 36
        const GRAPH_Y = TOP_Y + TOP_H + GAP;   // 388
        const GRAPH_W = W - MX * 2;            // 1728
        const GRAPH_H = 546;                   // bottom: 934

        // Sismógrafo centrado con amplia altura vertical simétrica
        const cX = GRAPH_X + 64;               // 100
        const cW = GRAPH_W - 148;              // 1580
        const cY = GRAPH_Y + 70;               // 458
        const cH = 416;                        // Altura generosa sin recortar
        const bot = cY + cH;                   // 874

        const prof = buildPixelProfile(nps_data, cW);
        const sProfRaw = smoothProfile(prof, Math.max(3, Math.floor(cW / 260)));

        let maxS = 0, maxSIdx = 0;
        for (let i = 0; i < cW; i++) {
          if (sProfRaw[i] > maxS) { maxS = sProfRaw[i]; maxSIdx = i; }
        }

        const sProf = new Float64Array(cW);
        const scaleS = (pkY > 0 && maxS > 0) ? (pkY / maxS) : 1.0;
        for (let i = 0; i < cW; i++) { sProf[i] = sProfRaw[i] * scaleS; }

        const tStart = nps_data[0][0], tEnd = nps_data[nps_data.length - 1][0];
        const spanS = Math.max(1, (tEnd - tStart) / 1000);

        let hardSecs = 0;
        for (let i = 0; i < cW; i++) {
          if (sProf[i] >= dominantNps && sProf[i] >= 5.0) {
            hardSecs += (spanS / cW);
          }
        }
        const hardPct = Math.round((hardSecs / Math.max(1, spanS)) * 100);
        const hardTimeStr = fmtT(Math.round(hardSecs));
        const peakTimeSec = Math.max(0, (pkTime - nps_data[0][0]) / 1000);

        // Paleta y Símbolo del Dan
        const danPal = getDanPalette(danShort);
        const danSym = getDanSymbol(danShort);

        // ── 4. TARJETA A (Izquierda): Identidad del Mapa + Stats Grandes ──────
        drawCard(LEFT_X, TOP_Y, LEFT_W, TOP_H, COL_AMBER);

        const PAD = 24;
        const MEDIA_X = LEFT_X + PAD;          // 60
        const MEDIA_Y = TOP_Y + PAD;          // 56
        const MEDIA_H = 150;
        const hasBanner = !!(bannerImg && (bannerImg.naturalWidth > 0 || bannerImg.width > 0));
        let mediaBoxW = 0;

        if (hasBanner) {
          // Etterna banner con proporción real
          const bImgW = bannerImg.naturalWidth || bannerImg.width;
          const bImgH = bannerImg.naturalHeight || bannerImg.height;
          const ratio = bImgW / Math.max(1, bImgH);
          const maxBW = 280, maxBH = MEDIA_H;

          let bW = maxBW, bH = Math.round(maxBW / ratio);
          if (bH > maxBH) {
            bH = maxBH;
            bW = Math.round(maxBH * ratio);
          }
          bW = Math.max(96, Math.min(maxBW, bW));
          bH = Math.max(60, Math.min(maxBH, bH));
          const bY = MEDIA_Y + Math.round((MEDIA_H - bH) / 2);

          ctx.fillStyle = "#05070A";
          ctx.fillRect(MEDIA_X, bY, bW, bH);
          ctx.drawImage(bannerImg, 0, 0, bImgW, bImgH, MEDIA_X, bY, bW, bH);

          // Marca de agua sutil en la esquina del banner si hay Dan
          if (danSym) {
            ctx.save();
            ctx.beginPath();
            ctx.rect(MEDIA_X, bY, bW, bH);
            ctx.clip();
            ctx.font = `900 68px ${FONT_DISPLAY}`;
            ctx.textAlign = "right";
            ctx.fillStyle = danPal[0].replace("rgb", "rgba").replace(")", ", 0.22)");
            ctx.fillText(danSym, MEDIA_X + bW - 6, bY + bH - 4);
            ctx.restore();
          }

          ctx.strokeStyle = COL_BORDER;
          ctx.lineWidth = 1.5;
          ctx.strokeRect(MEDIA_X, bY, bW, bH);
          drawCornerTicks(ctx, MEDIA_X, bY, bW, bH, 7, COL_AMBER, 1.5);

          mediaBoxW = bW;
        } else if (hasBg) {
          // osu!mania portada nítida con marca de agua parcial de Dan en la esquina
          const vW = 246, vH = MEDIA_H;
          const iW = bgImg.naturalWidth || bgImg.width;
          const iH = bgImg.naturalHeight || bgImg.height;
          const sc = Math.max(vW / iW, vH / iH);
          const sw = vW / sc, sh = vH / sc;

          ctx.save();
          chamferRect(ctx, MEDIA_X, MEDIA_Y, vW, vH, 4);
          ctx.clip();
          ctx.drawImage(bgImg, (iW - sw) / 2, (iH - sh) / 2, sw, sh, MEDIA_X, MEDIA_Y, vW, vH);

          // Ícono/símbolo del Dan parcial en la esquina (estilo skin modern)
          if (danSym) {
            ctx.font = `900 76px ${FONT_DISPLAY}`;
            ctx.textAlign = "right";
            const wmGrad = ctx.createLinearGradient(MEDIA_X + vW - 70, MEDIA_Y + vH - 70, MEDIA_X + vW, MEDIA_Y + vH);
            wmGrad.addColorStop(0, danPal[0].replace("rgb", "rgba").replace(")", ", 0.32)"));
            wmGrad.addColorStop(1, danPal[danPal.length - 1].replace("rgb", "rgba").replace(")", ", 0.18)"));
            ctx.fillStyle = wmGrad;
            ctx.fillText(danSym, MEDIA_X + vW - 4, MEDIA_Y + vH - 4);
          }
          ctx.restore();

          chamferRect(ctx, MEDIA_X, MEDIA_Y, vW, vH, 4);
          ctx.strokeStyle = COL_BORDER;
          ctx.lineWidth = 1.5;
          ctx.stroke();
          drawCornerTicks(ctx, MEDIA_X, MEDIA_Y, vW, vH, 7, COL_CYAN, 1.5);

          mediaBoxW = vW;
        }

        const hasDan = !!(danShort && danShort.trim());
        const danFullText = `${(danShort || "").toUpperCase()}${danSub ? " " + danSub.toUpperCase() : ""}`;

        // Marca de Agua Monumental (Ambient Backdrop en Card A sin marcos ni cajas)
        if (hasDan) {
          ctx.save();
          const cx = LEFT_X + LEFT_W - PAD - 105;
          const cy = MEDIA_Y + 72;

          // Resplandor radial de fondo
          const bgGlow = ctx.createRadialGradient(cx, cy, 10, cx, cy, 140);
          bgGlow.addColorStop(0, danPal[0].replace("rgb", "rgba").replace(")", ", 0.18)"));
          bgGlow.addColorStop(1, "rgba(8, 11, 16, 0)");
          ctx.fillStyle = bgGlow;
          ctx.beginPath();
          ctx.arc(cx, cy, 140, 0, Math.PI * 2);
          ctx.fill();

          // Glifo monumental transparente
          if (danSym) {
            const wmGrad = ctx.createLinearGradient(0, cy - 70, 0, cy + 90);
            wmGrad.addColorStop(0, danPal[0].replace("rgb", "rgba").replace(")", ", 0.22)"));
            wmGrad.addColorStop(1, danPal[danPal.length - 1].replace("rgb", "rgba").replace(")", ", 0.05)"));
            ctx.font = `900 170px ${FONT_DISPLAY}`;
            ctx.textAlign = "center";
            ctx.fillStyle = wmGrad;
            ctx.fillText(danSym, cx, cy + 58);
          }

          // Tipografía en primer plano (limpia, flotante, sin cajas)
          ctx.textAlign = "center";
          ctx.font = `700 10px ${FONT_MONO}`;
          ctx.fillStyle = "#94A3B8";
          ctx.fillText("ESTIMATED TIER", cx, cy - 14);

          const textGrad = ctx.createLinearGradient(cx - 70, 0, cx + 70, 0);
          textGrad.addColorStop(0, danPal[0]);
          textGrad.addColorStop(1, danPal[danPal.length - 1]);
          ctx.font = `900 24px ${FONT_DISPLAY}`;
          ctx.fillStyle = textGrad;
          ctx.shadowColor = danPal[0];
          ctx.shadowBlur = 12;
          ctx.fillText(danFullText, cx, cy + 18);
          ctx.shadowBlur = 0;

          // Acento en la base
          ctx.fillStyle = textGrad;
          ctx.fillRect(cx - 24, cy + 28, 48, 2);

          ctx.restore();
        }

        const infoX = mediaBoxW > 0 ? (MEDIA_X + mediaBoxW + 24) : MEDIA_X;
        const maxInfoX = hasDan ? (LEFT_X + LEFT_W - PAD - 225) : (LEFT_X + LEFT_W - PAD);
        const infoW = maxInfoX - infoX;

        // Fila 1: Badges limpios (sin "1.00X NM" y sin "CLASS //", solo el tipo de mapa)
        const badges = [
          {
            code: isEtterna ? `ETTERNA ${kc}K` : `OSU!MANIA ${kc}K`,
            bg: "rgba(255, 255, 255, 0.06)", fg: "#CBD5E1", border: "rgba(255, 255, 255, 0.16)"
          },
          ...modChips
        ];

        if (fam && fam.trim()) {
          badges.push({
            code: fam.toUpperCase(),
            bg: "rgba(0, 229, 204, 0.16)", fg: COL_CYAN, border: "rgba(0, 229, 204, 0.50)", bold: true
          });
        }

        let bx = infoX;
        const by = MEDIA_Y;
        const bh = 24;
        badges.forEach(b => {
          ctx.font = `700 11px ${FONT_MONO}`;
          const bw = Math.ceil(ctx.measureText(b.code).width + 16);
          if (bx + bw <= infoX + infoW) {
            chamferRect(ctx, bx, by, bw, bh, 4);
            ctx.fillStyle = b.bg;
            ctx.fill();
            ctx.strokeStyle = b.border;
            ctx.lineWidth = 1;
            ctx.stroke();

            ctx.textAlign = "center";
            ctx.fillStyle = b.fg;
            ctx.fillText(b.code, bx + bw / 2, by + 16);
            bx += bw + 8;
          }
        });

        // Fila 2: Título Protagonista
        const titleStr = (title && title.trim()) ? title.trim() : "Untitled Track";
        let titleSize = 36;
        ctx.font = `900 ${titleSize}px ${FONT_DISPLAY}`;
        while (titleSize > 24 && ctx.measureText(titleStr).width > infoW) {
          titleSize -= 2;
          ctx.font = `900 ${titleSize}px ${FONT_DISPLAY}`;
        }

        ctx.save();
        ctx.textAlign = "left";
        ctx.fillStyle = "#FFFFFF";
        ctx.shadowColor = "rgba(0, 0, 0, 0.85)";
        ctx.shadowBlur = 10;
        ctx.shadowOffsetY = 2;
        ctx.fillText(truncateText(ctx, titleStr, infoW), infoX, MEDIA_Y + 68);
        ctx.restore();

        // Fila 3: Artista
        ctx.textAlign = "left";
        ctx.font = `600 17px ${FONT_UI}`;
        ctx.fillStyle = "#CBD5E1";
        ctx.fillText(truncateText(ctx, artist || "Unknown Artist", infoW), infoX, MEDIA_Y + 98);

        // Fila 4: Dificultad + Mapper + Pack
        const metaRowY = MEDIA_Y + 122;
        const diffPillH = 24;
        const diffStr = (version && version.trim()) ? version.trim() : "Challenge";
        ctx.font = `700 12px ${FONT_MONO}`;
        const maxDiffW = Math.min(280, infoW * 0.46);
        const safeDiff = truncateText(ctx, diffStr, maxDiffW - 16);
        const diffW = Math.ceil(ctx.measureText(safeDiff).width + 18);

        chamferRect(ctx, infoX, metaRowY, diffW, diffPillH, 4);
        ctx.fillStyle = "rgba(255, 255, 255, 0.10)";
        ctx.fill();
        ctx.strokeStyle = COL_INK;
        ctx.lineWidth = 1;
        ctx.stroke();

        ctx.textAlign = "left";
        ctx.fillStyle = COL_INK;
        ctx.fillText(safeDiff, infoX + 9, metaRowY + 16);

        let mx = infoX + diffW + 14;
        const maxMetaX = infoX + infoW;
        const creatorLabel = isEtterna ? "Charted by " : "Mapped by ";
        const creatorName = (creator && creator.trim()) ? creator.trim() : "Unknown";

        if (mx < maxMetaX - 40) {
          ctx.font = `500 13px ${FONT_UI}`;
          ctx.fillStyle = COL_MUTED;
          ctx.fillText(creatorLabel, mx, metaRowY + 16.5);
          mx += ctx.measureText(creatorLabel).width;

          ctx.font = `700 13px ${FONT_UI}`;
          const availForCreatorAndPack = maxMetaX - mx;
          const packReserve = pack ? Math.min(180, availForCreatorAndPack * 0.45) : 0;
          const creatorSafe = truncateText(ctx, creatorName, Math.max(40, availForCreatorAndPack - packReserve));
          ctx.fillStyle = COL_INK;
          ctx.fillText(creatorSafe, mx, metaRowY + 16.5);
          mx += ctx.measureText(creatorSafe).width;

          const isRealPack = pack && !pack.toLowerCase().includes("test") && !pack.startsWith(".") && pack.toLowerCase() !== "unknown";
          if (isRealPack && mx < maxMetaX - 36) {
            ctx.font = `500 13px ${FONT_UI}`;
            ctx.fillStyle = COL_DIM;
            const sep = "  ·  ";
            ctx.fillText(sep, mx, metaRowY + 16.5);
            mx += ctx.measureText(sep).width;

            ctx.font = `600 13px ${FONT_UI}`;
            ctx.fillStyle = "#7DD3FC";
            ctx.fillText(truncateText(ctx, pack, maxMetaX - mx), mx, metaRowY + 16.5);
          }
        }

        // Separador horizontal técnico con pip ámbar
        const DIV_Y = TOP_Y + 214;             // 246
        ctx.strokeStyle = COL_HAIRLINE;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(LEFT_X + PAD, DIV_Y);
        ctx.lineTo(LEFT_X + LEFT_W - PAD, DIV_Y);
        ctx.stroke();

        ctx.fillStyle = COL_AMBER;
        ctx.fillRect(LEFT_X + PAD, DIV_Y - 1, 28, 2);

        // Matriz de Parámetros Grandes (sin enumeración ni //)
        const lnRatioPct = notes > 0 ? ((lns / notes) * 100) : 0;
        const showDrainSub = drT > 0 && Math.abs(durSec - drT) >= 3;
        const lnSub = lns > 0 ? `${lnRatioPct.toFixed(1)}% LN` : "No LNs";

        let stats = [];
        if (isEtterna) {
          stats = [
            { l: "BPM", v: bpm > 0 ? bpm.toString() : "--", sub: "", col: COL_INK },
            { l: "KEYMODE", v: `${kc}K`, sub: "", col: COL_INK },
            { l: "DURATION", v: fmtT(durSec), sub: showDrainSub ? `Drain ${fmtT(drT)}` : "", col: COL_INK },
            { l: "TOTAL NOTES", v: fmtInt(notes), sub: "", col: COL_INK },
            { l: "LONG NOTES", v: fmtInt(lns), sub: lnSub, col: lns > 0 ? COL_CYAN : COL_MUTED }
          ];
        } else {
          stats = [
            { l: "STAR RATING", v: `${(meta.sr_official || 0.0).toFixed(2)}★`, sub: "", col: COL_AMBER },
            { l: "ACCURACY", v: `OD ${od}`, sub: "", col: COL_INK },
            { l: "BPM", v: bpm > 0 ? bpm.toString() : "--", sub: "", col: COL_INK },
            { l: "DURATION", v: fmtT(durSec), sub: showDrainSub ? `Drain ${fmtT(drT)}` : "", col: COL_INK },
            { l: "NOTES", v: fmtInt(notes), sub: "", col: COL_INK },
            { l: "LONG NOTES", v: fmtInt(lns), sub: lnSub, col: lns > 0 ? COL_CYAN : COL_MUTED }
          ];
        }

        const STAT_X = LEFT_X + PAD;
        const STAT_W = LEFT_W - PAD * 2;
        const STAT_TOP = DIV_Y + 14;
        const cellW = STAT_W / stats.length;

        stats.forEach((st, i) => {
          const sx = STAT_X + i * cellW;
          if (i > 0) {
            ctx.strokeStyle = COL_HAIRLINE;
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(sx, STAT_TOP + 4);
            ctx.lineTo(sx, TOP_Y + TOP_H - 18);
            ctx.stroke();
          }

          const innerX = sx + (i === 0 ? 0 : 18);
          ctx.textAlign = "left";

          ctx.fillStyle = st.col === COL_INK ? "rgba(255, 255, 255, 0.20)" : st.col;
          ctx.fillRect(innerX, STAT_TOP, 22, 2);

          ctx.font = `700 10px ${FONT_MONO}`;
          ctx.fillStyle = COL_DIM;
          ctx.fillText(st.l, innerX, STAT_TOP + 18);

          ctx.font = `900 31px ${FONT_DISPLAY}`;
          ctx.fillStyle = st.col;
          ctx.fillText(st.v, innerX, STAT_TOP + 58);

          if (st.sub) {
            ctx.font = `600 11px ${FONT_MONO}`;
            ctx.fillStyle = COL_MUTED;
            ctx.fillText(st.sub, innerX, STAT_TOP + 78);
          }
        });

        // ── 5. TARJETA B (Derecha): Overall Rating + 7 Skillsets ─────────────
        drawCard(RIGHT_X, TOP_Y, RIGHT_W, TOP_H, COL_AMBER);

        const ss = payload.skillsets || {};
        const skList = [
          { k: "stream", l: "Stream", v: ss.stream || 0 },
          { k: "jumpstream", l: "Jumpstream", v: ss.jumpstream || 0 },
          { k: "handstream", l: "Handstream", v: ss.handstream || 0 },
          { k: "stamina", l: "Stamina", v: ss.stamina || 0 },
          { k: "jackspeed", l: "Jackspeed", v: ss.jackspeed || 0 },
          { k: "chordjack", l: "Chordjack", v: ss.chordjack || 0 },
          { k: "technical", l: "Technical", v: ss.technical || 0 }
        ];

        let maxM = overall_msd > 0 ? overall_msd : 10.0;
        let topSkillVal = 0;
        let topSkillName = "";
        skList.forEach(s => {
          if (s.v > maxM) maxM = s.v;
          if (s.v > topSkillVal) { topSkillVal = s.v; topSkillName = s.l; }
        });
        const scaleMax = Math.max(10, Math.ceil(maxM / 5) * 5);

        // Cabecera Overall Rating
        const OV_H = 76;
        ctx.save();
        const ovWash = ctx.createLinearGradient(RIGHT_X, TOP_Y, RIGHT_X + RIGHT_W, TOP_Y + OV_H);
        ovWash.addColorStop(0, "rgba(245, 166, 35, 0.04)");
        ovWash.addColorStop(1, "rgba(245, 166, 35, 0.12)");
        ctx.fillStyle = ovWash;
        ctx.fillRect(RIGHT_X + 1, TOP_Y + 1, RIGHT_W - 2, OV_H);
        ctx.restore();

        ctx.textAlign = "left";
        ctx.font = `800 16px ${FONT_DISPLAY}`;
        ctx.fillStyle = COL_INK;
        ctx.fillText(isEtterna ? "OVERALL MSD" : "OVERALL RATING", RIGHT_X + PAD, TOP_Y + 36);

        ctx.font = `600 12px ${FONT_UI}`;
        ctx.fillStyle = COL_MUTED;
        if (topSkillName) {
          const prefix = "Top Skillset: ";
          ctx.fillText(prefix, RIGHT_X + PAD, TOP_Y + 57);
          const pw = ctx.measureText(prefix).width;
          ctx.font = `700 12px ${FONT_UI}`;
          ctx.fillStyle = COL_AMBER;
          ctx.fillText(topSkillName, RIGHT_X + PAD + pw, TOP_Y + 57);
        } else {
          ctx.fillText(isEtterna ? "MinaCalc MSD" : "Estimated Rating", RIGHT_X + PAD, TOP_Y + 57);
        }

        ctx.save();
        ctx.textAlign = "right";
        ctx.font = `900 46px ${FONT_DISPLAY}`;
        ctx.fillStyle = COL_AMBER;
        ctx.shadowColor = "rgba(245, 166, 35, 0.35)";
        ctx.shadowBlur = 14;
        ctx.fillText(overall_msd > 0 ? overall_msd.toFixed(2) : "--", RIGHT_X + RIGHT_W - PAD, TOP_Y + 55);
        ctx.restore();

        ctx.strokeStyle = COL_HAIRLINE;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(RIGHT_X + PAD, TOP_Y + OV_H);
        ctx.lineTo(RIGHT_X + RIGHT_W - PAD, TOP_Y + OV_H);
        ctx.stroke();

        // 7 Filas de Skillsets con Barras de Ecualizador Tácticas
        const SK_START_Y = TOP_Y + OV_H + 8;
        const SK_ROW_H = 32;
        const barX = RIGHT_X + 136;
        const barW = 348;
        const barH = 10;

        for (let i = 0; i < skList.length; i++) {
          const r = skList[i];
          const ry = SK_START_Y + i * SK_ROW_H;
          const midY = ry + SK_ROW_H / 2;
          const isApex = topSkillVal > 0 && r.v >= topSkillVal - 0.05;
          const isStrong = overall_msd > 0 ? (r.v >= overall_msd * 0.85) : (r.v > 0);
          const valCol = mapColor(r.v);

          if (isApex) {
            chamferRect(ctx, RIGHT_X + 10, ry + 2, RIGHT_W - 20, SK_ROW_H - 4, 4);
            ctx.fillStyle = "rgba(245, 166, 35, 0.09)";
            ctx.fill();

            ctx.fillStyle = COL_AMBER;
            ctx.fillRect(RIGHT_X + 12, midY - 9, 3, 18);
          }

          // Nombre del skillset (sin enumeraciones ni //)
          ctx.textAlign = "left";
          ctx.font = `${isApex ? "700" : "600"} 13px ${FONT_UI}`;
          ctx.fillStyle = isApex ? COL_AMBER : (isStrong ? "#E2E8F0" : "#8B98AD");
          ctx.fillText(r.l, RIGHT_X + PAD, midY + 4.5);

          // Pista del ecualizador
          const barY = midY - barH / 2;
          ctx.fillStyle = "rgba(0, 0, 0, 0.55)";
          ctx.fillRect(barX, barY, barW, barH);
          ctx.strokeStyle = "rgba(255, 255, 255, 0.08)";
          ctx.strokeRect(barX, barY, barW, barH);

          const fillW = Math.round(Math.max(0, Math.min(1, r.v / scaleMax)) * barW);
          if (fillW > 0) {
            const barGrad = ctx.createLinearGradient(barX, 0, barX + fillW, 0);
            barGrad.addColorStop(0, mapColor(r.v * 0.5, 0.85));
            barGrad.addColorStop(1, valCol);
            ctx.fillStyle = barGrad;
            ctx.fillRect(barX, barY, fillW, barH);

            ctx.fillStyle = "#FFFFFF";
            ctx.fillRect(barX + Math.max(0, fillW - 2), barY, 2, barH);
          }

          // 20 ticks segmentados grabados
          ctx.strokeStyle = "rgba(10, 13, 19, 0.75)";
          for (let s = 1; s < 20; s++) {
            const sx = barX + Math.round((s / 20) * barW);
            ctx.beginPath(); ctx.moveTo(sx, barY); ctx.lineTo(sx, barY + barH); ctx.stroke();
          }

          // Aguja de referencia Overall MSD
          if (overall_msd > 0) {
            const ovX = barX + Math.round(Math.min(1, overall_msd / scaleMax) * barW);
            ctx.strokeStyle = COL_AMBER;
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            ctx.moveTo(ovX, barY - 2.5);
            ctx.lineTo(ovX, barY + barH + 2.5);
            ctx.stroke();
          }

          // Valor numérico
          ctx.textAlign = "right";
          ctx.font = `700 15px ${FONT_MONO}`;
          ctx.fillStyle = r.v > 0 ? (isApex ? COL_AMBER : (isStrong ? COL_INK : "#94A3B8")) : COL_DIM;
          ctx.fillText(r.v > 0 ? r.v.toFixed(2) : "--", RIGHT_X + RIGHT_W - PAD, midY + 5);
        }

        // ── 6. TARJETA C (Inferior): Sismógrafo Temporal de Densidad NPS ──────
        drawCard(GRAPH_X, GRAPH_Y, GRAPH_W, GRAPH_H, COL_CYAN);

        // Cabecera limpia
        ctx.textAlign = "left";
        ctx.font = `800 17px ${FONT_DISPLAY}`;
        ctx.fillStyle = COL_INK;
        ctx.fillText("NOTE DENSITY", GRAPH_X + PAD, GRAPH_Y + 42);
        const ndW = ctx.measureText("NOTE DENSITY").width;

        ctx.font = `500 13px ${FONT_UI}`;
        ctx.fillStyle = COL_DIM;
        ctx.fillText("Notes Per Second", GRAPH_X + PAD + ndW + 14, GRAPH_Y + 41.5);

        // 3 Chips KPI
        function drawKpiPill(rightEdgeX, centerY, dotCol, dotShape, label, valueStr, extraStr = "") {
          const padX = 14;
          const pillH = 32;
          const py = centerY - pillH / 2;

          ctx.font = `700 10px ${FONT_MONO}`;
          const lblW = ctx.measureText(label).width;
          ctx.font = `700 14px ${FONT_MONO}`;
          const valW = ctx.measureText(valueStr).width;
          ctx.font = `600 11px ${FONT_MONO}`;
          const extW = extraStr ? ctx.measureText(extraStr).width + 8 : 0;

          const totalW = padX + 14 + lblW + 8 + valW + extW + padX;
          const px = rightEdgeX - totalW;

          chamferRect(ctx, px, py, totalW, pillH, 6);
          ctx.fillStyle = "rgba(255, 255, 255, 0.04)";
          ctx.fill();
          ctx.strokeStyle = "rgba(255, 255, 255, 0.09)";
          ctx.lineWidth = 1;
          ctx.stroke();

          const dx = px + padX + 4;
          const dy = centerY;
          ctx.fillStyle = dotCol;
          if (dotShape === "diamond") {
            ctx.save();
            ctx.translate(dx, dy);
            ctx.rotate(Math.PI / 4);
            ctx.fillRect(-3.5, -3.5, 7, 7);
            ctx.restore();
          } else {
            ctx.beginPath();
            ctx.arc(dx, dy, 3.5, 0, Math.PI * 2);
            ctx.fill();
          }

          let tx = px + padX + 14;
          ctx.textAlign = "left";
          ctx.font = `700 10px ${FONT_MONO}`;
          ctx.fillStyle = COL_MUTED;
          ctx.fillText(label, tx, centerY + 3.5);
          tx += lblW + 8;

          ctx.font = `700 14px ${FONT_MONO}`;
          ctx.fillStyle = dotShape === "neutral" ? COL_INK : dotCol;
          ctx.fillText(valueStr, tx, centerY + 4.5);
          tx += valW + 8;

          if (extraStr) {
            ctx.font = `600 11px ${FONT_MONO}`;
            ctx.fillStyle = COL_MUTED;
            ctx.fillText(extraStr, tx, centerY + 4);
          }
          return px;
        }

        let kpiRight = GRAPH_X + GRAPH_W - PAD;
        const kpiY = GRAPH_Y + 36;
        kpiRight = drawKpiPill(kpiRight, kpiY, COL_MUTED, "neutral", "AVG", `${avgNps.toFixed(1)} NPS`) - 12;
        kpiRight = drawKpiPill(kpiRight, kpiY, COL_CRIMSON, "diamond", "PEAK", `${pkY.toFixed(1)} NPS`, `@ ${fmtT(peakTimeSec)}`) - 12;
        drawKpiPill(
          kpiRight, kpiY, COL_CYAN, "dot", "SUSTAINED",
          `${dominantNps.toFixed(1)} NPS`,
          hardSecs > 0 ? `· ${hardTimeStr} (${hardPct}%)` : ""
        );

        // Fondo del área del gráfico
        ctx.fillStyle = "rgba(7, 9, 14, 0.54)";
        ctx.fillRect(cX, cY, cW, cH);

        // Rejilla horizontal + Eje Y limpio
        ctx.lineWidth = 1;
        for (let v = 0; v <= maxY; v += yStep) {
          const y = bot - (v / maxY) * cH;
          ctx.strokeStyle = v === 0 ? "rgba(255, 255, 255, 0.18)" : "rgba(255, 255, 255, 0.05)";
          ctx.beginPath();
          ctx.moveTo(cX, y);
          ctx.lineTo(cX + cW, y);
          ctx.stroke();

          ctx.font = `600 12px ${FONT_MONO}`;
          ctx.fillStyle = "#7D8DA3";
          ctx.textAlign = "right";
          ctx.fillText(v.toString(), cX - 14, y + 4);
        }

        // Rejilla vertical + Eje X de tiempos
        const tStepS = spanS > 600 ? 120 : (spanS > 300 ? 60 : (spanS > 120 ? 30 : (spanS > 60 ? 15 : 10)));
        const endX = cX + cW;

        ctx.font = `600 12px ${FONT_MONO}`;
        for (let s = 0; s <= spanS; s += tStepS) {
          const x = cX + (s / spanS) * cW;
          if (s !== 0 && (endX - x) < 64) continue;

          if (s > 0) {
            ctx.strokeStyle = "rgba(255, 255, 255, 0.04)";
            ctx.beginPath();
            ctx.moveTo(x, cY);
            ctx.lineTo(x, bot);
            ctx.stroke();
          }

          ctx.fillStyle = "#8B98AD";
          ctx.textAlign = s === 0 ? "left" : "center";
          ctx.fillText(fmtT(s), x, bot + 26);
        }

        ctx.textAlign = "right";
        ctx.fillStyle = COL_INK;
        ctx.fillText(fmtT(spanS), endX, bot + 26);

        // Curva y Relleno de Densidad
        ctx.save();
        ctx.beginPath();
        ctx.rect(cX, cY, cW, cH);
        ctx.clip();

        const pathPoints = [];
        for (let i = 0; i < cW; i++) {
          const x = cX + i;
          const y = bot - (sProf[i] / maxY) * cH;
          pathPoints.push([x, y, sProf[i]]);
        }

        if (pathPoints.length > 1) {
          ctx.save();
          ctx.beginPath();
          ctx.moveTo(pathPoints[0][0], bot + 2);
          for (let i = 0; i < pathPoints.length; i++) {
            ctx.lineTo(pathPoints[i][0], pathPoints[i][1]);
          }
          ctx.lineTo(pathPoints[pathPoints.length - 1][0], bot + 2);
          ctx.closePath();
          ctx.clip();

          // Relleno vertical continuo (Espec. Imagen 3)
          for (let i = 0; i < cW; i++) {
            const v = sProf[i];
            if (v <= 0.02) continue;
            const x = cX + i;
            const y = bot - (v / maxY) * cH;
            const h = bot - y;
            if (h <= 0) continue;

            const [r, g, b] = pRgb(mapColor(v));
            const vGrad = ctx.createLinearGradient(0, y, 0, bot);
            vGrad.addColorStop(0, `rgba(${r}, ${g}, ${b}, 0.54)`);
            vGrad.addColorStop(0.38, `rgba(${r}, ${g}, ${b}, 0.25)`);
            vGrad.addColorStop(0.78, `rgba(${r}, ${g}, ${b}, 0.08)`);
            vGrad.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0.01)`);

            ctx.fillStyle = vGrad;
            ctx.fillRect(x - 0.2, y - 2, 1.4, h + 4);
          }

          // Iluminación superior en tramos difíciles
          if (dominantNps > 0.1 && dominantNps < pkY) {
            const domPx = Math.max(cY, Math.min(bot, bot - (dominantNps / maxY) * cH));
            ctx.save();
            ctx.beginPath();
            ctx.rect(cX, cY, cW, domPx - cY);
            ctx.clip();

            for (let i = 0; i < cW; i++) {
              const v = sProf[i];
              if (v < dominantNps) continue;
              const x = cX + i;
              const y = bot - (v / maxY) * cH;
              const [r, g, b] = pRgb(mapColor(v));
              const topGrad = ctx.createLinearGradient(0, y, 0, domPx);
              topGrad.addColorStop(0, `rgba(${r}, ${g}, ${b}, 0.22)`);
              topGrad.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0.02)`);
              ctx.fillStyle = topGrad;
              ctx.fillRect(x - 0.2, y - 2, 1.4, (domPx - y) + 4);
            }
            ctx.restore();
          }

          ctx.restore();
        }

        // Contorno continuo superior
        ctx.save();
        ctx.lineJoin = "round";
        ctx.lineCap = "round";
        for (let i = 0; i < pathPoints.length - 1; i++) {
          const [x1, y1, v1] = pathPoints[i];
          const [x2, y2, v2] = pathPoints[i + 1];
          const meanV = (v1 + v2) / 2;
          const isHard = meanV >= dominantNps;
          const strokeCol = mapColor(meanV);

          ctx.strokeStyle = strokeCol;
          ctx.lineWidth = isHard ? 3.4 : 2.2;
          if (isHard) {
            ctx.shadowColor = strokeCol;
            ctx.shadowBlur = 8;
          } else {
            ctx.shadowBlur = 0;
          }

          ctx.beginPath();
          ctx.moveTo(x1, y1);
          ctx.lineTo(x2, y2);
          ctx.stroke();
        }
        ctx.restore();

        // Línea horizontal de umbral sostenido
        const dominantNps_px = Math.max(cY, Math.min(bot, bot - (dominantNps / maxY) * cH));
        if (dominantNps > 0.1) {
          ctx.save();
          ctx.strokeStyle = "rgba(0, 229, 204, 0.72)";
          ctx.lineWidth = 1.5;
          ctx.setLineDash([6, 5]);
          ctx.beginPath();
          ctx.moveTo(cX, dominantNps_px);
          ctx.lineTo(cX + cW, dominantNps_px);
          ctx.stroke();
          ctx.restore();
        }

        // Marcador del Pico
        if (pkY > 0 && maxSIdx >= 0 && maxSIdx < cW) {
          const pkX_px = cX + maxSIdx;
          const pkY_px = bot - (sProf[maxSIdx] / maxY) * cH;

          ctx.save();
          ctx.strokeStyle = "rgba(255, 69, 96, 0.40)";
          ctx.lineWidth = 1;
          ctx.setLineDash([4, 4]);
          ctx.beginPath();
          ctx.moveTo(pkX_px, pkY_px + 6);
          ctx.lineTo(pkX_px, bot);
          ctx.stroke();
          ctx.restore();

          ctx.save();
          ctx.translate(pkX_px, pkY_px);
          ctx.rotate(Math.PI / 4);
          ctx.fillStyle = COL_CRIMSON;
          ctx.fillRect(-4.5, -4.5, 9, 9);
          ctx.strokeStyle = "#FFFFFF";
          ctx.lineWidth = 1.5;
          ctx.strokeRect(-4.5, -4.5, 9, 9);
          ctx.restore();

          const pkAtSec = Math.round((maxSIdx / Math.max(1, cW - 1)) * spanS);
          const pkTagText = `PEAK ${pkY.toFixed(1)} @ ${fmtT(pkAtSec)}`;
          ctx.font = `700 11px ${FONT_MONO}`;
          const tagW = Math.ceil(ctx.measureText(pkTagText).width + 20);
          const tagH = 24;
          const flipLeft = (pkX_px + 14 + tagW > cX + cW - 8);
          const tagX = flipLeft ? (pkX_px - 14 - tagW) : (pkX_px + 14);
          const tagY = Math.max(cY + 8, Math.min(bot - tagH - 8, pkY_px - tagH / 2));

          chamferRect(ctx, tagX, tagY, tagW, tagH, 4);
          ctx.fillStyle = "rgba(11, 14, 20, 0.92)";
          ctx.fill();
          ctx.strokeStyle = COL_CRIMSON;
          ctx.lineWidth = 1.5;
          ctx.stroke();

          ctx.textAlign = "left";
          ctx.fillStyle = COL_INK;
          ctx.fillText(pkTagText, tagX + 10, tagY + 16);
        }

        ctx.restore(); // Fin clip

        ctx.strokeStyle = "rgba(255, 255, 255, 0.09)";
        ctx.lineWidth = 1;
        ctx.strokeRect(cX, cY, cW, cH);
        drawCornerTicks(ctx, cX, cY, cW, cH, 8, COL_MUTED, 1.2);

        // Badge sostenido anclado a la derecha
        if (dominantNps > 0.1) {
          const pillW = 60;
          const pillH = 24;
          const pillX = cX + cW + 12;
          const pillY = Math.max(cY, Math.min(bot - pillH, dominantNps_px - pillH / 2));
          const arrowY = Math.max(pillY + 6, Math.min(pillY + pillH - 6, dominantNps_px));

          ctx.beginPath();
          ctx.moveTo(pillX - 6, arrowY);
          ctx.lineTo(pillX + 1, arrowY - 5);
          ctx.lineTo(pillX + 1, arrowY + 5);
          ctx.closePath();
          ctx.fillStyle = COL_CYAN;
          ctx.fill();

          chamferRect(ctx, pillX, pillY, pillW, pillH, 4);
          ctx.fillStyle = COL_CYAN;
          ctx.fill();

          ctx.font = `800 12px ${FONT_MONO}`;
          ctx.fillStyle = "#07090D";
          ctx.textAlign = "center";
          ctx.fillText(dominantNps.toFixed(1), pillX + pillW / 2, pillY + 16.5);
        }

        // ── 7. Firma Discreta Inferior ───────────────────────────────────────
        const FOOT_Y = 960;
        ctx.fillStyle = COL_AMBER;
        ctx.fillRect(MX + 2, FOOT_Y - 9, 3, 11);

        ctx.textAlign = "left";
        ctx.font = `700 11px ${FONT_MONO}`;
        ctx.fillStyle = "rgba(255, 255, 255, 0.40)";
        ctx.fillText("DANOVERLAY", MX + 14, FOOT_Y);

        ctx.textAlign = "right";
        ctx.font = `600 11px ${FONT_MONO}`;
        ctx.fillStyle = "rgba(255, 255, 255, 0.28)";
        ctx.fillText(isEtterna ? "Etterna · MinaCalc MSD" : "osu!mania 4K · Density Profile", W - MX, FOOT_Y);

        // ── 8. CAPTURA (Intacto) ─────────────────────────────────────────────
        let captured = false;
        _doCapture();

        function _doCapture() {
          if (captured) return;
          captured = true;
          try {
            console.log("[CHART] _doCapture called");
            const fn = `${artist} - ${title} [${version}]`;

            const b64 = canvas.toDataURL("image/png");

            // Liberar memoria inmediatamente
            canvas.width = 0;
            canvas.height = 0;

            console.log("[CHART] b64 length:", b64.length, "fn:", fn);
            if (typeof setChartGenerating === "function") setChartGenerating(false);
            if (window.pywebview && window.pywebview.api && window.pywebview.api.save_chart) {
              console.log("[CHART] Calling save_chart...");
              window.pywebview.api.save_chart(b64, fn).then(res => {
                if (typeof showToast === "function") {
                  if (res.status === "ok") showToast(res.message || "Imagen generada", 2000);
                  else showToast(res.message || "Error al guardar", 3000);
                }
              }).catch((err) => {
                if (typeof showToast === "function") showToast("Error al guardar la imagen", 3000);
              });
            } else {
              if (typeof showToast === "function") showToast("save_chart no disponible", 3000);
            }
          } catch (err) {
            if (window.pywebview && window.pywebview.api && window.pywebview.api.log_js_error) {
              window.pywebview.api.log_js_error("Error inside _doCapture: " + err.toString());
            }
            if (typeof showToast === "function") showToast("Error en _doCapture: " + err.toString(), 4000);
            if (typeof setChartGenerating === "function") setChartGenerating(false);
          }
        }
      } catch (err) {
        console.error("[CHART] Exception inside runDraw:", err);
        if (typeof showToast === "function") showToast("Error en renderExportChart: " + (err.message || err), 4000);
        if (typeof setChartGenerating === "function") setChartGenerating(false);
      }
    }

    function loadImg(src) {
      if (!src) return Promise.resolve(null);
      return new Promise((resolve) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = () => resolve(null);
        img.src = src;
        if (img.complete && img.naturalWidth > 0) resolve(img);
      });
    }

    let drawn = false;
    const drawOnce = (bgImg, bnImg) => {
      if (drawn) return;
      drawn = true;
      runDraw(bgImg, bnImg);
    };

    Promise.all([
      loadImg(payload.bg_image),
      loadImg(payload.banner_image)
    ]).then(([bgImg, bnImg]) => {
      drawOnce(bgImg, bnImg);
    }).catch(() => {
      drawOnce(null, null);
    });
  } catch (err) {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.log_js_error) {
      window.pywebview.api.log_js_error(err.stack || err.toString());
    } else {
      console.error("[CHART ERROR]", err);
    }
  }
}
