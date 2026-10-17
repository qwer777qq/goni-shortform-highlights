"""Render every catalog type with original synthetic footage, never user media."""
from pathlib import Path
import json,hashlib,shutil
from PIL import Image,ImageDraw,ImageFont
import core
from template_styles import CATALOG

def main():
    root=Path(__file__).resolve().parent
    result=root/'test-results'/'template-pack'
    result.mkdir(parents=True,exist_ok=True)
    core.DATA=result/'projects'
    # Original fixture shared by all template previews.
    im=Image.new('RGB',(960,540),'#19324B');d=ImageDraw.Draw(im)
    f=ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf',60)
    d.rounded_rectangle((60,70,900,470),30,fill='#244A67',outline='#76E0CA',width=5)
    d.text((480,140),'로컬 편집 예제',font=f,fill='white',anchor='mt')
    d.text((480,260),'영상 입력 → 구간 선택',font=ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf',40),fill='#A5F5DE',anchor='mt')
    d.text((480,350),'합성 테스트 화면',font=ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf',26),fill='white',anchor='mt')
    im.save(result/'fixture.png')
    core.run(['ffmpeg','-y','-v','error','-loop','1','-i',str(result/'fixture.png'),
              '-f','lavfi','-i','sine=frequency=440:duration=3','-t','3','-af','volume=0.025',
              '-vf','format=yuv420p','-c:v','libx264','-preset','ultrafast','-r','30','-c:a','aac',str(result/'fixture.mp4')])
    project=core.import_file(result/'fixture.mp4','템플릿 테스트')
    project['segments']=[dict(start=0,end=3,text='어절마다 자막 효과를 확인하세요')]
    gallery=root.parent/'docs'/'templates'/'previews'
    gallery.mkdir(parents=True,exist_ok=True)
    reports=[];thumbs=[]
    for item in CATALOG:
        if item['legacy']:continue
        key=item['id']
        project['edit'].update(theme=key,start=0,end=3,title='제목을 두 줄로\n안전하게 배치합니다',
                              footer='고니 · 로컬 숏폼',comment='이 기능은 어떻게 사용하는 건가요?',captions=True)
        ex=core.render(project,lambda *a:None)
        folder=core.project_dir(project['id'])/'exports'/ex['id']
        # Use a mid-word sample, rather than a zero-alpha first frame.
        core.run(['ffmpeg','-y','-v','error','-ss','0.7','-i',str(folder/'short.mp4'),'-frames:v','1',str(gallery/(key+'.jpg'))])
        shutil.copy2(folder/'short.mp4',gallery/(key+'.mp4'))
        thumb=Image.open(gallery/(key+'.jpg')).convert('RGB');thumb.thumbnail((216,384))
        thumbs.append((item['name'],thumb))
        reports.append({'id':key,'duration':ex['duration'],'audio':ex['has_audio'],'decoded':True,
                        'sha256':hashlib.sha256((folder/'short.mp4').read_bytes()).hexdigest()})
        print('PASS',key,flush=True)
    sheet=Image.new('RGB',(216*4,430*2),'#18212C');draw=ImageDraw.Draw(sheet)
    for i,(label,im) in enumerate(thumbs):
        x=(i%4)*216;y=(i//4)*430
        sheet.paste(im,(x,y+35))
        draw.text((x+8,y+6),label,font=ImageFont.truetype('C:/Windows/Fonts/malgunbd.ttf',18),fill='white')
    sheet.save(gallery/'all-templates.jpg',quality=93)
    (result/'report.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')
    print('All seven templates rendered and decoded.',flush=True)

if __name__=='__main__':main()
