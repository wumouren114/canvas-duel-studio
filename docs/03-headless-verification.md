# 03 · 无头验证：让动画项目也能被断言

纯 Canvas 的东西最难测：没有 DOM 可点，没有文本可读，全靠肉眼看。
这一篇是把这个项目从「看截图猜」变成「跑脚本看数字」的全部做法。

## 1. 先给内部状态开一个口子

在模板末尾（IIFE 内、`resize();` 之后）注入一个调试对象，把闭包里的状态暴露出去：

```js
window.__dbg = {
  advance: h => { step(h); elapsed += h; },   // 手动推进物理
  draw:    () => draw(),                       // 手动重绘
  pause:   () => { running = false; },
  reset:   () => { reset(); running = false; },
  sfxOff:  () => { sfxOn = false; },           // 关音效，避免干扰/报错
  kill:    () => { balls[0].cd = 0; balls[0].hp = 1; return triggerHit(0); },
  snap: () => ({
    t: +elapsed.toFixed(3), over: gameOver,
    hp: [balls[0].hp, balls[1].hp],
    stun: [balls[0].stun, balls[1].stun],
    bias: [!!balls[0].aimBias, !!balls[1].aimBias],
    pos: [balls[0].x, balls[0].y, balls[1].x, balls[1].y],
    waves: shockwaves.length, hearts: hearts.length, bullets: bullets.length,
    track: document.getElementById('track').textContent
  })
};
```

注入靠一个**唯一的锚点字符串**，找不到就 `assert` 失败：

```python
anchor = 'resize();\n})();\n</script>'
assert base.count(anchor) == 1, 'anchor count=' + str(base.count(anchor))
```

> 锚点唯一性检查是必须的。改动模板时如果锚点变成 0 个或多处，脚本会立刻报错，
> 而不是悄悄生成一堆没注入探针的页面——那种页面跑出来全是 `NO PROBE`，很难查。

## 2. 虚拟时间下 rAF 不会推进，所以手动步进

这是最大的坑。用 `--virtual-time-budget` 时，`requestAnimationFrame` 基本不按预期推进，
游戏会「停在第 0 帧」，探针永远读到 `elapsed=0`。

解决方案：探针模式下**不依赖 rAF**，直接同步循环：

```js
d.pause();                               // 停掉 rAF 驱动
for (var n = 0; n < 240 * 50; n++) {     // 最多模拟 50 秒
  d.advance(1 / 240);
  var q = d.snap();
  if (q.over) { results.push(q.t); break; }
}
d.draw();                                // 手动画最后一帧，用于截图
```

一个 30 秒的对局 = 7200 次 `step()`，同步跑完只要几十毫秒。
`--virtual-time-budget` 只是给「页面加载 + 解码素材」留时间预算，与模拟时长无关。

## 3. 音频解码会挂起，所以打桩

无头环境里 `decodeAudioData` 常常不 resolve，`await` 就永远等下去，整页卡死。
探针页注入一个桩，让它立刻返回一段静音 Buffer：

```js
var __AC = window.AudioContext || window.webkitAudioContext;
if (__AC) {
  __AC.prototype.decodeAudioData = function (b, ok) {
    var s = this, buf = s.createBuffer(2, Math.floor(s.sampleRate * 8), s.sampleRate);
    if (ok) Promise.resolve().then(function () { ok(buf); });
    return Promise.resolve(buf);
  };
}
```

注意：**只用来验证逻辑，不要用来验证音色**。要确认「音乐真的响了」，只能有头浏览器（见 04）。

## 4. 把结果写进 DOM，用 `--dump-dom` 取

探针跑完后：

```js
var dv = document.createElement('div');
dv.id = 'probe';
dv.textContent = txt;
document.body.appendChild(dv);
```

命令行侧：

```bash
"$EDGE" --headless=new --disable-gpu --no-first-run \
  --user-data-dir="$BASE/edge_p1" \
  --virtual-time-budget=60000 --window-size=940,780 \
  --dump-dom "file:///$BASE/v_over.html" \
| python -c "import sys,re
s=sys.stdin.read()
m=re.search(r'<div id=\"probe\">(.*?)</div>',s,re.S)
print(m.group(1) if m else 'NO PROBE')"
```

`NO PROBE` 基本只有三种原因：锚点没注入、加载前脚本报错、解码卡死。
加一段 `window.onerror` 把错误写进 `document.title` 能省很多时间。

**每次跑都用不同的 `--user-data-dir`**，否则第二个进程会因 profile 锁直接退出。

## 5. 断言什么

不要只断言「跑完了」，要断言**设计意图**：

```js
// 6 局连跑，记录事件时间线
for (var run = 0; run < 6; run++) {
  if (run) d.reset();
  var prev = {w:0,h:0,s0:0,s1:0,b1:false}, ev = [];
  for (var n = 0; n < 240*50; n++) {
    d.advance(1/240); var q = d.snap();
    if (q.waves  > prev.w) ev.push('W'+q.t);              // 冲击波发射
    if (q.hearts > prev.h) ev.push('H'+q.t);              // 爱心炮发射
    if (prev.s1 <= 0 && q.stun[1] > 0) ev.push('S2@'+q.t); // 眩晕触发
    if (!prev.b1 && q.bias[1]) ev.push('B2@'+q.t);         // 打偏标记
    prev = {w:q.waves,h:q.hearts,s0:q.stun[0],s1:q.stun[1],b1:q.bias[1]};
    if (q.over) break;
  }
}
```

产出形如：

```
PROBE over=15.2|16.8|14.1|... 冲击波2次 爱心炮3次
       ev=H2.2,S1@2.479,W4.004,...
```

由此可断言：

- 倒地时间落在设计区间（本项目：15 格血 → 13~17 秒）；
- 每局两个大招都放得出来，且爱心炮都触发了眩晕；
- 眩晕期间位移 = 0、新增吐字 = 0（证明「定住」真的生效）；
- 音乐状态 `A[BGM] → B[END] → C[BGM]` 随开始/倒地/重置正确切换。

一次改动的验证成本 = 一条命令，所以敢频繁改动数值。

## 6. 调参前先跑纯逻辑仿真

`tools/sim_battle.js` 把物理和 AI 抽出来，不依赖浏览器与 Canvas：

```bash
node tools/sim_battle.js 20      # 跑 20 局，输出胜率/平均时长/命中率
```

命中率、倒地时间这类统计量，用仿真跑 20 局比开 20 次浏览器快两个数量级。
仿真只回答「数值合不合理」，画面问题仍然要靠截图。
