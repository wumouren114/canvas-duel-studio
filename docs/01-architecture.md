# 01 · 架构：单文件、固定步长、视觉与碰撞分离

## 1. 为什么是「一个 HTML」

目标产物是**可以随手发给别人、双击就能玩**的素材，所以不能有外链资源：

- 立绘 → `WEBP`（质量 90，失败回落 PNG）→ base64 → `data:` URI
- 音乐 → MP3 原始字节 → base64 → `data:audio/mpeg;base64,...`
- 音效 → 不用文件，运行时用 `OscillatorNode` / 噪声 Buffer 合成

模板里预留占位符，构建期替换：

```html
<!-- src/scene_template.html -->
<img id="art1" src="__IMG_FULL_1__">
const RECT1=[__RECT1__], RECT2=[__RECT2__];
const BGM='__BGM_B64__', END='__END_B64__';
```

`tools/build_scene.py` 做替换，并对每个占位符 `assert key in html`——
**占位符拼错会立刻炸，而不是产出一个静默坏掉的页面**。

```python
for key, im in assets.items():
    assert key in html, 'missing placeholder: ' + key
    uri, size = data_uri(im)
    html = html.replace(key, uri)
```

代价是体积：2 张立绘 + 2 首曲子 = 约 2.9 MB。换来的是零依赖、可离线、可以直接当素材发人。

## 2. 固定步长，而不是 `dt`

```js
const h = 1 / 240;          // 物理步长固定 240Hz
function loop(now){
  acc += Math.min((now - last) / 1000, 0.1);   // 单帧最多补 0.1s，防止切后台回来炸
  while (acc >= h) { step(h); acc -= h; }
  draw();
  requestAnimationFrame(loop);
}
```

好处：

- 弹幕速度、碰撞结果**与刷新率无关**，60Hz / 120Hz / 掉帧都一致；
- 探针脚本可以脱离 `requestAnimationFrame` 直接 `step(h)` 上万次（见 03）；
- 调参时可复现——同样的种子 + 同样的步数 = 同样的结局。

## 3. 物理：圆形碰撞 + 墙面反射

角色用**不可见的圆**做碰撞体，视觉上贴完整立绘（不是圆头像）：

```js
// 完全弹性碰撞，按面积（r²）分配质量
const m1 = b1.r*b1.r, m2 = b2.r*b2.r, M = m1 + m2;
// 沿法线交换动量分量，切向不变
```

墙面反射只翻转速分量并夹回场内，避免速度衰减导致的「贴墙抖动」。

所有尺寸都从场地短边派生，换分辨率不用改数值：

```js
const r = Math.min(W, H) * 0.09;      // 角色半径
const sc = () => W / 360;             // 线宽/字号等比缩放
```

## 4. 视觉大小 ≠ 碰撞大小

两张立绘的原始画布差很多（1080×1438 与 751×564），直接按图片框缩放会让一个人大一圈。
做法是**只对齐主体**：

```python
def subject_rect(path):
    im = Image.open(path).convert('RGBA')
    w, h = im.size
    bb = im.getchannel('A').point(lambda p: 255 if p > 60 else 0).getbbox()
    return [bb[0]/w, bb[1]/h, (bb[2]-bb[0])/w, (bb[3]-bb[1])/h]
```

把归一化主体矩形写进 `RECT1/RECT2`，渲染时按主体高度反推绘制尺寸：

```js
// 让主体高度一致，而不是图片高度一致
const drawH = targetH / RECT[i][3];
```

碰撞圆仍然是统一的 `r`。这样「看起来差不多大」和「打起来公平」互不干扰。
本项目实测两人物视觉差从 45% 收到 4% 以内。

## 5. 渲染细节

- **高 DPI**：`canvas.width = cssW * dpr`，`ctx.scale(dpr, dpr)`，dpr 上限 2（再高只烧 GPU）。
- **像素字**：单独 20×20 离屏画布写字，`imageSmoothingEnabled = false` 放大，
  字号取 `15px SimSun` + 细描边，避免小字号汉字糊成黑块（见 02）。
- **血条**：分段矩形而不是连续条，扣血时飞出血格碎片；宽度取
  `max(2r, min(W,H)*0.22)`——人物缩小后仍保证 15 格数得清。

## 6. 状态机

```
idle ──开始──▶ running ⇄ paused
                 │
                 ├─ 眩晕(stun>0)：定住、不出招、CD 顺延
                 └─ hp<=0 ──▶ over：定住画面、清弹幕、灰屏、下雨、切歌
                                  └─重置──▶ idle
```

`over` 之后**停止推进**而不是继续跑：`running=false` + `gameOver=true`，
渲染循环仍在跑（要画雨和抖动），但 `step()` 不再更新实体。
