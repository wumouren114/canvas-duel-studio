# 02 · 技能与特效：参数、算法与取舍

所有常量集中在模板第 97~104 行，改手感只需要动这几个数。

```js
const SPAWN_GAP=0.55, GLYPH=20, FLASH_TIME=0.38, HIT_CD=0.55;     // 无敌帧 0.55s
const MAX_HP=15, AIM_LEAD=0.6, AIM_SPREAD=8*Math.PI/180;
const HIT_STOP=0.06, SHAKE_TIME=0.22, CHARGE_TIME=0.12;
const SHOCK_CD=6.0, HEART_CD=5.0, STUN_TIME=1.0, AIM_BIAS=30*Math.PI/180;
const SHOCK_RANGE=0.58, SHOCK_SPEED=0.64;
const HEART_TURN=4.2, HEART_SPEED=190, HEART_DELAY=0.28;
```

## 1. 一字一字弹幕

每个人挂一句台词，`SPAWN_GAP` 秒吐一个字，吐完回到第一个字循环。

**「尽量朝向敌人」不能只朝当前位置**——目标在飞，直着打几乎打不中。做法是解析预判：

```js
function fire(i){
  const b = balls[i], f = balls[1-i];
  const flight = Math.hypot(f.x-b.x, f.y-b.y) / BULLET_SPEED;
  // 按目标当前速度外推，再乘一个 0.6 的折扣（预判过强会显得「开挂」）
  const tx = f.x + f.vx * flight * AIM_LEAD;
  const ty = f.y + f.vy * flight * AIM_LEAD;
  let ang = Math.atan2(ty-b.y, tx-b.x);
  ang += (Math.random()*2-1) * AIM_SPREAD;   // ±8° 散射，避免每发都必中
  if (b.aimBias) ang += b.aimBias;           // 被冲击波打偏时叠加
  ...
}
```

**为什么无敌帧是 0.55s 而不是命中冷却 0.55s**：早期版本用「每 0.55s 才能再中一次」，
结果 7 格血在 2.9 秒内掉完，一句台词都吐不完。改成**受击后 0.55s 无敌**后，
命中率约 43%，10 格血约 9.4 秒、15 格血约 13~16 秒，节奏才立得住。

## 2. 像素字渲染

汉字缩到 12~16px 直接画会糊成一团黑。三层处理：

1. **超采样**：在 20×20 的离屏画布上用 `15px SimSun` 画一次，开 1px 描边；
2. **关插值**：`ctx.imageSmoothingEnabled = false` 再放大到屏幕上的 `GLYPH` 像素；
3. **加拖影**：沿速度方向取 3 个历史位置，透明度 `1/t` 递减，做出「射出去」的运动感。

```js
const c = document.createElement('canvas'); c.width = 20; c.height = 20;
const g = c.getContext('2d');
g.font = '15px SimSun'; g.textAlign = 'center'; g.textBaseline = 'middle';
g.lineWidth = 1; g.strokeStyle = '#1f2328'; g.fillStyle = color;
g.strokeText(ch, 10, 10); g.fillText(ch, 10, 10);
glyphCache[ch+color] = c;                       // 每个字只画一次，之后纯 blit
```

缓存很关键：一句话 10 个字 × 2 人 × 每秒 2 发，不缓存的话每帧都在建画布。

## 3. 冲击波（情种1）

**扩散环**用「半径随时间的圆」而不是粒子，判定和绘制共用同一个半径：

```js
s.r += SHOCK_SPEED * Math.min(W,H) * h;         // 扩散
if (s.r > SHOCK_RANGE * Math.min(W,H)) remove;  // 到范围上限消失

// 只对敌方判定一次，且要求目标圆与环带相交
if (!s.hit && Math.abs(dist - s.r) < f.r + 6 && dist < SHOCK_RANGE*Math.min(W,H)) {
  s.hit = true;
  triggerHit(1-s.owner);                        // 1 格伤害
  knockback(f, s);                              // 径向弹飞
  balls[1-s.owner].aimBias = ±AIM_BIAS;         // 下一发打偏 30°
  balls[1-s.owner].biasLeft = BIAS_TIME;
}
```

