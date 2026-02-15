/* ── GhostRadar App JS ── */

(function () {
  'use strict';

  // ── State ──
  let direction = 'they';
  let lastResult = null;
  let scanCount = 0;

  // ── DOM refs ──
  const textarea      = document.getElementById('scan-input');
  const scanBtn       = document.getElementById('scan-btn');
  const dirBtns       = document.querySelectorAll('.dir-btn');
  const scannerOverlay= document.getElementById('scanner-overlay');
  const scannerText   = document.getElementById('scanner-text');
  const resultsSection= document.getElementById('results-section');
  const paywallOverlay= document.getElementById('paywall-overlay');

  // ── Init ──
  logEvent('landed_app');
  loadHistory();

  // ── Direction toggle ──
  dirBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      dirBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      direction = btn.dataset.dir;
    });
  });

  // ── Scan button ──
  scanBtn.addEventListener('click', doScan);

  async function doScan() {
    const text = textarea.value.trim();
    if (!text) { textarea.focus(); return; }

    logEvent('scan_clicked');
    scanBtn.disabled = true;
    showScanner();

    try {
      const res = await fetch('/api/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message_text: text, direction }),
      });

      if (res.status === 402) {
        hideScanner();
        scanBtn.disabled = false;
        showPaywall();
        return;
      }

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || 'Scan failed');
      }

      const data = await res.json();
      lastResult = data;
      window.__lastResult = data;
      scanCount++;

      // Stage the scanner text transitions
      await stageText('Detecting signals…', 600);
      await stageText('Estimating ghost risk…', 600);
      await stageText('Compiling analysis…', 400);

      hideScanner();
      scanBtn.disabled = false;
      renderResults(data);
      loadHistory();

    } catch (err) {
      hideScanner();
      scanBtn.disabled = false;
      alert(err.message);
    }
  }

  // ── Scanner animation ──
  function showScanner() {
    scannerText.textContent = 'Scanning tone…';
    scannerOverlay.classList.add('active');
  }

  function hideScanner() {
    scannerOverlay.classList.remove('active');
  }

  function stageText(text, delay) {
    return new Promise(resolve => {
      setTimeout(() => {
        scannerText.textContent = text;
        resolve();
      }, delay);
    });
  }

  // ── Render results ──
  function renderResults(data) {
    resultsSection.classList.add('visible');

    // Meters
    animateMeter('meter-interest', data.interest_score, colorForScore(data.interest_score, false));
    animateMeter('meter-redflag', data.red_flag_risk, colorForScore(data.red_flag_risk, true));
    animateMeter('meter-distance', data.emotional_distance, colorForScore(data.emotional_distance, true));
    animateMeter('meter-ghost', data.ghost_probability, colorForScore(data.ghost_probability, true));

    // Archetype — always visible
    const archetypeEl = document.getElementById('archetype-badge');
    if (data.archetype) {
      archetypeEl.textContent = data.archetype;
      archetypeEl.style.display = 'inline-block';
    } else {
      archetypeEl.style.display = 'none';
    }

    // Hidden signals panel
    const hsPanel = document.getElementById('hidden-signals-panel');
    const hsCount = document.getElementById('hs-count');
    const hsList  = document.getElementById('hs-list');
    hsCount.textContent = data.hidden_signals_count;

    if (data.locked) {
      hsPanel.classList.add('panel-locked');
      hsList.innerHTML = '<li><span class="signal-title">Signal data</span><br>Details hidden</li>'.repeat(data.hidden_signals_count);
    } else {
      hsPanel.classList.remove('panel-locked');
      hsList.innerHTML = (data.hidden_signals || []).map(s =>
        `<li><span class="signal-title">${esc(s.title)}</span><br>${esc(s.detail)}</li>`
      ).join('');
    }

    // Prediction panel
    document.getElementById('pred-window').textContent = data.reply_window || '—';
    document.getElementById('pred-confidence').textContent = data.confidence || '—';

    // Summary panel — always visible (the AI "voice")
    const summaryPanel = document.getElementById('summary-panel');
    const summaryText  = document.getElementById('summary-text');
    summaryPanel.classList.remove('panel-locked');
    summaryText.textContent = data.summary || '';

    // Replies panel
    const repliesPanel = document.getElementById('replies-panel');
    if (data.locked || !data.replies || !data.replies.soft_confident) {
      repliesPanel.classList.add('panel-locked');
      document.getElementById('reply-soft').textContent = 'Locked';
      document.getElementById('reply-playful').textContent = 'Locked';
      document.getElementById('reply-direct').textContent = 'Locked';
    } else {
      repliesPanel.classList.remove('panel-locked');
      document.getElementById('reply-soft').textContent = data.replies.soft_confident;
      document.getElementById('reply-playful').textContent = data.replies.playful;
      document.getElementById('reply-direct').textContent = data.replies.direct;
    }

    // Scroll to results
    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

    // Locked panels → open paywall
    document.querySelectorAll('.panel-locked').forEach(el => {
      el.onclick = showPaywall;
    });
  }

  // ── Meter animation ──
  function animateMeter(id, value, color) {
    const wrap = document.getElementById(id);
    if (!wrap) return;
    const circle = wrap.querySelector('.meter-ring-fill');
    const valEl  = wrap.querySelector('.meter-value');
    const circumference = 2 * Math.PI * 34; // r=34
    circle.style.stroke = color;
    circle.style.strokeDasharray = circumference;
    circle.style.strokeDashoffset = circumference;

    requestAnimationFrame(() => {
      const offset = circumference - (value / 100) * circumference;
      circle.style.strokeDashoffset = offset;
    });

    // Animate number
    let current = 0;
    const step = Math.max(1, Math.ceil(value / 40));
    const interval = setInterval(() => {
      current += step;
      if (current >= value) { current = value; clearInterval(interval); }
      valEl.textContent = current;
    }, 30);
  }

  function colorForScore(v, danger) {
    if (danger) {
      if (v >= 70) return '#ef4444';
      if (v >= 40) return '#f59e0b';
      return '#06d6a0';
    } else {
      if (v >= 70) return '#06d6a0';
      if (v >= 40) return '#f59e0b';
      return '#ef4444';
    }
  }

  // ── History & trends ──
  async function loadHistory() {
    try {
      const res = await fetch('/api/history');
      if (!res.ok) return;
      const data = await res.json();
      renderTrends(data.trends, data.locked);
    } catch (e) { /* ignore */ }
  }

  function renderTrends(trends, locked) {
    const section = document.getElementById('trend-section');
    if (!trends || (!trends.interest_score && !trends.ghost_probability)) {
      section.style.display = 'none';
      return;
    }
    if (locked) {
      section.classList.add('panel-locked');
    } else {
      section.classList.remove('panel-locked');
    }
    section.style.display = 'block';
    document.getElementById('trend-interest').textContent = capitalize(trends.interest_score || 'stable');
    document.getElementById('trend-interest').className = 'trend-badge ' + (trends.interest_score || 'stable');
    document.getElementById('trend-ghost').textContent = capitalize(trends.ghost_probability || 'stable');
    document.getElementById('trend-ghost').className = 'trend-badge ' + (trends.ghost_probability || 'stable');
  }

  // ── Paywall ──
  function showPaywall() {
    logEvent('paywall_shown');
    paywallOverlay.classList.add('active');
  }

  function hidePaywall() {
    paywallOverlay.classList.remove('active');
  }

  window.hidePaywall = hidePaywall;

  window.checkout = async function (plan) {
    logEvent('checkout_clicked_' + plan);
    try {
      const res = await fetch('/api/create-checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan }),
      });
      const data = await res.json();
      if (data.url) {
        window.location.href = data.url;
      } else {
        alert(data.error || 'Checkout failed');
      }
    } catch (e) {
      alert('Network error');
    }
  };

  // ── Scan another ──
  window.scanAnother = function () {
    textarea.value = '';
    textarea.focus();
    resultsSection.classList.remove('visible');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // ── Reply copy ──
  document.querySelectorAll('.reply-option').forEach(el => {
    el.addEventListener('click', () => {
      const text = el.querySelector('.reply-text')?.textContent;
      if (text && text !== 'Locked') {
        navigator.clipboard.writeText(text).then(() => {
          el.style.borderColor = 'var(--accent-teal)';
          setTimeout(() => el.style.borderColor = '', 1000);
        });
      }
    });
  });

  // ── Event logger ──
  function logEvent(name, meta) {
    fetch('/api/event', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event_name: name, meta: meta || {} }),
    }).catch(() => {});
  }

  // ── Utils ──
  function esc(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  function capitalize(s) {
    return s.charAt(0).toUpperCase() + s.slice(1);
  }
})();
