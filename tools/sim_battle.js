function run(opts) {
  const { mode = 'aim', lead = .6, spreadDeg = 8, iframe = 0, seed0 = 20261112 } = opts;
  const W = 420, H = 315, k = W / 360, r = Math.min(W, H) * 0.11;
  const sz = Math.round(30 * k), reach = sz * 0.34, bs = 300 * k;
  const MAX_HP = 10, spread = spreadDeg * Math.PI / 180;
  const T1 = '1还要为你流多少次泪', T2 = '我们不要再计较过去了';
  let seed = seed0;
  function rnd() { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; }
  const b = [
    { x: W * .26, y: H * .32, vx: 148 * k, vy: 201 * k, r, text: T1, idx: 0, spawn: 0, hp: MAX_HP, down: false, last: -9 },
    { x: W * .74, y: H * .68, vx: -179 * k, vy: -147 * k, r, text: T2, idx: 0, spawn: .27, hp: MAX_HP, down: false, last: -9 }
  ];
  let bullets = [], pairs = 0, fired = 0, bh = 0, overAt = -1, winner = '';
  const h = 1 / 240;
  let n = 0, t = 0;
  function trigger(i) {
    const q = b[i]; if (!q || q.down) return;
    if (iframe > 0 && t - q.last < iframe) return;
    q.last = t;
    q.hp = Math.max(0, q.hp - 1);
    if (q.hp <= 0) {
      q.down = true;
      bullets = bullets.filter(p => p.owner !== i);
      overAt = +t.toFixed(2);
      winner = b[0].down && b[1].down ? '同时倒地' : (i === 0 ? '情种2 胜' : '情种1 胜');
    }
  }
  for (; n < 180 / h; n++) {
    if (overAt >= 0) break;
    t = n * h;
    for (let i = 0; i < 2; i++) {
      const q = b[i]; q.x += q.vx * h; q.y += q.vy * h;
      if (q.x - q.r < 0) { q.x = q.r; q.vx = Math.abs(q.vx); }
      else if (q.x + q.r > W) { q.x = W - q.r; q.vx = -Math.abs(q.vx); }
      if (q.y - q.r < 0) { q.y = q.r; q.vy = Math.abs(q.vy); }
      else if (q.y + q.r > H) { q.y = H - q.r; q.vy = -Math.abs(q.vy); }
      q.spawn += h;
      if (q.spawn >= .55 && !q.down) {
        q.spawn -= .55;
        let vx, vy;
        if (mode === 'old') {
          const m = Math.hypot(q.vx, q.vy) || 1;
          vx = q.vx / m * bs; vy = q.vy / m * bs;
        } else {
          const foe = b[1 - i], dist = Math.hypot(foe.x - q.x, foe.y - q.y), flight = dist / bs;
          const px = Math.max(0, Math.min(W, foe.x + foe.vx * flight * lead));
          const py = Math.max(0, Math.min(H, foe.y + foe.vy * flight * lead));
          const a = Math.atan2(py - q.y, px - q.x) + (rnd() - .5) * 2 * spread;
          vx = Math.cos(a) * bs; vy = Math.sin(a) * bs;
        }
        bullets.push({ x: q.x, y: q.y, vx, vy, owner: i, ch: q.text[q.idx] });
        q.idx = (q.idx + 1) % q.text.length; fired++;
      }
    }
    const a = b[0], c = b[1], dx = c.x - a.x, dy = c.y - a.y, d = Math.hypot(dx, dy), min = 2 * r;
    if (d > 0 && d < min) {
      const nx = dx / d, ny = dy / d, ov = min - d;
      a.x -= nx * ov / 2; a.y -= ny * ov / 2; c.x += nx * ov / 2; c.y += ny * ov / 2;
      const rv = (c.vx - a.vx) * nx + (c.vy - a.vy) * ny;
      if (rv < 0) {
        const imp = -rv;
        a.vx -= imp * nx; a.vy -= imp * ny; c.vx += imp * nx; c.vy += imp * ny;
        pairs++; trigger(0); trigger(1);
      }
    }
    for (let j = bullets.length - 1; j >= 0; j--) {
      const p = bullets[j]; p.x += p.vx * h; p.y += p.vy * h;
      if (p.x < -40 || p.x > W + 40 || p.y < -40 || p.y > H + 40) { bullets.splice(j, 1); continue; }
      const tg = b[1 - p.owner];
      if (!tg.down && Math.hypot(p.x - tg.x, p.y - tg.y) < tg.r + reach) {
        if (!(iframe > 0 && t - tg.last < iframe)) { bh++; trigger(1 - p.owner); }
        bullets.splice(j, 1);
      }
    }
  }
  return {
    label: mode === 'old' ? '旧版' : ('预判' + lead + ' ±' + spreadDeg + '°' + (iframe ? ' 无敌' + iframe + 's' : '')),
    fired, bh, rate: (100 * bh / fired).toFixed(1) + '%', pairs, overAt, winner, hp: b.map(x => x.hp)
  };
}

const configs = [
  { label: '旧版(沿自身方向)', mode: 'old' },
  { label: '预判0.6 ±8° 无无敌帧', lead: .6, spreadDeg: 8, iframe: 0 },
  { label: '预判0.6 ±8° 无敌0.55s', lead: .6, spreadDeg: 8, iframe: .55 },
  { label: '预判0.3 ±8° 无敌0.55s', lead: .3, spreadDeg: 8, iframe: .55 },
];
const seeds = [20261112, 7, 421, 9001, 55555, 314159, 8888];
for (const cfg of configs) {
  const rs = seeds.map(s => run(Object.assign({}, cfg, { seed0: s })));
  const avg = key => (rs.reduce((a, x) => a + x[key], 0) / rs.length).toFixed(2);
  const rates = rs.map(x => parseFloat(x.rate));
  console.log(cfg.label.padEnd(26) +
    ' | 平均发射 ' + avg('fired').padStart(6) +
    ' | 平均命中 ' + avg('bh').padStart(5) +
    ' | 命中率 ' + (rates.reduce((a, b) => a + b, 0) / rates.length).toFixed(1) + '%' +
    ' | 平均倒地 ' + avg('overAt').padStart(5) + 's' +
    ' | 倒地范围 ' + Math.min(...rs.map(x => x.overAt)) + '~' + Math.max(...rs.map(x => x.overAt)) + 's');
}
