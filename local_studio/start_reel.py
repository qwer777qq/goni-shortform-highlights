"""Launch this local studio in a hidden subprocess, then open the reel editor."""
import argparse
from pathlib import Path
import json
import subprocess
import sys
import time
from urllib.request import urlopen
import webbrowser


def main():
    p=argparse.ArgumentParser(); p.add_argument('--port',type=int,default=8769); args=p.parse_args()
    root=Path(__file__).resolve().parent
    url=f'http://127.0.0.1:{args.port}'
    def ready():
        try:
            with urlopen(url+'/api/config',timeout=1) as r:
                config=json.load(r)
            # Avoid silently opening a different installation on an occupied port.
            if Path(config.get('data_dir','')).resolve() != (root/'data').resolve():
                raise RuntimeError('다른 스튜디오가 이 포트를 사용합니다. 다른 --port를 선택하세요.')
            return True
        except (OSError, ValueError): return False
    if not ready():
        log=(root/'reel-server.log').open('a',encoding='utf-8')
        proc=subprocess.Popen([sys.executable,str(root/'server.py'),'--port',str(args.port)],cwd=root,
                              stdin=subprocess.DEVNULL,stdout=log,stderr=log,
                              creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        log.close()
        for _ in range(40):
            if ready(): break
            if proc.poll() is not None: raise SystemExit('서버 시작 실패: reel-server.log를 확인하세요.')
            time.sleep(.25)
        else: raise SystemExit('서버 시작 시간 초과: reel-server.log를 확인하세요.')
    webbrowser.open(url+'/reel')
    print(url+'/reel')


if __name__=='__main__': main()
