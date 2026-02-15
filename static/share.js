/* ── GhostRadar Share Card (Canvas) ── */

window.shareScore = function () {
  fetch('/api/event', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ event_name: 'share_clicked' }),
  }).catch(() => {});

  const r = window.__lastResult;
  if (!r) return;

  const W = 600, H = 400;
  const canvas = document.createElement('canvas');
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext('2d');

  // Background
  const grad = ctx.createLinearGradient(0, 0, W, H);
  grad.addColorStop(0, '#0a0a0f');
  grad.addColorStop(1, '#1a1025');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, W, H);

  // Accent line
  const lg = ctx.createLinearGradient(0, 0, W, 0);
  lg.addColorStop(0, '#7c3aed');
  lg.addColorStop(1, '#06d6a0');
  ctx.strokeStyle = lg;
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.moveTo(40, 60);
  ctx.lineTo(W - 40, 60);
  ctx.stroke();

  // Title
  ctx.fillStyle = '#a855f7';
  ctx.font = 'bold 28px Inter, sans-serif';
  ctx.fillText('GhostRadar', 40, 48);

  // Scores
  const scores = [
    { label: 'Interest', value: r.interest_score, color: '#06d6a0' },
    { label: 'Ghost Risk', value: r.ghost_probability, color: '#ef4444' },
    { label: 'Red Flags', value: r.red_flag_risk, color: '#f59e0b' },
    { label: 'Distance', value: r.emotional_distance, color: '#7c3aed' },
  ];

  const startY = 110;
  const colW = (W - 80) / 4;

  scores.forEach((s, i) => {
    const cx = 40 + colW * i + colW / 2;

    // Circle bg
    ctx.beginPath();
    ctx.arc(cx, startY + 50, 42, 0, Math.PI * 2);
    ctx.strokeStyle = '#27272a';
    ctx.lineWidth = 5;
    ctx.stroke();

    // Circle filled arc
    const pct = s.value / 100;
    ctx.beginPath();
    ctx.arc(cx, startY + 50, 42, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * pct);
    ctx.strokeStyle = s.color;
    ctx.lineWidth = 5;
    ctx.stroke();

    // Value
    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 26px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(s.value, cx, startY + 58);

    // Label
    ctx.fillStyle = '#71717a';
    ctx.font = '12px Inter, sans-serif';
    ctx.fillText(s.label, cx, startY + 110);
  });

  ctx.textAlign = 'left';

  // Prediction
  ctx.fillStyle = '#71717a';
  ctx.font = '14px Inter, sans-serif';
  ctx.fillText('Reply window: ' + (r.reply_window || '—'), 40, 310);
  ctx.fillText('Confidence: ' + (r.confidence || '—'), 40, 335);

  // Watermark
  ctx.fillStyle = '#52525b';
  ctx.font = '12px Inter, sans-serif';
  ctx.textAlign = 'right';
  ctx.fillText('ghostradar.app', W - 40, H - 20);

  // Download
  canvas.toBlob(blob => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'ghostradar-score.png';
    a.click();
    URL.revokeObjectURL(url);

    fetch('/api/event', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event_name: 'share_downloaded' }),
    }).catch(() => {});
  }, 'image/png');
};
