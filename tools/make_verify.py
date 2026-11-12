# -*- coding: utf-8 -*-
"""从构建产物生成带内部状态探针的验证页（headless Edge/Chrome 用）。

先跑 tools/build_scene.py 得到 build/duel_4x3.html，再运行本脚本，
会生成 v_wave / v_heart / v_stun / v_over / v_audio 等探针页。
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
T = os.environ.get('DUEL_BUILD', os.path.join(ROOT, 'build'))
os.makedirs(T, exist_ok=True)
HTML = os.environ.get('DUEL_HTML', os.path.join(T, 'duel_4x3.html'))
base = open(HTML, encoding='utf-8').read()

DBG = r'''
window.__dbg={
 advance:function(h){step(h);elapsed+=h;},
 draw:function(){draw();},
 update:function(){update();},
 pause:function(){running=false;},
 reset:function(){reset();running=false;},
 sfxOff:function(){sfxOn=false;},
 kill:function(){balls[0].cd=0;balls[0].hp=1;return triggerHit(0);},
 snap:function(){return {
  t:+elapsed.toFixed(3),over:gameOver,
  hp:[balls[0].hp,balls[1].hp],
  stun:[balls[0].stun,balls[1].stun],
  bias:[!!balls[0].aimBias,!!balls[1].aimBias],
  pos:[balls[0].x,balls[0].y,balls[1].x,balls[1].y],
  fired:[balls[0].fired,balls[1].fired],
  waves:shockwaves.length,hearts:hearts.length,bullets:bullets.length,
  walls:hits[0]+hits[1],
  bgmSrc:!!bgmSrc,endSrc:!!endSrc,fallback:fallback,
  track:document.getElementById('track').textContent,
  info:document.getElementById('skillInfo').textContent
 };}
};
'''

anchor = 'resize();\n})();\n</script>'
assert base.count(anchor) == 1, 'anchor count=' + str(base.count(anchor))
inj = base.replace(anchor, 'resize();\n' + DBG + '})();\n</script>')

STUB = ("var __AC=window.AudioContext||window.webkitAudioContext;"
        "if(__AC){__AC.prototype.decodeAudioData=function(b,ok,err){"
        "var s=this,buf=s.createBuffer(2,Math.floor(s.sampleRate*8),s.sampleRate);"
        "if(ok)Promise.resolve().then(function(){ok(buf);});return Promise.resolve(buf);};}")


def finish(extra=''):
    return ("d.draw();if(d.update)d.update();var q2=d.snap();" + extra +
            "document.title=txt;var dv=document.createElement('div');dv.id='probe';"
            "dv.textContent=txt;document.body.appendChild(dv);")


def page(mode, target=0):
    if mode == 'over':
        body = r'''
 var d=window.__dbg,results=[],logs=[];
 d.pause();d.sfxOff();
 for(var run=0;run<6;run++){
  if(run>0)d.reset();
  var prev={w:0,h:0,s0:0,s1:0,b0:false,b1:false},ev=[],nw=0,nh=0;
  for(var n=0;n<240*50;n++){
   d.advance(1/240);var q=d.snap();
   if(q.waves>prev.w){ev.push('W'+q.t);nw++;}
   if(q.hearts>prev.h){ev.push('H'+q.t);nh++;}
   if(prev.s0<=0&&q.stun[0]>0)ev.push('S1@'+q.t);
   if(prev.s1<=0&&q.stun[1]>0)ev.push('S2@'+q.t);
   if(!prev.b1&&q.bias[1])ev.push('B2@'+q.t);
   prev={w:q.waves,h:q.hearts,s0:q.stun[0],s1:q.stun[1],b0:q.bias[0],b1:q.bias[1]};
   if(q.over){results.push(q.t);logs.push('run'+run+' over='+q.t+' hp='+q.hp.join(':')+
     ' 冲击波'+nw+'次 爱心炮'+nh+'次 bgmSrc='+q.bgmSrc+' endSrc='+q.endSrc+
     ' | '+q.track+' | ev='+ev.slice(0,16).join(','));break;}
  }
  if(results.length<=run)results.push(-1);
 }
 d.draw();if(d.update)d.update();
 var txt='PROBE over='+results.join('|')+' || '+logs.join(' || ');
'''
    elif mode == 'stun':
        body = r'''
 var d=window.__dbg,prev={w:0,h:0,s0:0,s1:0},stopT=-1;
 d.pause();d.sfxOff();
 for(var n=0;n<240*30;n++){
  d.advance(1/240);var q=d.snap();
  if((q.stun[0]>0||q.stun[1]>0)){stopT=q.t;break;}
 }
 var a=d.snap();
 for(var n=0;n<240*0.9;n++)d.advance(1/240);
 var b2=d.snap();
 var dm=Math.hypot(b2.pos[0]-a.pos[0],b2.pos[1]-a.pos[1]);
 var fd=b2.fired[0]-a.fired[0];
 d.draw();if(d.update)d.update();
 var txt='PROBE mode=stun 首次眩晕@'+stopT+'s 时长='+a.stun[0].toFixed(2)+
   's | 眩晕期间情种1位移='+dm.toFixed(1)+'px 新增吐字='+fd+
   ' | 0.9s后剩余眩晕='+b2.stun[0].toFixed(2)+'s hp='+b2.hp.join(':');
'''
    else:
        cond = {
            'wave': 'q.waves>0&&q.t>=__TARGET__',
            'heart': 'q.hearts>0',
            'heartfly': 'q.hearts>0',
        }[mode].replace('__TARGET__', str(target))
        body = r'''
 var d=window.__dbg,prev={w:0,h:0,s0:0,s1:0},ev=[],stopT=-1;
 d.pause();d.sfxOff();
 for(var n=0;n<240*30;n++){
  d.advance(1/240);var q=d.snap();
  if(q.waves>prev.w)ev.push('W'+q.t);
  if(q.hearts>prev.h)ev.push('H'+q.t);
  if(prev.s0<=0&&q.stun[0]>0)ev.push('S1@'+q.t);
  if(prev.s1<=0&&q.stun[1]>0)ev.push('S2@'+q.t);
  prev={w:q.waves,h:q.hearts,s0:q.stun[0],s1:q.stun[1]};
  if(__COND__){stopT=q.t;break;}
 }
 __EXTRA__
 d.draw();if(d.update)d.update();var q2=d.snap();
 var txt='PROBE mode=__MODE__ stop='+stopT+' hp='+q2.hp.join(':')+' waves='+q2.waves+
   ' hearts='+q2.hearts+' stun='+q2.stun.map(function(x){return x.toFixed(2)}).join(':')+
   ' ev='+ev.slice(0,12).join(',')+' || '+q2.info;
'''.replace('__COND__', cond).replace('__MODE__', mode).replace(
    '__EXTRA__',
    ('for(var z=0;z<240*0.30;z++)d.advance(1/240);' if mode == 'wave'
     else 'for(var z=0;z<240*0.20;z++)d.advance(1/240);' if mode == 'heartfly' else ''))

    script = ('<script>' + STUB +
              "window.addEventListener('load',function(){setTimeout(function(){"
              "var b=document.getElementById('btnStart');if(b)b.click();"
              "var d=window.__dbg;if(!d){document.title='ERR no dbg';return;}" +
              body +
              "document.title=txt;var dv=document.createElement('div');dv.id='probe';"
              "dv.textContent=txt;document.body.appendChild(dv);"
              "},250);});</script>")
    return inj.replace('</body>', script + '\n</body>')


AUDIO_JS = r'''<script>
window.addEventListener('load',function(){
 setTimeout(function(){
  document.getElementById('btnStart').click();
  setTimeout(function(){
   var a=document.getElementById('track').textContent;
   window.__dbg.kill();
   setTimeout(function(){
    var b=document.getElementById('track').textContent;
    document.getElementById('btnReset').click();
    setTimeout(function(){
     var c=document.getElementById('track').textContent;
     var f=window.__dbg.snap();
     var txt='PROBE AUDIO A['+a+'] B['+b+'] C['+c+'] fallback='+f.fallback;
     document.title=txt;var dv=document.createElement('div');dv.id='probe';
     dv.textContent=txt;document.body.appendChild(dv);
    },700);
   },900);
  },3600);
 },250);
});
</script>'''

files = {
    'v_wave.html': page('wave', 3.15),
    'v_heart.html': page('heart'),
    'v_heartfly.html': page('heartfly'),
    'v_stun.html': page('stun'),
    'v_over.html': page('over'),
    'v_audio.html': inj.replace('</body>', AUDIO_JS + '\n</body>'),
}
for name, content in files.items():
    p = os.path.join(T, name)
    open(p, 'w', encoding='utf-8').write(content)
    print(name, len(content), 'bytes')
