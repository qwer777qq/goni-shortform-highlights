"""Exercise real HTTP and FFmpeg paths, keeping evidence in test-results."""
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import core
from make_demo import main as make_demo

ROOT=core.ROOT
RESULTS=ROOT/'test-results'

def main():
    RESULTS.mkdir(exist_ok=True)
    if not (ROOT/'demo.mp4').exists(): make_demo()
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
    base=f'http://127.0.0.1:{port}'
    log=(RESULTS/'server.log').open('w',encoding='utf-8')
    proc=subprocess.Popen([sys.executable,str(ROOT/'server.py'),'--port',str(port),
                           '--data-dir',str(RESULTS/'projects')],stdout=log,stderr=log,
                          creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    def req(path,body=None,headers=None,raw=None):
        h={} if headers is None else headers.copy()
        if body is not None:
            raw=json.dumps(body).encode();h.update({'Content-Type':'application/json','X-Studio-Request':'1'})
        with urlopen(Request(base+path,data=raw,headers=h),timeout=30) as r:
            return r.status,r.read(),dict(r.headers)
    def api(path,body=None): return json.loads(req(path,body)[1])
    def wait(job):
        deadline=time.monotonic()+180
        while job['status'] in ('queued','running') and time.monotonic()<deadline:
            time.sleep(.25);job=api('/api/jobs/'+job['id'])
        assert job['status']=='done',job
        return job['result']
    def denied(path,headers,raw=None,code=403):
        try: req(path,headers=headers,raw=raw)
        except HTTPError as e: assert e.code==code,(e.code,code)
        else: raise AssertionError('Unsafe request accepted')
    try:
        for _ in range(100):
            try: api('/api/config');break
            except OSError: time.sleep(.1)
        else: raise AssertionError('Server did not start')
        assert b'canvas' in req('/')[1]
        denied('/api/demo',{},b'{}')
        denied('/api/demo',{'Origin':'https://example.org','X-Studio-Request':'1'},b'{}')
        denied('/api/config',{'Host':'evil.example'})
        source=(ROOT/'demo.mp4').read_bytes(); before=hashlib.sha256(source).hexdigest()
        job=json.loads(req('/api/upload?name=demo.mp4',raw=source,headers={'X-Studio-Request':'1'})[1])
        p=wait(job)['project']; pid=p['id']
        p=api('/api/srt',{'id':pid,'text':(ROOT/'demo.srt').read_text(encoding='utf-8')})
        p['edit'].update(start=2,end=8,speed=1.2,title='로컬 편집 테스트',footer='원본 보존 · 출력 검증',theme='paper')
        p=api('/api/save',{'id':pid,'edit':p['edit'],'segments':p['segments']})
        assert api('/api/projects/'+pid)['edit']['start']==2
        assert api('/api/recommend',{'id':pid,'target':8})['candidates']
        result=wait(api('/api/render',{'id':pid})); ex=result['export']
        folder=RESULTS/'projects'/pid/'exports'/ex['id']; out=folder/'short.mp4'
        info=core.probe(out)
        assert (info['width'],info['height'],info['codec'],info['has_audio'])==(1080,1920,'h264',True)
        assert abs(info['duration']-5)<.2,info
        core.run(['ffmpeg','-v','error','-xerror','-i',str(out),'-f','null','-'])
        captions=core.parse_srt((folder/'captions.srt').read_text(encoding='utf-8-sig'))
        assert captions[0]['start']==0 and abs(captions[-1]['end']-5)<.01
        media=f'/media/{pid}/exports/{ex["id"]}/short.mp4'
        status,part,headers=req(media,headers={'Range':'bytes=0-99'})
        assert status==206 and len(part)==100 and 'Content-Range' in headers
        denied(media,{'Range':'bytes=999999999-'},code=416)
        status,full,headers=req(media+'?download=1')
        assert hashlib.sha256(full).digest()==hashlib.sha256(out.read_bytes()).digest()
        assert 'attachment' in headers['Content-Disposition']
        denied(f'/media/{pid}/../../server.py',{},code=403)
        assert before==hashlib.sha256((ROOT/'demo.mp4').read_bytes()).hexdigest()
        # No-audio source, slow playback, crop, no captions, different template.
        silent=RESULTS/'silent.mp4'
        core.run(['ffmpeg','-y','-v','error','-i',str(ROOT/'demo.mp4'),'-t','2','-an','-c:v','copy',str(silent)])
        p2=wait(api('/api/import',{'path':str(silent)}))['project']
        p2['edit'].update(start=.25,end=1.25,speed=.5,layout='crop',theme='navy',captions=False)
        api('/api/save',{'id':p2['id'],'edit':p2['edit']})
        r2=wait(api('/api/render',{'id':p2['id']}))
        assert not r2['export']['has_audio'] and abs(r2['export']['duration']-2)<.2
        report={'status':'passed','checks':['HTTP upload/import/save/reopen/SRT/recommend/render/download',
                   'audio and silent render','speed 1.2 and 0.5 / fit and crop / paper and navy',
                   '1080x1920 H264 AAC / full decode / expected duration / clipped SRT',
                   'Range 206/416 / cross-origin and missing-header 403 / traversal 403 / source preserved'],
                'project':pid,'output':str(out),'thumbnail':str(folder/'thumbnail.jpg'),'source_sha256':before}
        (RESULTS/'smoke-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False,indent=2))
    finally:
        proc.terminate()
        try:proc.wait(timeout=10)
        except subprocess.TimeoutExpired:proc.kill();proc.wait()
        log.close()

if __name__=='__main__':main()
