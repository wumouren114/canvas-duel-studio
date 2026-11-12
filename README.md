# canvas-duel-studio

> 一个**自包含单文件**的 Canvas 2D 双人对决小游戏，外加一套「**无头浏览器验证 + 自动录屏出片**」的工程方法。

两个人像在 4:3 场地里不断回弹碰撞，各自循环吐出像素字弹幕；一方打空 15 格血倒地，画面定格、灰屏、头顶下雨。
所有画面、音效、音乐、立绘都内嵌在一个 `.html` 里，双击即可离线运行。

这个仓库的重点不只是游戏，而是**怎么让一个纯前端的动画项目可以被自动验证、自动出片**——
不靠肉眼看，靠脚本跑；不靠手动录屏，靠浏览器自己的 `MediaRecorder`。

```
素材(立绘/音乐) ──build_scene.py──▶ 单文件 HTML(2.9MB, 离线)
                                        │
                  ┌─────────────────────┼─────────────────────┐
                  ▼                     ▼                     ▼
          make_verify.py         make_video.py          直接双击打开
        (无头探针 / 状态断言)   (自动对局 + 录制 WebM)      (给人玩)
                  │                     │
            dump-dom 取结果        vidserver.py 落盘
                                        │
                                  ffmpeg 转 MP4
```

## 特性

**玩法**

- 4:3 场地，红底渐变 + 粉色爱心背景，两人像按圆形碰撞体做完全弹性碰撞与墙面反射（质量按 `r²`）
- 每人循环「一字一字」吐像素字弹幕，带**预判瞄准**（按目标速度提前量 + 随机散射）
- 情种1 **冲击波**：以自身为圆心向外扩散的发光环，扫中把敌人弹飞、扣 1 格、并让敌人下一发打偏 30°
- 情种2 **爱心炮**：8×6 点阵像素爱心，自动追踪走弧线，命中扣 1 格并**眩晕 1 秒**
- 15 格血、受击无敌帧 + 顿帧 + 震屏 + 碎屑、倒地后灰屏阴雨定格
- Web Audio 合成音效（不依赖任何音频文件），双轨音乐切换（BGM → 倒地曲）

**工程**

- `build_scene.py` 把源码模板打成**单文件离线 HTML**，立绘按 alpha 包围盒自动对齐视觉大小
- 纯 Canvas 录制：`captureStream()` + `MediaStreamDestination` 音轨 → `MediaRecorder` → 本地 HTTP 落盘
- `make_verify.py` 注入 `window.__dbg` 探针，在**虚拟时间**下手动步进模拟，输出可断言的文本结果
- `sim_battle.js` 纯逻辑仿真，调参阶段用来批量跑胜率/时长，不依赖浏览器

## 目录结构

```
src/scene_template.html   游戏源码（含 __IMG_FULL_1__ 等占位符，不含真实素材）
tools/build_scene.py      模板 + 素材 → 单文件 HTML + 静态预览图
tools/make_verify.py      生成带探针的验证页（无头浏览器用）
tools/make_video.py       生成自动对局 + 自动录制页
tools/vidserver.py        接收浏览器上传的视频（CORS + .done 标记）
tools/sim_battle.js       物理与节奏的纯逻辑仿真
docs/                     技术文档（建议按顺序读）
assets/                   放你自己的立绘与音乐（不随仓库分发）
```

## 快速开始

**环境**：Python 3.9+ 与 Pillow；Node.js（校验/仿真，可选）；ffmpeg（转码抽帧，可选）；Edge 或 Chrome。

> 下面命令里的 `msedge` 请换成你本机的浏览器可执行文件，例如
> `"/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"` 或 `google-chrome`。

```bash
git clone https://github.com/wumouren114/canvas-duel-studio.git
cd canvas-duel-studio
pip install pillow
```

**1) 准备素材**（详见 `assets/README.md`）

```
assets/p1.png    左边（红队）立绘，透明背景 PNG
assets/p2.png    右边（蓝队）立绘
assets/bgm.mp3   循环 BGM
assets/end.mp3   倒地后播放的曲子
```

素材来源自己定；仓库**不包含**任何人物图与音乐文件。

**2) 构建**

```bash
python tools/build_scene.py
# → build/duel_4x3.html   （自包含，双击即可玩）
# → build/preview.png     （静态预览图）
```

素材不在默认位置时用环境变量指定：

```bash
DUEL_ASSETS=/path/to/assets \
DUEL_BGM=/path/to/bgm.mp3 DUEL_END=/path/to/end.mp3 \
python tools/build_scene.py
```

**3) 无头验证**（改完代码先跑这个，别靠肉眼）

```bash
python tools/make_verify.py
# 生成 build/v_over.html 等页面，下面用浏览器跑其中一个
msedge --headless=new --disable-gpu --virtual-time-budget=60000 \
  --dump-dom "file://$PWD/build/v_over.html" | grep -o 'PROBE[^<]*'
# → PROBE over=15.2|16.8|... 冲击波2次 爱心炮3次 ...
```

**4) 自动录屏出片**

```bash
python tools/vidserver.py out 8765        # 终端 A：先起接收端
python tools/make_video.py                # 生成 build/video_1.html、video_2.html
# 终端 B：必须有头浏览器（音频解码在无头下会挂起），--kiosk 保证窗口拿到焦点
msedge --kiosk --autoplay-policy=no-user-gesture-required \
  --user-data-dir=/tmp/rec "file://$PWD/build/video_1.html"
# 约 30 秒后 out/duel_p1_win.webm 出现（含音频轨）
ffmpeg -i out/duel_p1_win.webm -c:v libx264 -crf 20 -pix_fmt yuv420p \
  -c:a aac -b:a 160k out/duel_p1_win.mp4
```

## 关键实现速查

| 主题 | 做法 | 文档 |
|---|---|---|
| 单文件打包 | 构建期把 PNG→WebP/MP3→base64 填进占位符 | [01](docs/01-architecture.md) |
| 手感稳定 | 固定步长 `h=1/240`，与渲染帧率解耦 | [01](docs/01-architecture.md) |
| 立绘大小对齐 | 按 alpha>60 求主体包围盒，只缩放视觉不缩放碰撞圆 | [01](docs/01-architecture.md) |
| 像素字弹幕 | 20×20 离屏画布 + `imageSmoothingEnabled=false` | [02](docs/02-skill-fx.md) |
| 追踪弹 | 转向角速度限制 + 0.28s「起飞窗口」不判定命中 | [02](docs/02-skill-fx.md) |
| 自动验证 | 注入 `__dbg`，虚拟时间下手动 `step()` | [03](docs/03-headless-verification.md) |
| 自动录屏 | `captureStream` + 音频 `MediaStreamDestination` | [04](docs/04-video-recording.md) |
| 踩过的坑 | 焦点、dpr、ffmpeg 写盘、奇数高度…… | [05](docs/05-pitfalls.md) |

## 素材与版权

- 仓库内**不含**任何人物立绘与音乐文件（`assets/` 里只有说明）。请使用你有权使用的素材。
- 代码以 MIT 协议开源；你自行放入 `assets/` 的素材版权归原作者，不在本协议范围内。
- 演示中曾使用的两首流行歌曲仅作本地测试，未随仓库分发。

## License

MIT © 2026 wumouren114
