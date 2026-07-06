/* =====================================================================
 * AI 替代风险测评 · 应用主控 (app.js)
 * 状态管理 / 页面流转 / 滑块交互 / 仪表盘+雷达绘制 / 沙盘推演 / 付费锁
 * ===================================================================== */
(function () {
  'use strict';
  const D = window.APP_DATA;
  const E = window.Engine;
  const P = D.palette;

  /* ---------------- 状态管理 ---------------- */
  const defaultState = {
    userJob: '', jobBaselineRisk: 60, currentQuestionIndex: 0,
    answers: {}, sandboxState: { ai: 0, collab: 0, agile: 0 }, unlocked: false
  };
  let state = loadState();

  function loadState() {
    try {
      const raw = localStorage.getItem(D.storageKey);
      if (raw) return Object.assign({}, defaultState, JSON.parse(raw));
    } catch (e) {}
    return JSON.parse(JSON.stringify(defaultState));
  }
  function saveState() {
    try { localStorage.setItem(D.storageKey, JSON.stringify(state)); } catch (e) {}
  }

  /* 模块内暂存：首页解析出的基线 */
  let pending = { job: '', base: 60, group: 'mid', resolved: false };

  /* ---------------- DOM 速查 ---------------- */
  const $ = (id) => document.getElementById(id);
  const views = { hero: $('view-hero'), quiz: $('view-quiz'), result: $('view-result') };
  function showView(name) {
    Object.values(views).forEach(v => v.classList.remove('active'));
    views[name].classList.add('active');
    window.scrollTo(0, 0);
  }

  /* 风险 → 颜色 */
  function riskColor(v) {
    return v >= 60 ? P.danger : (v >= 35 ? P.warn : P.safe);
  }

  /* ============================================================
   * 视图 1：破冰首页
   * ========================================================== */
  const jobInput = $('jobInput');
  const baselineReadout = $('baselineReadout');
  const baselineValue = $('baselineValue');
  const baselineRing = $('baselineRing');
  const choiceArea = $('choiceArea');
  const choiceRow = $('choiceRow');
  const ctaBtn = $('ctaBtn');
  const ctaText = $('ctaText');

  let debounceTimer = null;
  jobInput.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(resolveJob, 300);
  });

  function resolveJob() {
    const job = jobInput.value.trim();
    pending.job = job;
    pending.resolved = false;
    choiceArea.style.display = 'none';
    ctaBtn.disabled = true;

    if (!job) { baselineReadout.classList.remove('show'); setTheme(''); return; }

    const res = E.matchBaseline(job);
    if (res.needsChoice) {
      baselineReadout.classList.remove('show');
      renderChoice();
      return;
    }
    pending.base = res.base;
    pending.group = res.group;
    pending.resolved = true;
    setTheme(res.group);
    showBaseline(res.base);
    ctaBtn.disabled = false;
  }

  function renderChoice() {
    choiceArea.style.display = 'block';
    choiceRow.innerHTML = '';
    D.baselineChoice.forEach(c => {
      const b = document.createElement('button');
      b.className = 'choice-btn';
      b.innerHTML = `<b>${c.label}</b><span>${c.desc}</span>`;
      b.onclick = () => {
        pending.base = c.base;
        pending.group = c.base <= 40 ? 'low' : (c.base >= 80 ? 'high' : 'mid');
        pending.resolved = true;
        choiceArea.style.display = 'none';
        setTheme(pending.group);
        showBaseline(c.base);
        ctaBtn.disabled = false;
      };
      choiceRow.appendChild(b);
    });
  }

  function showBaseline(base) {
    baselineValue.textContent = base;
    const col = riskColor(base);
    baselineRing.style.borderColor = col;
    baselineValue.style.color = col;
    baselineReadout.classList.add('show');
  }

  function setTheme(group) {
    document.body.classList.remove('theme-high', 'theme-mid', 'theme-low');
    if (group) document.body.classList.add('theme-' + group);
  }

  ctaBtn.addEventListener('click', () => {
    if (!pending.resolved) return;
    ctaBtn.classList.add('loading');
    ctaText.textContent = '正在生成你的沙盘…';
    setTimeout(() => {
      state.userJob = pending.job;
      state.jobBaselineRisk = pending.base;
      state.currentQuestionIndex = 0;
      state.answers = {};
      state.sandboxState = { ai: 0, collab: 0, agile: 0 };
      state.unlocked = false;
      saveState();
      ctaBtn.classList.remove('loading');
      ctaText.textContent = '一键开启突围测试';
      startQuiz();
    }, 520);
  });

  /* ============================================================
   * 视图 2：沉浸式测验（单题模式，防漏题）
   * ========================================================== */
  const cardStage = $('cardStage');
  const progressFill = $('progressFill');
  const progNow = $('progNow');
  const progTotal = $('progTotal');
  progTotal.textContent = D.totalQuestions;

  let advancing = false;
  let currentIdx = 0; // 当前在 questionOrder 中的位置

  /* 题目随机打乱（防止社会期许效应）；顺序持久化 */
  function shuffle(arr) {
    const a = arr.slice();
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  function startQuiz() {
    const hasProgress = Object.keys(state.answers).length > 0 && !state.unlocked;
    const orderOk = Array.isArray(state.questionOrder) && state.questionOrder.length === D.totalQuestions;
    if (!hasProgress) {
      state.answers = {};
      state.questionOrder = shuffle(D.questions.map(q => q.n));
      currentIdx = 0;
    } else if (!orderOk) {
      state.questionOrder = shuffle(D.questions.map(q => q.n));
      currentIdx = 0;
    } else {
      // 恢复进度：跳到第一个未答的题目
      currentIdx = 0;
      while (currentIdx < state.questionOrder.length
        && typeof state.answers['dim_' + state.questionOrder[currentIdx]] === 'number') {
        currentIdx++;
      }
      if (currentIdx >= state.questionOrder.length) currentIdx = state.questionOrder.length - 1;
    }
    saveState();
    showView('quiz');
    renderCard(currentIdx, 'right');
  }

  function answeredCount() {
    return state.questionOrder.filter(n => typeof state.answers['dim_' + n] === 'number').length;
  }

  /* 单题卡片渲染 */
  function renderCard(idx, dir) {
    if (idx < 0 || idx >= D.totalQuestions) return;
    advancing = false;
    currentIdx = idx;
    saveState();

    const n = state.questionOrder[idx];
    const q = D.questions.find(x => x.n === n);
    const prev = state.answers['dim_' + n];
    const startVal = (typeof prev === 'number') ? prev : 5;

    // 进度感知
    const done = answeredCount();
    progressFill.style.width = (done / D.totalQuestions) * 100 + '%';
    progNow.textContent = done;

    const isLast = idx === D.totalQuestions - 1;
    const isFirst = idx === 0;

    cardStage.innerHTML = `
      <div class="q-card ${dir === 'right' ? 'slideInRight' : ''}" id="qCard">
        <div class="q-title">${q.question}</div>
        <div class="q-sub">凭直觉拖动滑块，表达你真实的日常工作状态。</div>
        <div class="slider-wrap">
          <div class="slider-value num" id="sv-${n}">${startVal}</div>
          <input type="range" min="0" max="10" step="1" value="${startVal}" class="slider" id="slider-${n}" />
          <div class="slider-anchors">
            <div class="l">1 · ${q.left}</div>
            <div class="r">${q.right} · 10</div>
          </div>
        </div>
      </div>
      <div class="q-actions">
        <button class="btn-ghost" id="backBtn">${isFirst ? '← 首页' : '← 上一题'}</button>
        <button class="btn-primary" id="nextBtn">${isLast ? '生成我的沙盘 →' : '下一题 →'}</button>
      </div>
    `;

    const slider = $('slider-' + n);
    const sv = $('sv-' + n);
    const paint = (v) => {
      sv.textContent = v;
      sv.style.color = riskColor(100 - v * 10);
    };
    paint(startVal);

    slider.addEventListener('input', () => {
      state.answers['dim_' + n] = Number(slider.value);
      paint(Number(slider.value));
      saveState();
      // 实时更新进度条
      const d = answeredCount();
      progressFill.style.width = (d / D.totalQuestions) * 100 + '%';
      progNow.textContent = d;
    });

    $('nextBtn').addEventListener('click', () => {
      if (advancing) return;
      advance(idx);
    });
    $('backBtn').addEventListener('click', () => {
      if (advancing) return;
      if (isFirst) { showView('hero'); return }
      goPrev(idx);
    });
  }

  function advance(idx) {
    advancing = true;
    const wrap = $('qCard');
    if (wrap) wrap.classList.add('slideOutLeft');
    setTimeout(() => {
      if (idx >= D.totalQuestions - 1) { progressFill.style.width = '100%'; finishQuiz(); }
      else { renderCard(idx + 1, 'right'); }
    }, 360);
  }

  function goPrev(idx) {
    advancing = true;
    const wrap = $('qCard');
    if (wrap) wrap.classList.add('slideOutLeft');
    setTimeout(() => { renderCard(idx - 1, 'right'); }, 360);
  }

  function finishQuiz() {
    showView('result');
    renderResult();
  }

  /* ============================================================
   * 视图 3：黄金沙盘预售页
   * ========================================================== */
  const gaugeBig = $('gaugeBig');
  const gaugeSvg = $('gauge');
  const radarSvg = $('radar');
  const idxPanel = $('idxPanel');
  const sandboxSliders = $('sandboxSliders');
  const diagnosisPanel = $('diagnosisPanel');
  const paywallCopy = $('paywallCopy');
  const minRiskEl = $('minRisk');

  let report = null;     // Engine.generate 结果
  let baseRadar = null;  // 原始雷达（0-100）

  function renderResult() {
    report = E.generate(state.answers, state.userJob, state.jobBaselineRisk);
    baseRadar = report.radar;
    state.sandboxState = state.sandboxState || { ai: 0, collab: 0, agile: 0 };
    saveState();

    // 仪表盘（初始）
    drawGauge(report.baseRisk);
    // 雷达
    drawRadar(report.radar);
    // 指数条
    renderIndices(report.indices);
    // 沙盘滑块
    renderSandbox();
    // 诊断文案
    renderDiagnosis(report);
    // 引流锁
    paywallCopy.textContent = report.paywall;
    minRiskEl.textContent = report.minRisk;

    if (state.unlocked) {
      if (followGate) followGate.style.display = 'none';
      payNote.textContent = '✅ 已解锁 · 完整报告已生成';
      const noteEl = $('unlockedNote');
      noteEl.style.whiteSpace = 'pre-line';
      noteEl.style.textAlign = 'left';
      noteEl.style.padding = '20px 16px';
      noteEl.style.background = 'rgba(255,255,255,.08)';
      noteEl.style.borderRadius = '12px';
      noteEl.style.marginTop = '14px';
      noteEl.style.display = 'block';
      noteEl.textContent = report.fullReport || '(报告生成中…)';
    } else {
      payNote.textContent = '关注公众号 · 免费解锁完整报告';
    }
  }

  /* ---- 半环仪表盘 ---- */
  function polar(cx, cy, r, deg) {
    const a = deg * Math.PI / 180;
    return { x: cx + r * Math.cos(a), y: cy - r * Math.sin(a) };
  }
  function arcPath(cx, cy, r, a0, a1) {
    const p0 = polar(cx, cy, r, a0);
    const p1 = polar(cx, cy, r, a1);
    const large = (a0 - a1) > 180 ? 1 : 0;
    return `M ${p0.x.toFixed(2)} ${p0.y.toFixed(2)} A ${r} ${r} 0 ${large} 1 ${p1.x.toFixed(2)} ${p1.y.toFixed(2)}`;
  }
  function drawGauge(value) {
    const cx = 150, cy = 150, r = 120;
    const col = riskColor(value);
    const a1 = 180 - (value / 100) * 180; // 指针角度（左=0% 右=100%）
    const needle = polar(cx, cy, r - 16, a1);
    gaugeSvg.innerHTML = `
      <path d="${arcPath(cx, cy, r, 180, 0)}" stroke="${P.line}" stroke-width="16" fill="none" stroke-linecap="round"/>
      <path d="${arcPath(cx, cy, r, 180, a1)}" stroke="${col}" stroke-width="16" fill="none" stroke-linecap="round"/>
      <line x1="${cx}" y1="${cy}" x2="${needle.x.toFixed(2)}" y2="${needle.y.toFixed(2)}" stroke="${col}" stroke-width="4" stroke-linecap="round"/>
      <circle cx="${cx}" cy="${cy}" r="8" fill="${col}"/>
    `;
    gaugeBig.textContent = value;
    gaugeBig.style.color = col;
  }

  /* ---- 五维雷达图 ---- */
  function drawRadar(rd) {
    const cx = 200, cy = 200, r = 135;
    const axes = ['RIASEC', 'AI素养', '协作', '数字技能', '突围力'];
    const vals = [rd.RIASEC, rd.AI素养, rd.协作, rd.数字技能, rd.突围力];
    const N = axes.length;
    const ang = (i) => -90 + i * (360 / N);

    let grid = '';
    [25, 50, 75, 100].forEach(level => {
      const pts = axes.map((_, i) => {
        const p = polar(cx, cy, r * level / 100, ang(i));
        return `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
      }).join(' ');
      grid += `<polygon points="${pts}" fill="none" stroke="${P.line}" stroke-width="1"/>`;
    });

    let lines = '';
    axes.forEach((_, i) => {
      const p = polar(cx, cy, r, ang(i));
      lines += `<line x1="${cx}" y1="${cy}" x2="${p.x.toFixed(1)}" y2="${p.y.toFixed(1)}" stroke="${P.line}" stroke-width="1"/>`;
    });

    const dataPts = vals.map((v, i) => {
      const p = polar(cx, cy, r * v / 100, ang(i));
      return `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
    }).join(' ');

    let labels = '';
    axes.forEach((ax, i) => {
      const lp = polar(cx, cy, r + 28, ang(i));
      const anchor = Math.abs(lp.x - cx) < 6 ? 'middle' : (lp.x < cx ? 'end' : 'start');
      labels += `<text x="${lp.x.toFixed(1)}" y="${(lp.y + 4).toFixed(1)}" text-anchor="${anchor}" font-size="13" font-weight="700" fill="${P.sub}">${ax}</text>`;
      const vp = polar(cx, cy, r * vals[i] / 100, ang(i));
      labels += `<text x="${vp.x.toFixed(1)}" y="${(vp.y - 6).toFixed(1)}" text-anchor="middle" font-size="12" font-weight="700" fill="${P.safe}">${vals[i]}</text>`;
    });

    radarSvg.innerHTML = `
      ${grid}${lines}
      <polygon points="${dataPts}" fill="rgba(14,159,152,.18)" stroke="${P.safe}" stroke-width="2.5"/>
      ${labels}
    `;
  }

  /* ---- 四大指数条 ---- */
  function renderIndices(idx) {
    const rows = [
      { name: '基础壁垒', v: idx.def },
      { name: '数字驾驭', v: idx.digital },
      { name: '协同演化', v: idx.coev },
      { name: '流程脆弱', v: idx.fragility }
    ];
    idxPanel.innerHTML = '';
    rows.forEach(r => {
      const col = r.v >= 70 ? P.safe : (r.v <= 45 ? P.danger : P.warn);
      const flag = r.name === '流程脆弱'
        ? (idx.danger ? '<span class="idx-flag danger">高危</span>' : '<span class="idx-flag safe">可控</span>')
        : (r.v >= 70 ? '<span class="idx-flag safe">强</span>' : (r.v <= 45 ? '<span class="idx-flag danger">弱</span>' : ''));
      const el = document.createElement('div');
      el.className = 'idx-row';
      el.innerHTML = `
        <div class="name">${r.name}</div>
        <div class="bar"><i style="width:${r.v}%;background:${col}"></i></div>
        <div class="val num">${r.v}</div>
        ${flag}
      `;
      idxPanel.appendChild(el);
    });
  }

  /* ---- 沙盘推演器 ---- */
  function renderSandbox() {
    sandboxSliders.innerHTML = '';
    D.interventions.forEach(iv => {
      const cur = state.sandboxState[iv.key] || 0;
      const wrap = document.createElement('div');
      wrap.className = 'sandbox-slider';
      wrap.innerHTML = `
        <div class="lab">${iv.label}</div>
        <div class="hint">${iv.hint}</div>
        <input type="range" min="0" max="100" step="1" value="${cur}" class="slider" id="sb-${iv.key}" style="background:linear-gradient(90deg,${P.safe},${P.warn} 60%,${P.danger})"/>
      `;
      sandboxSliders.appendChild(wrap);
      const sl = $('sb-' + iv.key);
      sl.addEventListener('input', () => {
        state.sandboxState[iv.key] = Number(sl.value);
        saveState();
        onSandboxChange();
      });
    });
  }

  function onSandboxChange() {
    const f = report.factors;
    const sim = E.simulate(report.rBase, f, state.sandboxState);
    drawGauge(sim.risk);
    // 雷达对应维度实时膨胀
    const rd = Object.assign({}, baseRadar, {
      AI素养: sim.eff.ai, 协作: sim.eff.collab, 突围力: sim.eff.agile
    });
    drawRadar(rd);
  }

  /* ---- 专家诊断文案 ---- */
  function renderDiagnosis(r) {
    const q = r.quadrant;
    diagnosisPanel.innerHTML = `
      <div class="qtag">${q.tagline}</div>
      <div class="qname">${q.name}</div>
      <div class="headline">${q.headline}</div>
      <div class="body">${q.body}</div>
      <div class="advice"><b>突围建议</b><br/>${q.advice}</div>
      <div class="body" style="margin-top:16px;">${r.freePreview}</div>
    `;
  }

  /* ---- 引流解锁：关注公众号后查看完整报告 ---- */
  const followBtn = $('followBtn');
  const followGate = $('followGate');

  /* ---- 解锁成功后的渲染 ---- */
  function unlockSuccess() {
    state.unlocked = true;
    saveState();
    if (followGate) followGate.style.display = 'none';
    payNote.textContent = '✅ 已解锁 · 完整报告已生成';

    let noteEl = $('unlockedNote');
    if (!noteEl) {
      noteEl = document.createElement('div');
      noteEl.id = 'unlockedNote';
      noteEl.className = 'unlocked';
      $('paywall').appendChild(noteEl);
    }
    noteEl.style.display = 'block';
    noteEl.style.whiteSpace = 'pre-line';
    noteEl.style.textAlign = 'left';
    noteEl.style.padding = '20px 16px';
    noteEl.style.background = 'rgba(255,255,255,.08)';
    noteEl.style.borderRadius = '12px';
    noteEl.style.marginTop = '14px';

    setTimeout(() => { noteEl.scrollIntoView({ behavior: 'smooth', block: 'start' }); }, 100);

    noteEl.textContent = '';
    const fullText = report.fullReport || '(报告生成中…)';
    let pos = 0;
    const chunk = Math.ceil(fullText.length / 30);
    function typeChunk() {
      const end = Math.min(pos + chunk, fullText.length);
      noteEl.textContent = fullText.substring(0, end);
      pos = end;
      if (pos < fullText.length) { requestAnimationFrame(typeChunk); }
    }
    typeChunk();
  }

  followBtn.addEventListener('click', () => {
    if (state.unlocked) return;
    unlockSuccess();
  });

  $('resultBack').addEventListener('click', () => {
    showView('hero');
  });

  /* ---- 若已有进度，刷新后停留在结果页（可选） ---- */
  // 默认每次进入都从首页开始，保持体验清晰；状态已持久化可回看。
})();
