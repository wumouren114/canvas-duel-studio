# -*- coding: utf-8 -*-
"""从构建产物生成两个自动对局视频页：
- 指定获胜方（WIN=0 情种1 / WIN=1 情种2）
- 页面自动点开始、自动开始 MediaRecorder 录制画布+音乐
- 倒地后继续录 DUEL_LYRIC_SEC 秒（默认 13.4s，对应倒地音乐里目标那句唱完），再停止并上传
- ?test=1 时不录制，手动步进模拟并输出胜负探针（headless 验证用）
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BUILD = os.environ.get('DUEL_BUILD', os.path.join(ROOT, 'build'))
os.makedirs(BUILD, exist_ok=True)
HTML = os.environ.get('DUEL_HTML', os.path.join(BUILD, 'duel_4x3.html'))
PORT = os.environ.get('DUEL_PORT', '8765')
LYRIC = float(os.environ.get('DUEL_LYRIC_SEC', '13.4'))
base = open(HTML, encoding='utf-8').read()

CONTROLLER = r'''
window.__VID={win:__WIN__,name:'__NAME__',lyric:__LYRIC__};
(function(){
 var V=window.__VID,WIN=V.win,LOSE=1-WIN,LY=V.lyric;
 var _th=triggerHit;
 triggerHit=function(i,force){
  // 获胜方血量到 1 后不再掉血，保证指定结局
  if(i===WIN&&balls[i]&&balls[i].hp<=1)return 0;
  return _th(i,force);
 };
 // 关掉失败方的大招开关（自然、可见）
 var skl=document.getElementById(LOSE===0?'skill1':'skill2');
 if(skl&&skl.checked){skl.checked=false;skl.dispatchEvent(new Event('change'));}

 function boost(){
  // 获胜方每 1.2s 额外吐一字（瞄准逻辑同自然开火），加快分出胜负
  var w=balls[WIN];
  if(!gameOver&&w&&!w.down&&w.stun<=0)fire(WIN);
 }

 function report(msg){
  document.title=msg;
  var dv=document.createElement('div');dv.id='probe';dv.textContent=msg;
  document.body.appendChild(dv);
 }

 function hb(msg){
  try{fetch('http://127.0.0.1:__PORT__/save?name=hb_'+encodeURIComponent(V.name)+'_'+encodeURIComponent(msg),{method:'POST',body:msg});}catch(e){}
 }

 function waitBoot(cb){
  var n=0;
  var iv=setInterval(function(){
   if((balls&&balls.length===2)||++n>200){clearInterval(iv);cb();}
  },50);
 }

 function run(){
  hb('start');
  try{startGame();}catch(e){hb('ERR_start_'+e);}
  hb('started_gameStarted='+gameStarted+' running='+running+' audioDest='+(!!audioDest));
  if(location.search.indexOf('test=1')>=0){
   // —— headless 验证：手动步进 ——
   running=false;
   var h=1/240,lastBoost=0,steps=0;
   for(var n=0;n<240*60;n++){
    step(h);elapsed+=h;steps++;
    if(!gameOver&&elapsed-lastBoost>=1.2){lastBoost=elapsed;boost();}
    if(gameOver)break;
   }
   var w=balls[0].down?2:1;
   report('PROBE win=情种'+w+' ko@'+elapsed.toFixed(2)+'s hp='+balls[0].hp+':'+balls[1].hp+
    ' bullets='+bullets.length+' track='+document.getElementById('track').textContent);
   return;
  }
  // —— 真实录制模式（需要有头浏览器，rAF 自然推进） ——
  hb('rec_setup');
  var stream=cv.captureStream(30);
  if(audioDest){var at=audioDest.stream.getAudioTracks()[0];if(at)stream.addTrack(at);}
  var mime=['video/webm;codecs=vp9,opus','video/webm;codecs=vp8,opus','video/webm'].filter(function(m){return MediaRecorder.isTypeSupported(m);})[0];
  var chunks=[],rec=new MediaRecorder(stream,{mimeType:mime});
  hb('mime='+mime+' audioTrack='+(stream.getAudioTracks().length));
  rec.ondataavailable=function(e){if(e.data.size)chunks.push(e.data);};
  rec.onstop=function(){
   var blob=new Blob(chunks,{type:mime});
   fetch('http://127.0.0.1:__PORT__/save?name='+encodeURIComponent(V.name),{method:'POST',body:blob})
    .then(function(){
     report('SAVED '+V.name+' '+(blob.size/1048576).toFixed(2)+'MB');
     fetch('http://127.0.0.1:__PORT__/done?name='+encodeURIComponent(V.name));
     setTimeout(function(){try{window.close();}catch(e){}},2500);
    })
    .catch(function(){
     var url=URL.createObjectURL(blob);var a=document.createElement('a');
     a.href=url;a.download=V.name;document.body.appendChild(a);a.click();
     report('DOWNLOAD '+V.name+' '+(blob.size/1048576).toFixed(2)+'MB');
    });
  };
  rec.start(250);
  hb('rec_started');
  try{window.focus();}catch(e){}
  setInterval(function(){hb('tick_'+(gameOver?'over':'run')+'_'+elapsed.toFixed(1)+'_'+(document.hasFocus()?'F':'-'));},4000);
  var ko=-1,lastBoost=0;
  var iv=setInterval(function(){
   if(!gameOver){
    if(elapsed-lastBoost>=1.2){lastBoost=elapsed;boost();}
   }else{
    if(ko<0){ko=Date.now();hb('ko_elapsed='+elapsed.toFixed(1));}
    if(Date.now()-ko>=(LY+0.1)*1000){
     clearInterval(iv);
     setTimeout(function(){if(rec.state!=='inactive'){hb('rec_stop');rec.stop();}},250);
    }
   }
  },50);
 }
 waitBoot(function(){setTimeout(run,150);});
})();
'''

anchor = 'resize();\n})();\n</script>'
assert base.count(anchor) == 1, 'anchor not found'

for win, name in [(0, 'duel_p1_win.webm'), (1, 'duel_p2_win.webm')]:
    code = (CONTROLLER.replace('__WIN__', str(win))
                    .replace('__NAME__', name)
                    .replace('__LYRIC__', str(LYRIC))
                    .replace('__PORT__', PORT))
    page = base.replace(anchor, 'resize();\n' + code + '})();\n</script>')
    # 录制版把画布 CSS 尺寸放大，提高录制分辨率（420→640）
    page = page.replace('</head>', '<style>.stage{width:640px!important}</style></head>', 1)
    out = os.path.join(BUILD, 'video_%d.html' % (win + 1))
    open(out, 'w', encoding='utf-8').write(page)
    print('built', out, len(page))