几个刻意选择：

- **弹飞不给额外伤害**（撞墙只给火花 + 震屏 + 顿帧）。多给一格会让「冲击波 + 撞墙」变成必杀连段，太强。
- 打偏只作用于**下一发**，`BIAS_TIME` 0.3s 内有效，避免长时间残废。
- 环的**视觉**比判定宽一点（绘制多画一圈发光），但判定按 `r`，玩家感知是「擦到就飞」，实际是「碰到才飞」。

扩散时长 = `SHOCK_RANGE / SHOCK_SPEED` ≈ 0.91 秒，慢到能看清推进，快到来得及反应。
早期版本 0.55 速 + 0.42 范围，0.76 秒一闪而过，几乎看不到环——**扩散速度和范围要一起调**。

## 4. 爱心炮（情种2）

8×6 点阵心形，自动追踪：

```js
const HEART_PIX = ['01100110','11111111','11111111',
                   '01111110','00111100','00011000'];
```

**追踪用限制转向角速度，不要直接朝目标飞**——直接朝目标飞是一条直线，看不出「追踪」：

```js
const want = Math.atan2(t.y-p.y, t.x-p.x);
let d = ((want - p.ang + Math.PI*3) % (Math.PI*2)) - Math.PI;
p.ang += Math.max(-HEART_TURN*h, Math.min(HEART_TURN*h, d));
```

**起飞窗口**（`HEART_DELAY=0.28`）：前 0.28 秒只飞不判定命中。
原因很实际——两人距离近时，弹速 190 下 0.14 秒就命中，追踪弧线根本来不及画出来，
玩家只看到「一闪，血少一格」。加了窗口后能稳定看到一段弧线再命中，代价是命中略延迟。

命中：1 格血 + `stun = 1.0`。眩晕期间：

- 速度归零、不出招、CD 暂停（`cd` 不减），
- 头顶画三颗黄色像素星，绕圈旋转，
- `triggerHit` 里对 `stun>0` 的目标跳过再次判定。

**像素爱心的清晰度**踩过坑：`shadowBlur` 一开始给到 16px，直接把 8×6 的点阵糊成一个方块。
最终方案是**每格先画一圈深色轮廓（`#6d0f24`）再填粉色**，发光收到 6px 以内，心形轮廓才立得住。

## 5. 受击特效

一次命中同时触发 5 件事，全部在一个函数里，避免状态散落：

| 效果 | 实现 | 时长 |
|---|---|---|
| 闪白 | `globalCompositeOperation='lighter'` 叠一层白 | 0.38s |
| 顿帧 | 全局 `hitStop` 计时，期间 `step` 传入 0 | 0.06s |
| 震屏 | `ctx.translate(random*shake)` | 0.22s |
| 碎屑 | 12 个粒子，初速随机、重力下坠 | 0.6s |
| 血格碎片 | 从血条被扣的那一格飞出 | 0.7s |

## 6. 倒地

`hp<=0` 时：`gameOver=true; running=false`，清空弹幕/冲击波/爱心弹，
倒地方旋转 90°、透明度和灰化一起过渡，`grayMode` 打开全屏去色，
在**倒地者正上方**生成雨（不是全屏雨），音乐淡出切到倒地曲。

雨只在局部：`x` 限定在倒地者 ± 场地 35% 范围内，`y` 从顶部落下到地面消失。
全屏雨会很吵，也会把「谁倒了」这个信息冲掉。

## 7. 音效不落地文件

```js
// 冲击波：低频正弦下扫 + 噪声爆
const o = ctx.createOscillator(); o.type='sine';
o.frequency.setValueAtTime(180, t);
o.frequency.exponentialRampToValueAtTime(40, t+0.35);
```

5 种音效（吐字、命中、冲击波、爱心炮、撞墙）全部合成，
一个 `noiseBuf` 复用给所有噪声类音效。好处是体积为 0，坏处是不好「设计音色」——
但这类街机感的小游戏，合成音反而比采样更贴。
