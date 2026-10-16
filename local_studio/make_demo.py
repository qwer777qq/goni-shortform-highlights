"""Generate original synthetic footage; no downloaded media needed."""
from pathlib import Path
from core import ROOT, run

def main():
    run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i',
         'testsrc2=size=960x540:rate=30:duration=12', '-f', 'lavfi', '-i',
         'sine=frequency=440:sample_rate=48000:duration=12', '-af', 'volume=0.05',
         '-c:v', 'libx264', '-preset', 'fast', '-crf', '23', '-pix_fmt', 'yuv420p',
         '-c:a', 'aac', '-movflags', '+faststart', str(ROOT / 'demo.mp4')])
    (ROOT / 'demo.srt').write_text('''1
00:00:00,000 --> 00:00:03,000
테스트 영상입니다

2
00:00:03,000 --> 00:00:06,000
원하는 구간을 직접 고르세요

3
00:00:06,000 --> 00:00:09,000
자막과 제목을 바꾸는 방법

4
00:00:09,000 --> 00:00:12,000
완성된 결과를 저장하세요
''', encoding='utf-8')
    print('Demo created:', ROOT / 'demo.mp4')

if __name__ == '__main__':
    main()
