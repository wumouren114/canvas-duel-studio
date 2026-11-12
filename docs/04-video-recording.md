# 04 · 自动录屏：让 canvas 自己把画面和声音录下来

目标：**脚本点一下，就得到一段「开局 → 对局 → 倒地 → 音乐唱到指定歌词」的成片**，
不装录屏软件、不手动剪、不错过关键帧。

## 1. 一句话原理

```js
const stream = cv.captureStream(30);                    // 画布画面，30fps
const at = audioDest.stream.getAudioTracks()[0];        // 音乐/音效的音轨
if (at) stream.addTrack(at);
const rec = new MediaRecorder(stream, { mimeType: 'video/webm;codecs=vp9,opus' });
```

关键是 `audioDest`：Web Audio 里所有音乐和音效都先汇到一个 `musicMaster` / `sfxMaster`，
再**同时**连到 `ctx.destination`（给人听）和 `ctx.createMediaStreamDestination()`（给录制用）。
这样录到的声音和玩家听到的完全一致，不需要额外混音。

```js
function outNode(master){
  master.connect(audioCtx.destination);
  audioDest = audioCtx.createMediaStreamDestination();
  master.connect(audioDest);
  return master;
}
```

## 2. 落盘：别指望「下载」，用 HTTP 上传

`a.download` 在无头环境里存到哪不确定。改成本地小服务器接收，确定、可轮询：

```js
rec.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
rec.onstop = () => {
  const blob = new Blob(chunks, { type: mime });
  fetch(`http://127.0.0.1:8765/save?name=${encodeURIComponent(name)}`, {
    method: 'POST', body: blob
  }).then(() => fetch(`http://127.0.0.1:8765/done?name=${encodeURIComponent(name)}`));
};
```

`tools/vidserver.py` 只有 50 行：收 `POST`、写文件、写一个 `.done` 标记、放开 CORS。
显式 `OPTIONS` 预检也要回，否则跨域 `file://` 页面发不出请求。

**再加一路心跳**：每 4 秒 POST 一个几字节的文本文件（`hb_*.done`）。
出问题时看目录里最后的心跳就知道卡在哪一步：`rec_started` → `tick_run_7.3` → `ko_elapsed` → `rec_stop`。

```js
setInterval(() => hb(`tick_${gameOver?'over':'run'}_${elapsed.toFixed(1)}_${document.hasFocus()?'F':'-'}`), 4000);
```

最后那个 `F/-` 是本篇最重要的调试信息，见下一节。

## 3. 三个必须踩过的坑

### ① 必须用「有头」浏览器

无头环境下 `decodeAudioData` 不 resolve（见 03 的打桩），程序会走 `Blob` 兜底播放——
音乐能响，但**音轨录不进去**，出来是默片。
所以录制必须用真正有窗口的浏览器，让音频正常解码。

### ② 窗口拿不到焦点，rAF 会被冻结

用 `--new-window` 启动但窗口被其他窗口盖住时，`document.hasFocus()` 为 `false`，
Chrome/Edge 会把 `requestAnimationFrame` 降到极低频率甚至暂停：
游戏卡在 7.3 秒不动，录出来是一个定格画面。

解法是 **kiosk 模式**（全屏、置顶、强制获得焦点）：

```bash
msedge --kiosk \
  --autoplay-policy=no-user-gesture-required \
  --disable-backgrounding-occluded-windows \
  --disable-features=CalculateNativeWinOcclusion \
  --user-data-dir=/tmp/rec \
  --window-size=1240,940 \
  "file:///path/to/build/video_1.html"
```

`--autoplay-policy=no-user-gesture-required` 让音乐无需交互就能自动播，
后面两个 flag 防止窗口被判定为「被遮挡」而降频。

> 顺便说：这也是为什么「自动录制」需要一次全屏弹出。这是浏览器安全模型的必然，
> 不是脚本没写好。

### ③ 录制分辨率被 CSS 卡住

画布的 `backing store` 是 `cssW × dpr`。模板里画布宽 420px、dpr 上限 2，
直接录只有 630×473——发出去偏糊。

两种加法：

| 方案 | 结果 | 结论 |
|---|---|---|
| `--force-device-scale-factor=2` | 更清晰，但掉到 ~17fps | ❌ 掉帧明显 |
| 注入 `.stage{width:640px!important}` | 960×720 / 30fps | ✅ 采用 |

第二种更好，因为它是「把画布本身做大」，dpr 仍是 1.5，渲染负担增长温和：

```python
page = page.replace('</head>', '<style>.stage{width:640px!important}</style></head>', 1)
```

## 4. 让结局可控

随机对局录不出「指定一方获胜」。用三重控制，且都不改动画表现：

```js
// ① 关掉失败方的大招开关（界面上真实可见）
document.getElementById(LOSE===0?'skill1':'skill2').checked = false;

// ② 获胜方每 1.2 秒补吐一字，加快分出胜负
setInterval(() => { if (!gameOver) fire(WIN); }, 1200);

// ③ 获胜方血量到 1 就不再掉血，保证不倒
const _th = triggerHit;
triggerHit = function (i, force) {
  if (i === WIN && balls[i] && balls[i].hp <= 1) return 0;
  return _th(i, force);
};
```

录制前先跑一次 `?test=1`（手动步进版）确认胜负方向正确，再开录——
验一次只要 1 秒，录错一次要 30 秒。

## 5. 什么时候停

「唱到某句歌词」不能靠估。做法：

1. 把倒地音乐丢给 ASR（本项目用 `AudioTranscribe`）拿到带时间戳的歌词；
2. 找到目标句的结束时间（例如某句歌词在 13.4s 唱完）；
3. 代码里 `LY` 就是这个秒数，倒地后再录 `LY` 秒才 `rec.stop()`。

```js
if (Date.now() - ko >= (LY + 0.1) * 1000) {
  clearInterval(iv);
  setTimeout(() => rec.state !== 'inactive' && rec.stop(), 250);
}
```

`+0.1` 和 `250ms` 是留白：留白太多会拖尾，太少会把最后一个字切掉。

## 6. 转码

浏览器只给 WebM（VP9/Opus）。要发微信/进剪辑软件就转 MP4：

```bash
ffmpeg -i in.webm -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p \
       -c:a aac -b:a 160k -movflags +faststart out.mp4
```

两个细节：

- **高度必须是偶数**，`473` 会让 libx264 直接报错，需要 `-vf scale=630:472`；
- 中文文件名在某些 shell 下 ffmpeg 写不出文件，用管道更稳：
  `ffmpeg ... -f mp4 pipe:1 > out.mp4`（抽帧同理 `-f image2 -c:v png pipe:1 > f.png`）。

## 7. 校验，而不是「看起来像」

```bash
# 时长/分辨率/编码
ffprobe -v error -show_entries format=duration:stream=codec_type,codec_name,width,height \
  -of default=noprint_wrappers=1 out/duel_p1_win.mp4

# WebM 的 duration 常是 N/A，用帧数 ÷ 帧率
ffprobe -v error -count_packets -select_streams v:0 \
  -show_entries stream=nb_read_packets,r_frame_rate -of default=noprint_wrappers=1 in.webm

# 确认不是默片
ffmpeg -i in.webm -af volumedetect -f null - 2>&1 | grep -E 'n_samples|mean_volume'
```

再抽关键帧拼图人眼过一遍（对局中段 / 倒地瞬间 / 结尾），确认：
谁倒地、灰屏有没有生效、雨是不是在倒地者上方、结尾那句歌词是否唱完。
