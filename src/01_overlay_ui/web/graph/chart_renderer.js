function renderExportChart(payload) {
  try {
    try {
      console.log("[CHART] renderExportChart called");
      const canvas = document.createElement("canvas");
      canvas.width = 1800;
      canvas.height = 980;
      const ctx = canvas.getContext("2d");
      const W = canvas.width, H = canvas.height;
      ctx.clearRect(0, 0, W, H);

      // ── Logical Helpers (UNTOUCHED) ────────────────────────────────────────
      function pRgb(s) { const m = s.match(/(\d+),\s*(\d+),\s*(\d+)/); return m ? [+m[1], +m[2], +m[3]] : [120, 160, 255] }
      function fmtT(s) { return `${Math.floor(s / 60).toString().padStart(2, "0")}:${Math.floor(s % 60).toString().padStart(2, "0")}` }
      function rRect(c, x, y, w, h, r) { c.beginPath(); c.moveTo(x + r, y); c.lineTo(x + w - r, y); c.quadraticCurveTo(x + w, y, x + w, y + r); c.lineTo(x + w, y + h - r); c.quadraticCurveTo(x + w, y + h, x + w - r, y + h); c.lineTo(x + r, y + h); c.quadraticCurveTo(x, y + h, x, y + h - r); c.lineTo(x, y + r); c.quadraticCurveTo(x, y, x + r, y); c.closePath() }

      function truncateText(ctx, text, maxWidth) {
        if (ctx.measureText(text).width <= maxWidth) return text;
        let str = text;
        while (str.length > 0 && ctx.measureText(str + "...").width > maxWidth) {
          str = str.slice(0, -1);
        }
        return str + "...";
      }

      const CS = [[0, [18, 76, 196]], [4, [26, 150, 224]], [8, [31, 214, 209]], [12, [79, 223, 110]],
      [16, [185, 224, 76]], [20, [246, 191, 44]], [24, [255, 136, 52]], [30, [248, 72, 56]],
      [38, [210, 56, 129]], [48, [156, 84, 236]], [60, [214, 168, 255]]];

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
          if (!seen[x] || nps > prof[x]) { prof[x] = nps; seen[x] = 1 }
        }
        let last = 0; for (let i = 0; i < width; i++) { if (seen[i]) last = prof[i]; else prof[i] = last }
        let nxt = 0; for (let i = width - 1; i >= 0; i--) { if (seen[i]) nxt = prof[i]; else if (prof[i] <= 0) prof[i] = nxt }
        return prof;
      }

      function smoothProfile(vals, radius) {
        if (!vals.length) return [];
        radius = Math.max(1, radius); const n = vals.length, out = new Float64Array(n);
        const pfx = new Float64Array(n + 1); for (let i = 0; i < n; i++)pfx[i + 1] = pfx[i] + vals[i];
        for (let i = 0; i < n; i++) { const lo = Math.max(0, i - radius), hi = Math.min(n, i + radius + 1); out[i] = (pfx[hi] - pfx[lo]) / (hi - lo) }
        return out;
      }

      // ── NEW Design Helpers (PREMIUM) ────────────────────────────────────────
      function drawGlassPanel(x, y, w, h) {
        ctx.save();
        // Deep shadow
        ctx.shadowColor = "rgba(0, 0, 0, 0.6)";
        ctx.shadowBlur = 40;
        ctx.shadowOffsetY = 20;

        // Semi-transparent gradient background
        const grad = ctx.createLinearGradient(x, y, x, y + h);
        grad.addColorStop(0, "rgba(22, 27, 39, 0.85)");
        grad.addColorStop(1, "rgba(13, 16, 23, 0.95)");
        ctx.fillStyle = grad;

        rRect(ctx, x, y, w, h, 24);
        ctx.fill();
        ctx.restore();

        // Top highlight (simulating glass edge)
        ctx.save();
        ctx.beginPath();
        rRect(ctx, x, y, w, h, 24);
        ctx.clip();

        ctx.strokeStyle = "rgba(255, 255, 255, 0.12)";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(x, y + 24);
        ctx.quadraticCurveTo(x, y, x + 24, y);
        ctx.lineTo(x + w - 24, y);
        ctx.quadraticCurveTo(x + w, y, x + w, y + 24);
        ctx.stroke();

        // Subtle outer border
        ctx.strokeStyle = "rgba(255, 255, 255, 0.03)";
        ctx.lineWidth = 1;
        rRect(ctx, x, y, w, h, 24);
        ctx.stroke();
        ctx.restore();
      }

      const FONT_FAM = "'Inter', 'Segoe UI', 'Bahnschrift', sans-serif";

      // ── 1. Background (Premium Dark Mesh) ───────────────────────────────────
      const bg = ctx.createLinearGradient(0, 0, W, H);
      bg.addColorStop(0, "#090a10"); // Darker and bluish
      bg.addColorStop(0.5, "#0d0f17");
      bg.addColorStop(1, "#050608");
      ctx.fillStyle = bg;
      ctx.fillRect(0, 0, W, H);

      // Subtle background glows
      ctx.save();
      ctx.globalCompositeOperation = "screen";

      const g1 = ctx.createRadialGradient(W * 0.2, H * 0.2, 0, W * 0.2, H * 0.2, 900);
      g1.addColorStop(0, "rgba(114, 46, 209, 0.15)");
      g1.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = g1;
      ctx.fillRect(0, 0, W, H);

      const g2 = ctx.createRadialGradient(W * 0.8, H * 0.9, 0, W * 0.8, H * 0.9, 800);
      g2.addColorStop(0, "rgba(255, 42, 109, 0.12)");
      g2.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = g2;
      ctx.fillRect(0, 0, W, H);

      // Dot pattern grid
      ctx.fillStyle = "rgba(255, 255, 255, 0.015)";
      for (let ix = 0; ix < W; ix += 40) {
        for (let iy = 0; iy < H; iy += 40) {
          ctx.beginPath(); ctx.arc(ix, iy, 1, 0, Math.PI * 2); ctx.fill();
        }
      }
      ctx.restore();

      // ── Initial Data (UNTOUCHED) ───────────────────────────────────────────
      const meta = payload.parsed_meta || {};
      const bpm = Math.round(meta.bpm || 0), od = meta.od ? meta.od.toFixed(1) : "0.0";
      const kc = 4;
      const { nps_data, density_meta = {} } = payload;
      if (!nps_data || !nps_data.length) { console.error("[CHART] No nps_data"); return; }

      let maxY = 10.0, pkY = 0.0;
      let sumY = 0.0, sumY2 = 0.0;
      let pkTime = nps_data[0][0];

      nps_data.forEach(d => {
        if (d[1] > pkY) { pkY = d[1]; pkTime = d[0]; }
        sumY += d[1];
        sumY2 += d[1] * d[1];
        if (d[1] > maxY) maxY = d[1];
      });
      
      // Dominant NPS from Python backend (histogram mode, time-weighted, ignores rests)
      let dominantNps = payload.dominant_nps || 0;
      // Fallback: if backend didn't provide it, use the self-weighted average
      if (!dominantNps || dominantNps <= 0) {
        dominantNps = sumY > 0 ? (sumY2 / sumY) : 0;
      }
      maxY = Math.ceil(maxY / 5) * 5;

      // ── Layout Geometry ────────────────────────────────────────────────────
      const panX1 = 40, panY1 = 110, panW1 = 1220, panH1 = 620;
      const panX2 = 40, panY2 = 760, panW2 = 1220, panH2 = 180;
      const panX3 = 1290, panY3 = 110, panW3 = 470, panH3 = 620;
      const panX4 = 1290, panY4 = 760, panW4 = 470, panH4 = 180;

      const cX = panX1 + 70;
      const cW = panW1 - 100;
      const cY = panY1 + 40;
      const cH = panH1 - 90;
      const bot = cY + cH;

      const prof = buildPixelProfile(nps_data, cW);
      const sProfRaw = smoothProfile(prof, Math.max(3, Math.floor(cW / 220)));

      let maxS = 0; let maxSIdx = 0;
      for (let i = 0; i < cW; i++) {
        if (sProfRaw[i] > maxS) { maxS = sProfRaw[i]; maxSIdx = i; }
      }

      const sProf = new Float64Array(cW);
      const scaleS = (pkY > 0 && maxS > 0) ? (pkY / maxS) : 1.0;
      for (let i = 0; i < cW; i++) { sProf[i] = sProfRaw[i] * scaleS; }

      // ── 3. PREMIUM HEADER ──────────────────────────────────────────────────
      // Title / Logo
      ctx.textAlign = "left";
      ctx.font = `900 36px ${FONT_FAM}`;
      ctx.fillStyle = "#ffffff";
      ctx.fillText("DanOverlay", 45, 65);

      // Colored accent dot next to title
      ctx.beginPath();
      ctx.arc(45 + ctx.measureText("DanOverlay").width + 12, 54, 4, 0, Math.PI * 2);
      ctx.fillStyle = "#ff2a6d";
      ctx.fill();

      ctx.font = `600 16px ${FONT_FAM}`;
      ctx.fillStyle = "#6e7681";
      ctx.letterSpacing = "2px";
      ctx.fillText("NOTE DENSITY CHART", 280, 62);
      ctx.letterSpacing = "0px";

      // Top badges (modern pills)
      ctx.textAlign = "center";
      let bx = W - 40;
      const overall_msd = payload.overall_msd || 0.0;
      const danShort = payload.dan_short || "";
      const family = (payload.family || "").toUpperCase();

      const bgs = [
        { t: `${overall_msd.toFixed(2)} MSD`, c: "#d8a4ff", bg: "rgba(157, 78, 221, 0.15)", br: "rgba(157, 78, 221, 0.4)", glow: "#9d4edd" },
        { t: family, c: "#e2e8f0", bg: "rgba(255,255,255,0.05)", br: "rgba(255,255,255,0.15)", glow: "transparent" },
        { t: danShort, c: "#e2e8f0", bg: "rgba(255,255,255,0.05)", br: "rgba(255,255,255,0.15)", glow: "transparent" }
      ];

      bgs.forEach(b => {
        if (!b.t) return;
        ctx.font = `bold 15px ${FONT_FAM}`;
        const bw = ctx.measureText(b.t).width + 36;
        bx -= bw;

        ctx.save();
        if (b.glow !== "transparent") {
          ctx.shadowColor = b.glow;
          ctx.shadowBlur = 10;
        }
        ctx.fillStyle = b.bg;
        rRect(ctx, bx, 35, bw, 34, 8); // Sharp/modern corners
        ctx.fill();
        ctx.restore();

        ctx.strokeStyle = b.br;
        ctx.lineWidth = 1;
        ctx.stroke();

        ctx.fillStyle = b.c;
        ctx.fillText(b.t, bx + bw / 2, 57);
        bx -= 12;
      });

      // ── 4. DRAW PANELS ─────────────────────────────────────────────────────
      drawGlassPanel(panX1, panY1, panW1, panH1);
      drawGlassPanel(panX2, panY2, panW2, panH2);
      drawGlassPanel(panX3, panY3, panW3, panH3);

      // ── 5. CHART AREA (Axes & Dashed Grid) ─────────────────────────────────
      ctx.textAlign = "right";
      ctx.font = `600 13px ${FONT_FAM}`;
      ctx.fillStyle = "#6e7681";

      for (let i = 0; i <= 5; i++) {
        const y = bot - (i / 5) * cH;
        ctx.strokeStyle = "rgba(255, 255, 255, 0.05)";
        ctx.lineWidth = 1;
        ctx.setLineDash([5, 5]); // Dashed tech grid lines
        ctx.beginPath(); ctx.moveTo(cX - 10, y); ctx.lineTo(cX + cW, y); ctx.stroke();
        ctx.setLineDash([]); // Reset
        if (i > 0) ctx.fillText(((i / 5) * maxY).toFixed(0), cX - 25, y + 4);
      }

      const t0 = nps_data[0][0], tf = nps_data[nps_data.length - 1][0], durS = (tf - t0) / 1000;
      const spanTime = Math.max(1, tf - t0);
      let tic = 15; if (durS > 180) tic = 30; if (durS > 360) tic = 60; if (durS > 600) tic = 120;

      ctx.textAlign = "center";
      for (let t = 0; t <= durS; t += tic) {
        const x = cX + (t / durS) * cW;
        ctx.strokeStyle = "rgba(255, 255, 255, 0.04)";
        ctx.setLineDash([4, 6]);
        ctx.beginPath(); ctx.moveTo(x, bot); ctx.lineTo(x, panY1 + 40); ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillText(fmtT(t), x, bot + 25);
      }

      // ── 6. DENSITY CURVE ───────────────────────────────────────────────────
      const bW = cW / nps_data.length;
      if (bW >= 2.4) {
        const gapW = Math.min(1.6, bW * 0.16), w = Math.max(1.0, bW - gapW);
        nps_data.forEach((d, i) => {
          const v = d[1]; if (v <= 0.02) return;
          const h = (v / maxY) * cH; if (h <= 0) return;
          const x = cX + (i * bW), y = bot - h;
          const col = mapColor(v);
          const c = pRgb(col);

          const lg = ctx.createLinearGradient(0, y, 0, bot);
          lg.addColorStop(0, col);
          lg.addColorStop(1, `rgba(${c[0]},${c[1]},${c[2]}, 0.05)`);

          ctx.fillStyle = lg;
          // Rounded top corners
          ctx.beginPath();
          ctx.moveTo(x, bot);
          ctx.lineTo(x, y + 2);
          ctx.quadraticCurveTo(x, y, x + w / 2, y);
          ctx.quadraticCurveTo(x + w, y, x + w, y + 2);
          ctx.lineTo(x + w, bot);
          ctx.fill();
        });
      } else {
        const areaColor = mapColor(pkY);
        const pRColor = pRgb(areaColor);

        // Curve fill
        ctx.beginPath(); ctx.moveTo(cX, bot);
        for (let i = 0; i < cW; i++) ctx.lineTo(cX + i, bot - (sProf[i] / maxY) * cH);
        ctx.lineTo(cX + cW, bot); ctx.closePath();

        const areaG = ctx.createLinearGradient(0, bot - cH, 0, bot);
        areaG.addColorStop(0, `rgba(${pRColor[0]}, ${pRColor[1]}, ${pRColor[2]}, 0.45)`);
        areaG.addColorStop(1, `rgba(${pRColor[0]}, ${pRColor[1]}, ${pRColor[2]}, 0.0)`);
        ctx.fillStyle = areaG;
        ctx.fill();

        // Colored glowing border stroke
        const segs = 80, sW = cW / segs;
        ctx.lineWidth = 3.5;
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
        for (let s = 0; s < segs; s++) {
          const st = Math.floor(s * sW), en = Math.floor((s + 1) * sW);
          if (st >= cW) break;
          let p = 0; for (let i = st; i < en; i++) p = Math.max(p, sProf[i]);

          ctx.save();
          const lineColor = mapColor(p, 1);
          ctx.strokeStyle = lineColor;
          ctx.shadowColor = lineColor;
          ctx.shadowBlur = 15; // Glow intensity
          ctx.beginPath();
          for (let i = st; i <= en && i < cW; i++) ctx[i === st ? "moveTo" : "lineTo"](cX + i, bot - (sProf[i] / maxY) * cH);
          ctx.stroke();
          ctx.restore();
        }
      }

      // --> PEAK POINT (Radar/Cyber design) <--
      let peakIdx, peakX, peakY;
      if (bW >= 2.4) {
        peakIdx = Math.max(0, Math.min(cW - 1, Math.round(((pkTime - t0) / spanTime) * (cW - 1))));
        peakX = cX + peakIdx;
        peakY = bot - (pkY / maxY) * cH;
      } else {
        peakIdx = maxSIdx;
        peakX = cX + peakIdx;
        peakY = bot - (sProf[peakIdx] / maxY) * cH;
      }

      ctx.save();
      const peakColStr = mapColor(pkY);

      // Vertical peak indicator line
      ctx.strokeStyle = `rgba(${pRgb(peakColStr).join(',')}, 0.3)`;
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.beginPath(); ctx.moveTo(peakX, peakY); ctx.lineTo(peakX, bot); ctx.stroke();
      ctx.setLineDash([]);

      // Outer ring
      ctx.beginPath(); ctx.arc(peakX, peakY, 14, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${pRgb(peakColStr).join(',')}, 0.2)`;
      ctx.fill();
      ctx.strokeStyle = `rgba(${pRgb(peakColStr).join(',')}, 0.6)`;
      ctx.lineWidth = 2;
      ctx.stroke();

      // Neon center dot
      ctx.beginPath(); ctx.arc(peakX, peakY, 6, 0, Math.PI * 2);
      ctx.fillStyle = peakColStr;
      ctx.shadowColor = peakColStr;
      ctx.shadowBlur = 20;
      ctx.fill();

      // Inner white core
      ctx.beginPath(); ctx.arc(peakX, peakY, 2.5, 0, Math.PI * 2);
      ctx.fillStyle = "#ffffff";
      ctx.shadowBlur = 0;
      ctx.fill();
      ctx.restore();

      // --> DRAW DOMINANT NPS LINE <--
      ctx.save();
      const dominantNps_px = bot - (dominantNps / maxY) * cH;
      
      // Dotted horizontal threshold line
      ctx.strokeStyle = "rgba(0, 240, 255, 0.4)"; // Light cyan accent
      ctx.lineWidth = 1.5;
      ctx.setLineDash([5, 5]);
      ctx.beginPath();
      ctx.moveTo(cX, dominantNps_px);
      ctx.lineTo(cX + cW, dominantNps_px);
      ctx.stroke();
      ctx.setLineDash([]);
      
      // Glow point on y-axis
      ctx.fillStyle = "#00f0ff";
      ctx.beginPath();
      ctx.arc(cX, dominantNps_px, 4, 0, Math.PI * 2);
      ctx.fill();
      
      // Value label
      ctx.font = "bold 16px 'Bahnschrift',sans-serif";
      ctx.fillStyle = "rgba(0, 240, 255, 0.8)";
      ctx.textAlign = "right";
      ctx.fillText(dominantNps.toFixed(1), cX - 10, dominantNps_px + 4);
      ctx.textAlign = "left";
      ctx.restore();

      // ── 7. METADATA PANEL (Stats Cards layout) ─────────────────────────────
      const { artist = "", title = "", version = "", creator = "" } = meta;
      const notes = meta.note_count || 0, lns = meta.ln_count || 0, drT = meta.drain_time_s || 0;
      const durSec = meta.total_time_ms ? Math.round(meta.total_time_ms / 1000) : drT;

      const statBlocks = [
        { l: "STARS", v: (meta.sr_official || 0.0).toFixed(2) },
        { l: "OD", v: od },
        { l: "BPM", v: bpm.toString() },
        { l: "KEYS", v: `${kc}K` },
        { l: "DUR", v: fmtT(durSec) },
        { l: "LN", v: lns.toString() },
        { l: "NOTES", v: notes.toString() }
      ];

      const mX = panX2 + 40;
      let mY = panY2 + 55;

      // Calculate stats layout width
      // Use stats cards instead of plain lines
      const statCardWidth = 85;
      const totalStatsWidth = statBlocks.length * statCardWidth;
      const statsStartX = panX2 + panW2 - totalStatsWidth - 20;
      const maxTextWidth = Math.max(200, statsStartX - mX - 60);

      // Title
      ctx.textAlign = "left";
      ctx.font = `900 38px ${FONT_FAM}`;
      ctx.fillStyle = "#ffffff";
      ctx.shadowColor = "rgba(0,0,0,0.5)"; ctx.shadowBlur = 8; ctx.shadowOffsetY = 4;
      const safeTitle = truncateText(ctx, title, maxTextWidth);
      ctx.fillText(safeTitle, mX, mY);
      ctx.shadowBlur = 0; ctx.shadowOffsetY = 0;

      // Artist
      mY += 32;
      ctx.font = `600 20px ${FONT_FAM}`;
      ctx.fillStyle = "#94a3b8"; // Modern cool grey
      const safeArtist = truncateText(ctx, artist, maxTextWidth);
      ctx.fillText(safeArtist, mX, mY);

      // Difficulty (bright solid pill) & Mapper
      mY += 35;
      const diffText = version;
      ctx.font = `bold 15px ${FONT_FAM}`;
      const diffW = ctx.measureText(diffText).width + 24;

      const pGrad = ctx.createLinearGradient(mX, 0, mX + diffW, 0);
      pGrad.addColorStop(0, "#9d4edd"); pGrad.addColorStop(1, "#c77dff");
      ctx.fillStyle = pGrad;
      rRect(ctx, mX, mY - 18, diffW, 26, 13);
      ctx.fill();
      ctx.fillStyle = "#ffffff";
      ctx.fillText(diffText, mX + 12, mY);

      let textX = mX + diffW + 15;
      ctx.font = `18px ${FONT_FAM}`;
      ctx.fillStyle = "#6e7681";
      ctx.fillText("Mapped by", textX, mY);
      textX += ctx.measureText("Mapped by ").width;

      ctx.fillStyle = "#e2e8f0";
      ctx.font = `bold 18px ${FONT_FAM}`;
      const safeCreator = truncateText(ctx, creator, maxTextWidth - textX + mX);
      ctx.fillText(safeCreator, textX, mY);

      // Technical info
      mY += 32;
      const tech = `SAMPLES: ${nps_data.length}  •  HOP: ${density_meta.hop_ms || 0}MS  •  WINDOW: ${density_meta.segment_ms || 0}MS`;
      ctx.font = `600 12px ${FONT_FAM}`;
      ctx.fillStyle = "#475569";
      ctx.letterSpacing = "1px";
      ctx.fillText(tech, mX, mY);
      ctx.letterSpacing = "0px";

      // Render Stat Cards (aligned right)
      let sx = statsStartX;
      const sy = panY2 + 45;

      statBlocks.forEach((sb, idx) => {
        // Card background
        ctx.fillStyle = "rgba(255, 255, 255, 0.02)";
        rRect(ctx, sx, sy, statCardWidth - 10, 90, 12);
        ctx.fill();

        // Card left accent edge
        ctx.fillStyle = "rgba(255, 255, 255, 0.1)";
        ctx.beginPath();
        ctx.roundRect(sx, sy, 3, 90, [12, 0, 0, 12]);
        ctx.fill();

        ctx.textAlign = "center";

        // Main value (large)
        ctx.font = `900 24px ${FONT_FAM}`;
        ctx.fillStyle = "#ffffff";
        ctx.fillText(sb.v, sx + (statCardWidth - 10) / 2, sy + 45);

        // Label (small)
        ctx.font = `700 12px ${FONT_FAM}`;
        ctx.fillStyle = "#64748b";
        ctx.fillText(sb.l, sx + (statCardWidth - 10) / 2, sy + 70);

        sx += statCardWidth;
      });

      // ── 8. SKILLSETS PANEL (Premium Neon Bars) ─────────────────────────────
      const ss = payload.skillsets || {};
      let maxM = overall_msd > 0 ? overall_msd : 10.0;
      Object.values(ss).forEach(v => maxM = Math.max(maxM, v));
      const skRows = [
        { l: "Overall", v: overall_msd, top: true },
        { l: "Stream", v: ss.stream || 0 },
        { l: "Jumpstream", v: ss.jumpstream || 0 },
        { l: "Handstream", v: ss.handstream || 0 },
        { l: "Stamina", v: ss.stamina || 0 },
        { l: "Jackspeed", v: ss.jackspeed || 0 },
        { l: "Chordjack", v: ss.chordjack || 0 },
        { l: "Technical", v: ss.technical || 0 }
      ];

      const skX = panX3 + 40;
      const skW = panW3 - 80;
      const rowH = (panH3 - 100) / skRows.length;
      let rY = panY3 + 40;

      // Overall header
      ctx.textAlign = "left";
      ctx.font = `900 28px ${FONT_FAM}`;
      ctx.fillStyle = "#ffffff";
      ctx.fillText("OVERALL", skX, rY + 30);

      ctx.textAlign = "right";
      ctx.font = `900 42px ${FONT_FAM}`;
      ctx.fillStyle = "#d8a4ff";
      ctx.shadowColor = "rgba(157, 78, 221, 0.6)";
      ctx.shadowBlur = 20;
      ctx.fillText(overall_msd > 0 ? overall_msd.toFixed(2) : "--.-", skX + skW, rY + 35);
      ctx.shadowBlur = 0;

      ctx.strokeStyle = "rgba(255, 255, 255, 0.08)";
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(skX, rY + 60); ctx.lineTo(skX + skW, rY + 60); ctx.stroke();

      rY += 85;

      // Skillsets
      for (let i = 1; i < skRows.length; i++) {
        const r = skRows[i];
        const valCol = mapColor(r.v);

        ctx.textAlign = "left";
        ctx.font = `600 14px ${FONT_FAM}`;
        ctx.fillStyle = "#94a3b8";
        ctx.fillText(r.l.toUpperCase(), skX, rY + 12);

        ctx.textAlign = "right";
        ctx.font = `bold 16px monospace`;
        ctx.fillStyle = "#f8fafc";
        ctx.fillText(r.v > 0 ? r.v.toFixed(2) : "--", skX + skW, rY + 12);

        const barY = rY + 25;
        const fillW = Math.round(Math.min(1, r.v / maxM) * skW);

        // Dark background track
        ctx.fillStyle = "rgba(0, 0, 0, 0.4)";
        rRect(ctx, skX, barY, skW, 10, 5);
        ctx.fill();
        ctx.strokeStyle = "rgba(255, 255, 255, 0.05)";
        ctx.stroke();

        if (fillW > 0) {
          ctx.save();
          // Gradient fill
          const barG = ctx.createLinearGradient(skX, 0, skX + fillW, 0);
          barG.addColorStop(0, "rgba(255, 255, 255, 0.2)"); // Base bar color
          barG.addColorStop(1, valCol);

          ctx.fillStyle = barG;
          rRect(ctx, skX, barY, fillW, 10, 5);
          ctx.fill();

          // Tip energy glow
          ctx.beginPath();
          ctx.arc(skX + fillW - 5, barY + 5, 4, 0, Math.PI * 2);
          ctx.fillStyle = "#ffffff";
          ctx.shadowColor = valCol;
          ctx.shadowBlur = 12;
          ctx.fill();

          ctx.restore();
        }
        rY += rowH;
      }

      // ── 9. NPS PANEL (Premium Telemetry) ───────────────────────────────────
      const boxW = (panW4 - 30) / 2;

      function drawNpsWidget(x, y, label, val, colorHex, shadowRgba) {
        ctx.save();

        // Card background with top radial glow
        const grad = ctx.createLinearGradient(x, y, x, y + panH4);
        grad.addColorStop(0, "rgba(20, 25, 35, 0.9)");
        grad.addColorStop(1, "rgba(10, 13, 18, 0.9)");
        ctx.fillStyle = grad;
        rRect(ctx, x, y, boxW, panH4, 16);
        ctx.fill();

        // Highlight top
        ctx.beginPath(); rRect(ctx, x, y, boxW, panH4, 16); ctx.clip();
        const radGlow = ctx.createRadialGradient(x + boxW / 2, y, 0, x + boxW / 2, y, 100);
        radGlow.addColorStop(0, shadowRgba);
        radGlow.addColorStop(1, "transparent");
        ctx.fillStyle = radGlow;
        ctx.fillRect(x, y, boxW, panH4);

        // Border
        ctx.strokeStyle = "rgba(255, 255, 255, 0.06)";
        ctx.lineWidth = 1.5;
        rRect(ctx, x, y, boxW, panH4, 16);
        ctx.stroke();
        ctx.restore();

        // Color indicator dot next to label
        ctx.beginPath();
        ctx.arc(x + boxW / 2 - ctx.measureText(label).width / 2 - 25, y + 46, 4, 0, Math.PI * 2);
        ctx.fillStyle = colorHex;
        ctx.shadowColor = colorHex; ctx.shadowBlur = 8;
        ctx.fill(); ctx.shadowBlur = 0;

        ctx.textAlign = "center";
        ctx.font = `700 14px ${FONT_FAM}`;
        ctx.fillStyle = "#94a3b8";
        ctx.letterSpacing = "1.5px";
        ctx.fillText(label, x + boxW / 2 + 10, y + 50);
        ctx.letterSpacing = "0px";

        // Large main value
        ctx.font = `900 58px ${FONT_FAM}`;
        ctx.fillStyle = colorHex;
        ctx.shadowColor = shadowRgba;
        ctx.shadowBlur = 25;
        ctx.fillText(val.toFixed(1), x + boxW / 2, y + 125);
        ctx.shadowBlur = 0;

        // Label text
        ctx.font = `600 12px ${FONT_FAM}`;
        ctx.fillStyle = "rgba(255,255,255,0.2)";
        ctx.fillText("NOTES / SEC", x + boxW / 2, y + 150);
      }

      drawNpsWidget(panX4, panY4, "DOM NPS", dominantNps, "#00f0ff", "rgba(0, 240, 255, 0.3)"); // Cyan brillante
      drawNpsWidget(panX4 + boxW + 30, panY4, "PEAK NPS", pkY, "#ff2a6d", "rgba(255, 42, 109, 0.3)"); // Rosa neón

      // ── 10. CAPTURE (UNTOUCHED) ────────────────────────────────────────────
      _doCapture();

      function _doCapture() {
        try {
          console.log("[CHART] _doCapture called");
          const fn = `${artist} - ${title} [${version}]`;

          const b64 = canvas.toDataURL("image/png");

          console.log("[CHART] b64 length:", b64.length, "fn:", fn);
          if (typeof setChartGenerating === "function") setChartGenerating(false);
          if (window.pywebview && window.pywebview.api && window.pywebview.api.save_chart) {
            console.log("[CHART] Calling save_chart...");
            window.pywebview.api.save_chart(b64, fn).then(res => {
              if (typeof showToast === "function") {
                if (res.status === "ok") showToast(res.message || "✓ Imagen generada", 2000);
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
      console.error("[CHART] Exception in renderExportChart:", err);
      if (typeof showToast === "function") showToast("Error en renderExportChart: " + (err.message || err), 4000);
      if (typeof setChartGenerating === "function") setChartGenerating(false);
    }
  } catch (err) {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.log_js_error) {
      window.pywebview.api.log_js_error(err.stack || err.toString());
    } else {
      console.error("[CHART ERROR]", err);
    }
  }
}