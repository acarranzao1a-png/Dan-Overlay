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

        // ── Logical Helpers ──────────────────────────────────────────────────
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

        const CS = [
          [0, [18, 76, 196]], [4, [26, 150, 224]], [8, [31, 214, 209]], [12, [79, 223, 110]],
          [16, [185, 224, 76]], [20, [246, 191, 44]], [24, [255, 136, 52]], [30, [248, 72, 56]],
          [38, [210, 56, 129]], [48, [156, 84, 236]], [60, [214, 168, 255]]
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
            if (!seen[x] || nps > prof[x]) { prof[x] = nps; seen[x] = 1 }
          }
          let last = 0; for (let i = 0; i < width; i++) { if (seen[i]) last = prof[i]; else prof[i] = last }
          let nxt = 0; for (let i = width - 1; i >= 0; i--) { if (seen[i]) nxt = prof[i]; else if (prof[i] <= 0) prof[i] = nxt }
          return prof;
        }

        function smoothProfile(vals, radius) {
          if (!vals.length) return [];
          radius = Math.max(1, radius); const n = vals.length, out = new Float64Array(n);
          const pfx = new Float64Array(n + 1); for (let i = 0; i < n; i++) pfx[i + 1] = pfx[i] + vals[i];
          for (let i = 0; i < n; i++) {
            const lo = Math.max(0, i - radius), hi = Math.min(n, i + radius + 1);
            out[i] = (pfx[hi] - pfx[lo]) / (hi - lo);
          }
          return out;
        }

        // ── Glass Panels ─────────────────────────────────────────────────────
        function drawGlassPanel(x, y, w, h) {
          ctx.save();
          ctx.shadowColor = "rgba(0, 0, 0, 0.65)";
          ctx.shadowBlur = 40;
          ctx.shadowOffsetY = 20;

          const grad = ctx.createLinearGradient(x, y, x, y + h);
          grad.addColorStop(0, "rgba(22, 27, 39, 0.88)");
          grad.addColorStop(1, "rgba(13, 16, 23, 0.96)");
          ctx.fillStyle = grad;

          rRect(ctx, x, y, w, h, 24);
          ctx.fill();
          ctx.restore();

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

          ctx.strokeStyle = "rgba(255, 255, 255, 0.03)";
          ctx.lineWidth = 1;
          rRect(ctx, x, y, w, h, 24);
          ctx.stroke();
          ctx.restore();
        }

        const FONT_FAM = "'Inter', 'Segoe UI', 'Bahnschrift', sans-serif";

        // ── 1. Background (Crisp Artwork with Dark Overlay & Vignette) ────────
        if (bgImg && bgImg.naturalWidth > 0) {
          const imgW = bgImg.naturalWidth, imgH = bgImg.naturalHeight;
          const scale = Math.max(W / imgW, H / imgH);
          const sw = W / scale, sh = H / scale;
          const sx = (imgW - sw) / 2, sy = (imgH - sh) / 2;

          ctx.drawImage(bgImg, sx, sy, sw, sh, 0, 0, W, H);

          const darkOverlay = ctx.createLinearGradient(0, 0, 0, H);
          darkOverlay.addColorStop(0, "rgba(9, 11, 18, 0.76)");
          darkOverlay.addColorStop(0.5, "rgba(10, 13, 20, 0.84)");
          darkOverlay.addColorStop(1, "rgba(6, 8, 13, 0.92)");
          ctx.fillStyle = darkOverlay;
          ctx.fillRect(0, 0, W, H);

          const vig = ctx.createRadialGradient(W / 2, H / 2, W * 0.25, W / 2, H / 2, W * 0.75);
          vig.addColorStop(0, "rgba(0, 0, 0, 0)");
          vig.addColorStop(1, "rgba(0, 0, 0, 0.55)");
          ctx.fillStyle = vig;
          ctx.fillRect(0, 0, W, H);
        } else {
          const bg = ctx.createLinearGradient(0, 0, W, H);
          bg.addColorStop(0, "#090a10");
          bg.addColorStop(0.5, "#0d0f17");
          bg.addColorStop(1, "#050608");
          ctx.fillStyle = bg;
          ctx.fillRect(0, 0, W, H);

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
          ctx.restore();
        }

        // ── 2. Initial Data ──────────────────────────────────────────────────
        const meta = payload.parsed_meta || {};
        const bpm = Math.round(meta.bpm || 0), od = meta.od ? meta.od.toFixed(1) : "0.0";
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
        maxY = Math.ceil(maxY / 5) * 5;

        // ── 3. Layout Geometry ───────────────────────────────────────────────
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

        let maxS = 0, maxSIdx = 0;
        for (let i = 0; i < cW; i++) {
          if (sProfRaw[i] > maxS) { maxS = sProfRaw[i]; maxSIdx = i; }
        }

        const sProf = new Float64Array(cW);
        const scaleS = (pkY > 0 && maxS > 0) ? (pkY / maxS) : 1.0;
        for (let i = 0; i < cW; i++) { sProf[i] = sProfRaw[i] * scaleS; }

        // ── 4. HEADER ────────────────────────────────────────────────────────
        ctx.textAlign = "left";
        ctx.font = `900 36px ${FONT_FAM}`;
        ctx.fillStyle = "#ffffff";
        ctx.fillText("DanOverlay", 45, 65);

        ctx.fillStyle = "#ff2a6d";
        ctx.beginPath(); ctx.arc(260, 53, 4, 0, Math.PI * 2); ctx.fill();

        ctx.font = `700 13px ${FONT_FAM}`;
        ctx.fillStyle = "#64748b";
        ctx.letterSpacing = "2px";
        ctx.fillText("NOTE DENSITY CHART", 275, 57);
        ctx.letterSpacing = "0px";

        // Badges on top right
        const danShort = payload.dan_short || "";
        const danSub = payload.dan_sublevel || "";
        const fam = payload.family || "";
        const overall_msd = payload.overall_msd || 0.0;
        const rateLabel = payload.rate_label || meta.rate_label || "";

        let curX = W - 40;
        function drawBadge(txt, bgCol, textCol, strokeCol) {
          ctx.font = `bold 14px ${FONT_FAM}`;
          const tw = ctx.measureText(txt).width;
          const bw = tw + 28, bh = 34;
          curX -= bw;
          ctx.fillStyle = bgCol;
          rRect(ctx, curX, 35, bw, bh, 8);
          ctx.fill();
          if (strokeCol) {
            ctx.strokeStyle = strokeCol;
            ctx.lineWidth = 1;
            ctx.stroke();
          }
          ctx.fillStyle = textCol;
          ctx.fillText(txt, curX + 14, 57);
          curX -= 12;
        }

        if (overall_msd > 0) drawBadge(`${overall_msd.toFixed(2)} MSD`, "rgba(157, 78, 221, 0.25)", "#d8a4ff", "rgba(157, 78, 221, 0.4)");
        if (fam) drawBadge(fam.toUpperCase(), "rgba(255, 255, 255, 0.08)", "#cbd5e1");
        if (danShort) drawBadge(danShort + (danSub ? ` ${danSub}` : ""), "rgba(255, 255, 255, 0.08)", "#ffffff");
        if (rateLabel) drawBadge(rateLabel, "rgba(245, 158, 11, 0.22)", "#fbbf24", "rgba(245, 158, 11, 0.5)");

        // ── 5. DRAW PANELS ───────────────────────────────────────────────────
        drawGlassPanel(panX1, panY1, panW1, panH1);
        drawGlassPanel(panX2, panY2, panW2, panH2);
        drawGlassPanel(panX3, panY3, panW3, panH3);

        // ── 6. NPS GRAPH AREA ────────────────────────────────────────────────
        const yStep = 9;
        ctx.lineWidth = 1;
        ctx.textAlign = "right";

        for (let v = 0; v <= maxY; v += yStep) {
          const y = bot - (v / maxY) * cH;
          ctx.strokeStyle = v === 0 ? "rgba(255, 255, 255, 0.15)" : "rgba(255, 255, 255, 0.03)";
          ctx.beginPath(); ctx.moveTo(cX, y); ctx.lineTo(cX + cW, y); ctx.stroke();

          ctx.fillStyle = "#475569";
          ctx.font = `600 12px ${FONT_FAM}`;
          ctx.fillText(v.toString(), cX - 15, y + 4);
        }

        // Vertical Time grid
        const tStart = nps_data[0][0], tEnd = nps_data[nps_data.length - 1][0];
        const spanS = Math.max(1, (tEnd - tStart) / 1000);
        const tStepS = spanS > 240 ? 60 : (spanS > 120 ? 30 : 15);

        ctx.font = `600 12px ${FONT_FAM}`;
        ctx.fillStyle = "#475569";

        for (let s = 0; s <= spanS; s += tStepS) {
          if (spanS - s < tStepS * 0.4 && s !== 0) continue;

          const x = cX + (s / spanS) * cW;
          ctx.strokeStyle = "rgba(255, 255, 255, 0.03)";
          ctx.beginPath(); ctx.moveTo(x, cY); ctx.lineTo(x, bot); ctx.stroke();

          ctx.textAlign = s === 0 ? "left" : "center";
          ctx.fillText(fmtT(s), x, bot + 25);
        }

        // Always draw explicit end time marker at the right boundary
        const endX = cX + cW;
        ctx.strokeStyle = "rgba(255, 255, 255, 0.06)";
        ctx.beginPath(); ctx.moveTo(endX, cY); ctx.lineTo(endX, bot); ctx.stroke();
        ctx.textAlign = "right";
        ctx.fillStyle = "#64748b";
        ctx.fillText(fmtT(spanS), endX, bot + 25);

        // Density Path
        ctx.save();
        ctx.beginPath(); ctx.rect(cX, cY - 10, cW, cH + 10); ctx.clip();

        const pathPoints = [];
        for (let i = 0; i < cW; i++) {
          const x = cX + i;
          const y = bot - (sProf[i] / maxY) * cH;
          pathPoints.push([x, y, sProf[i]]);
        }

        for (let i = 0; i < pathPoints.length - 1; i++) {
          const [x1, y1, v1] = pathPoints[i];
          const [x2, y2, v2] = pathPoints[i + 1];

          ctx.fillStyle = mapColor((v1 + v2) / 2, 0.15);
          ctx.beginPath();
          ctx.moveTo(x1, bot);
          ctx.lineTo(x1, y1);
          ctx.lineTo(x2, y2);
          ctx.lineTo(x2, bot);
          ctx.fill();
        }

        ctx.save();
        ctx.shadowColor = "rgba(255, 42, 109, 0.4)";
        ctx.shadowBlur = 12;
        ctx.lineWidth = 3.5;
        ctx.lineJoin = "round";
        ctx.lineCap = "round";

        for (let i = 0; i < pathPoints.length - 1; i++) {
          const [x1, y1, v1] = pathPoints[i];
          const [x2, y2, v2] = pathPoints[i + 1];

          const lineGrad = ctx.createLinearGradient(x1, 0, x2, 0);
          lineGrad.addColorStop(0, mapColor(v1));
          lineGrad.addColorStop(1, mapColor(v2));

          ctx.strokeStyle = lineGrad;
          ctx.beginPath();
          ctx.moveTo(x1, y1);
          ctx.lineTo(x2, y2);
          ctx.stroke();
        }
        ctx.restore();

        // Peak point
        if (maxSIdx >= 0 && maxSIdx < cW) {
          const pkX_px = cX + maxSIdx;
          const pkY_px = bot - (sProf[maxSIdx] / maxY) * cH;

          ctx.strokeStyle = "rgba(255, 255, 255, 0.15)";
          ctx.lineWidth = 1;
          ctx.setLineDash([4, 4]);
          ctx.beginPath(); ctx.moveTo(pkX_px, pkY_px); ctx.lineTo(pkX_px, bot); ctx.stroke();
          ctx.setLineDash([]);

          ctx.save();
          ctx.shadowColor = "#ffffff";
          ctx.shadowBlur = 15;
          ctx.fillStyle = "#ffffff";
          ctx.beginPath(); ctx.arc(pkX_px, pkY_px, 6, 0, Math.PI * 2); ctx.fill();

          ctx.fillStyle = mapColor(pkY);
          ctx.beginPath(); ctx.arc(pkX_px, pkY_px, 3, 0, Math.PI * 2); ctx.fill();
          ctx.restore();
        }
        ctx.restore();

        // Dominant NPS reference line
        ctx.save();
        const dominantNps_px = bot - (dominantNps / maxY) * cH;

        ctx.strokeStyle = "rgba(0, 240, 255, 0.4)";
        ctx.lineWidth = 1.5;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(cX, dominantNps_px);
        ctx.lineTo(cX + cW, dominantNps_px);
        ctx.stroke();
        ctx.setLineDash([]);

        ctx.fillStyle = "#00f0ff";
        ctx.beginPath();
        ctx.arc(cX, dominantNps_px, 4, 0, Math.PI * 2);
        ctx.fill();

        ctx.font = "bold 16px 'Bahnschrift',sans-serif";
        ctx.fillStyle = "rgba(0, 240, 255, 0.8)";
        ctx.textAlign = "right";
        ctx.fillText(dominantNps.toFixed(1), cX - 10, dominantNps_px + 4);
        ctx.textAlign = "left";
        ctx.restore();

        // ── 7. METADATA PANEL (Banner + Pack + Info + Stats) ─────────────────
        const { artist = "", title = "", version = "", creator = "", format = "" } = meta;
        const pack = (payload.pack || meta.pack || "").trim();
        const notes = meta.note_count || 0, lns = meta.ln_count || 0, drT = meta.drain_time_s || 0;
        const durSec = meta.total_time_ms ? Math.round(meta.total_time_ms / 1000) : drT;

        const isEtterna = !!(payload.is_etterna || format === "sm" || format === "ssc");

        // Option B: Omit STARS and OD for Etterna
        let statBlocks = [];
        if (isEtterna) {
          statBlocks = [
            { l: "BPM", v: bpm.toString() },
            { l: "KEYS", v: `${kc}K` },
            { l: "DUR", v: fmtT(durSec) },
            { l: "LN", v: lns.toString() },
            { l: "NOTES", v: notes.toString() }
          ];
        } else {
          statBlocks = [
            { l: "STARS", v: (meta.sr_official || 0.0).toFixed(2) },
            { l: "OD", v: od },
            { l: "BPM", v: bpm.toString() },
            { l: "KEYS", v: `${kc}K` },
            { l: "DUR", v: fmtT(durSec) },
            { l: "LN", v: lns.toString() },
            { l: "NOTES", v: notes.toString() }
          ];
        }

        // Banner card geometry (proportional fit to show full banner without cropping)
        const hasBanner = !!(bannerImg && bannerImg.naturalWidth > 0);
        let bannerW = 0, bannerH = 0, bannerX = panX2 + 25, bannerY = panY2 + 25;

        if (hasBanner) {
          const bImgW = bannerImg.naturalWidth;
          const bImgH = bannerImg.naturalHeight;
          const imgRatio = bImgW / Math.max(1, bImgH);

          // Standard StepMania banner is 256x80 or 512x160 (ratio 3.2:1) or 418x164 (ratio 2.55:1)
          // Target box bounds: max width 350px, max height 130px
          const maxBW = 350, maxBH = 130;
          if (imgRatio >= maxBW / maxBH) {
            bannerW = maxBW;
            bannerH = Math.round(maxBW / imgRatio);
          } else {
            bannerH = maxBH;
            bannerW = Math.round(maxBH * imgRatio);
          }

          // Vertically center banner inside panel 2
          bannerY = panY2 + Math.round((panH2 - bannerH) / 2);

          ctx.save();
          ctx.shadowColor = "rgba(0, 0, 0, 0.65)";
          ctx.shadowBlur = 24;
          ctx.shadowOffsetY = 8;

          rRect(ctx, bannerX, bannerY, bannerW, bannerH, 12);
          ctx.fillStyle = "#0c1017";
          ctx.fill();
          ctx.restore();

          ctx.save();
          ctx.beginPath();
          rRect(ctx, bannerX, bannerY, bannerW, bannerH, 12);
          ctx.clip();

          // Draw full banner completely without cropping
          ctx.drawImage(bannerImg, 0, 0, bImgW, bImgH, bannerX, bannerY, bannerW, bannerH);

          // Glass overlay on banner
          const bGrad = ctx.createLinearGradient(bannerX, bannerY, bannerX, bannerY + bannerH);
          bGrad.addColorStop(0, "rgba(255, 255, 255, 0.10)");
          bGrad.addColorStop(1, "rgba(0, 0, 0, 0.30)");
          ctx.fillStyle = bGrad;
          ctx.fillRect(bannerX, bannerY, bannerW, bannerH);

          // Glass border
          ctx.strokeStyle = "rgba(255, 255, 255, 0.18)";
          ctx.lineWidth = 1.5;
          rRect(ctx, bannerX, bannerY, bannerW, bannerH, 12);
          ctx.stroke();
          ctx.restore();
        }

        // Dynamic card widths and start position
        const statCardWidth = hasBanner ? 90 : (isEtterna ? 115 : 85);
        const totalStatsWidth = statBlocks.length * statCardWidth;
        const statsStartX = panX2 + panW2 - totalStatsWidth - 20;

        const mX = hasBanner ? (bannerX + bannerW + 25) : (panX2 + 40);
        const maxTextWidth = Math.max(160, statsStartX - mX - 25);
        let mY = panY2 + (pack ? 46 : 55);

        // Pack Header (clean without redundant "PACK" word)
        if (pack) {
          ctx.textAlign = "left";
          ctx.font = `800 12px ${FONT_FAM}`;
          ctx.letterSpacing = "1.2px";
          ctx.fillStyle = "#38bdf8";
          const safePack = truncateText(ctx, pack.toUpperCase(), maxTextWidth);
          ctx.fillText(safePack, mX, mY);
          ctx.letterSpacing = "0px";
          mY += (hasBanner ? 26 : 28);
        }

        // Title
        ctx.textAlign = "left";
        ctx.font = hasBanner ? `900 32px ${FONT_FAM}` : `900 38px ${FONT_FAM}`;
        ctx.fillStyle = "#ffffff";
        ctx.shadowColor = "rgba(0,0,0,0.6)"; ctx.shadowBlur = 8; ctx.shadowOffsetY = 4;
        const safeTitle = truncateText(ctx, title, maxTextWidth);
        ctx.fillText(safeTitle, mX, mY);
        ctx.shadowBlur = 0; ctx.shadowOffsetY = 0;

        // Artist
        mY += (hasBanner ? 25 : 30);
        ctx.font = `600 ${hasBanner ? 17 : 20}px ${FONT_FAM}`;
        ctx.fillStyle = "#94a3b8";
        const safeArtist = truncateText(ctx, artist, maxTextWidth);
        ctx.fillText(safeArtist, mX, mY);

        // Difficulty pill & Rate badge & Charter
        mY += (hasBanner ? 29 : 34);
        const diffText = version;
        ctx.font = `bold 14px ${FONT_FAM}`;
        const diffW = ctx.measureText(diffText).width + 22;

        const pGrad = ctx.createLinearGradient(mX, 0, mX + diffW, 0);
        pGrad.addColorStop(0, "#9d4edd"); pGrad.addColorStop(1, "#c77dff");
        ctx.fillStyle = pGrad;
        rRect(ctx, mX, mY - 17, diffW, 24, 12);
        ctx.fill();
        ctx.fillStyle = "#ffffff";
        ctx.fillText(diffText, mX + 11, mY);

        let nextBadgeX = mX + diffW + 10;

        // Active rate pill next to difficulty (if active)
        if (rateLabel) {
          ctx.font = `bold 13px ${FONT_FAM}`;
          const rateW = ctx.measureText(rateLabel).width + 18;
          const rGrad = ctx.createLinearGradient(nextBadgeX, 0, nextBadgeX + rateW, 0);
          rGrad.addColorStop(0, "#d97706"); rGrad.addColorStop(1, "#f59e0b");
          ctx.fillStyle = rGrad;
          rRect(ctx, nextBadgeX, mY - 17, rateW, 24, 12);
          ctx.fill();
          ctx.fillStyle = "#ffffff";
          ctx.fillText(rateLabel, nextBadgeX + 9, mY);
          nextBadgeX += rateW + 14;
        } else {
          nextBadgeX += 4;
        }

        if (creator && creator.trim()) {
          const labelText = isEtterna ? "Charter" : "Mapped by";
          ctx.font = `16px ${FONT_FAM}`;
          ctx.fillStyle = "#6e7681";
          ctx.fillText(labelText, nextBadgeX, mY);
          nextBadgeX += ctx.measureText(labelText + " ").width;

          ctx.fillStyle = "#e2e8f0";
          ctx.font = `bold 16px ${FONT_FAM}`;
          const safeCreator = truncateText(ctx, creator.trim(), maxTextWidth - nextBadgeX + mX);
          ctx.fillText(safeCreator, nextBadgeX, mY);
        }

        // Technical info
        mY += (hasBanner ? 25 : 30);
        const tech = `SAMPLES: ${nps_data.length}  •  HOP: ${density_meta.hop_ms || 0}MS  •  WINDOW: ${density_meta.segment_ms || 0}MS`;
        ctx.font = `600 11px ${FONT_FAM}`;
        ctx.fillStyle = "#475569";
        ctx.letterSpacing = "1px";
        ctx.fillText(tech, mX, mY);
        ctx.letterSpacing = "0px";

        // Render Stat Cards
        let sx = statsStartX;
        const sy = panY2 + 45;

        statBlocks.forEach((sb, idx) => {
          ctx.fillStyle = "rgba(255, 255, 255, 0.02)";
          rRect(ctx, sx, sy, statCardWidth - 10, 90, 12);
          ctx.fill();

          ctx.fillStyle = "rgba(255, 255, 255, 0.1)";
          ctx.beginPath();
          ctx.roundRect(sx, sy, 3, 90, [12, 0, 0, 12]);
          ctx.fill();

          ctx.textAlign = "center";

          ctx.font = `900 ${hasBanner && statCardWidth < 105 ? 20 : 24}px ${FONT_FAM}`;
          ctx.fillStyle = "#ffffff";
          ctx.fillText(sb.v, sx + (statCardWidth - 10) / 2, sy + 45);

          ctx.font = `700 12px ${FONT_FAM}`;
          ctx.fillStyle = "#64748b";
          ctx.fillText(sb.l, sx + (statCardWidth - 10) / 2, sy + 70);

          sx += statCardWidth;
        });

        // ── 8. SKILLSETS PANEL ───────────────────────────────────────────────
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

          ctx.fillStyle = "rgba(0, 0, 0, 0.4)";
          rRect(ctx, skX, barY, skW, 10, 5);
          ctx.fill();
          ctx.strokeStyle = "rgba(255, 255, 255, 0.05)";
          ctx.stroke();

          if (fillW > 0) {
            ctx.save();
            const barG = ctx.createLinearGradient(skX, 0, skX + fillW, 0);
            barG.addColorStop(0, "rgba(255, 255, 255, 0.2)");
            barG.addColorStop(1, valCol);

            ctx.fillStyle = barG;
            rRect(ctx, skX, barY, fillW, 10, 5);
            ctx.fill();

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

        // ── 9. NPS PANEL ─────────────────────────────────────────────────────
        const boxW = (panW4 - 30) / 2;

        function drawNpsWidget(x, y, label, val, colorHex, shadowRgba) {
          ctx.save();

          const grad = ctx.createLinearGradient(x, y, x, y + panH4);
          grad.addColorStop(0, "rgba(20, 25, 35, 0.9)");
          grad.addColorStop(1, "rgba(10, 13, 18, 0.9)");
          ctx.fillStyle = grad;
          rRect(ctx, x, y, boxW, panH4, 16);
          ctx.fill();

          ctx.beginPath(); rRect(ctx, x, y, boxW, panH4, 16); ctx.clip();
          const radGlow = ctx.createRadialGradient(x + boxW / 2, y, 0, x + boxW / 2, y, 100);
          radGlow.addColorStop(0, shadowRgba);
          radGlow.addColorStop(1, "transparent");
          ctx.fillStyle = radGlow;
          ctx.fillRect(x, y, boxW, panH4);

          ctx.strokeStyle = "rgba(255, 255, 255, 0.06)";
          ctx.lineWidth = 1.5;
          rRect(ctx, x, y, boxW, panH4, 16);
          ctx.stroke();
          ctx.restore();

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

          ctx.font = `900 58px ${FONT_FAM}`;
          ctx.fillStyle = colorHex;
          ctx.shadowColor = shadowRgba;
          ctx.shadowBlur = 25;
          ctx.fillText(val.toFixed(1), x + boxW / 2, y + 125);
          ctx.shadowBlur = 0;

          ctx.font = `600 12px ${FONT_FAM}`;
          ctx.fillStyle = "rgba(255,255,255,0.2)";
          ctx.fillText("NOTES / SEC", x + boxW / 2, y + 150);
        }

        drawNpsWidget(panX4, panY4, "DOM NPS", dominantNps, "#00f0ff", "rgba(0, 240, 255, 0.3)");
        drawNpsWidget(panX4 + boxW + 30, panY4, "PEAK NPS", pkY, "#ff2a6d", "rgba(255, 42, 109, 0.3)");

        // ── 10. CAPTURE ──────────────────────────────────────────────────────
        let captured = false;
        _doCapture();

        function _doCapture() {
          if (captured) return;
          captured = true;
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