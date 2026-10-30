"""Independent local video cleanup. Third-party service code is not used."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import urlsplit


def run(args):
    subprocess.run(args, check=True)


def clean_video(source, output_dir, region=None, audio='keep', auto_text=False):
    """Process a file or public URL into a new directory. Region is x,y,width,height."""
    if audio not in ('keep', 'mute', 'remove_voice', 'voice_only'):
        raise ValueError('오디오 모드를 확인하세요.')
    if region is not None and auto_text:
        raise ValueError('자동 자막 지우기와 수동 영역은 함께 지정할 수 없습니다.')
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        raise RuntimeError('FFmpeg와 ffprobe가 필요합니다.')
    out = Path(output_dir).expanduser().resolve()
    if out.exists():
        raise ValueError('기존 폴더는 덮어쓰지 않습니다. 새로운 출력 폴더를 지정하세요.')
    url = urlsplit(source)
    is_url = url.scheme.lower() in ('http', 'https')
    if is_url and (not url.hostname or url.username or url.password):
        raise ValueError('로그인 정보가 없는 영상 URL을 입력하세요.')
    if not is_url:
        source = str(Path(source).expanduser().resolve(strict=True))
        if not Path(source).is_file():
            raise ValueError('영상 파일을 선택하세요.')
    if is_url and not shutil.which('yt-dlp'):
        raise RuntimeError('URL 입력에는 yt-dlp가 필요합니다.')
    installed_python = Path(os.environ.get('LOCALAPPDATA', '')) / 'Goni' / 'erase-env' / 'Scripts' / 'python.exe'
    demucs_python = os.environ.get('GONI_DEMUCS_PYTHON', str(installed_python) if installed_python.is_file() else sys.executable)
    ocr_python = os.environ.get('GONI_ERASE_PYTHON', demucs_python)
    if audio in ('remove_voice', 'voice_only'):
        check = subprocess.run([demucs_python, '-c', 'import demucs'], capture_output=True)
        if check.returncode:
            raise RuntimeError('음성 분리에는 Demucs 설치가 필요합니다. 별도 환경은 GONI_DEMUCS_PYTHON으로 지정하세요.')
    if auto_text:
        check = subprocess.run([ocr_python, '-c', 'import cv2, easyocr'], capture_output=True)
        if check.returncode:
            raise RuntimeError('자동 자막 처리에는 EasyOCR과 OpenCV가 필요합니다. GONI_ERASE_PYTHON을 설정하세요.')
    out.mkdir(parents=True)
    if is_url:
        downloaded = out / 'downloaded-path.txt'
        run(['yt-dlp', '--ignore-config', '--no-playlist', '--no-overwrites',
             '--merge-output-format', 'mp4', '-o', str(out / 'source.%(ext)s'),
             '--print-to-file', 'after_move:filepath', str(downloaded), '--', source])
        source = downloaded.read_text(encoding='utf-8').splitlines()[-1].strip()
    info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams',
                                                '-show_format', '-of', 'json', source]))
    video = next((s for s in info['streams'] if s['codec_type'] == 'video'), None)
    has_audio = any(s['codec_type'] == 'audio' for s in info['streams'])
    if not video:
        raise ValueError('영상 스트림이 없습니다.')
    if region is not None:
        if len(region) != 4 or any(type(n) is not int for n in region):
            raise ValueError('영역은 정수 x,y,너비,높이입니다.')
        x, y, w, h = region
        if x < 1 or y < 1 or w < 1 or h < 1 or x + w >= video['width'] or y + h >= video['height']:
            raise ValueError('영역은 영상 안에 있어야 하며 가장자리를 피해야 합니다.')
    if audio in ('remove_voice', 'voice_only') and not has_audio:
        raise ValueError('원본에 오디오가 없습니다.')
    stem = None
    if audio in ('remove_voice', 'voice_only'):
        wav = out / 'source-audio.wav'
        run(['ffmpeg', '-v', 'error', '-nostdin', '-n', '-i', source, '-map', '0:a:0',
             '-vn', '-ac', '2', '-ar', '44100', str(wav)])
        run([demucs_python, '-m', 'demucs', '--two-stems', 'vocals', '-o', str(out / 'stems'), str(wav)])
        stem = out / 'stems' / 'htdemucs' / 'source-audio' / ('no_vocals.wav' if audio == 'remove_voice' else 'vocals.wav')
        if not stem.is_file():
            raise RuntimeError('음성 분리 결과를 찾지 못했습니다.')
    video_input = source
    if auto_text:
        video_input = str(out / 'ocr-video.mp4')
        run([ocr_python, str(Path(__file__).with_name('auto_erase_text.py')), source, video_input])
    result = out / 'cleaned.mp4'
    cmd = ['ffmpeg', '-v', 'error', '-nostdin', '-n', '-i', video_input]
    if stem:
        cmd += ['-i', str(stem)]
    elif auto_text and audio == 'keep' and has_audio:
        cmd += ['-i', source]
    cmd += ['-map', '0:v:0']
    if stem:
        cmd += ['-map', '1:a:0']
    elif audio == 'keep' and has_audio:
        cmd += ['-map', '1:a:0' if auto_text else '0:a:0']
    if region:
        cmd += ['-vf', f'delogo=x={x}:y={y}:w={w}:h={h}', '-c:v', 'libx264', '-crf', '18', '-preset', 'fast']
    else:
        cmd += ['-c:v', 'copy']
    cmd += ['-c:a', 'aac', '-map_metadata', '-1', '-movflags', '+faststart', str(result)]
    run(cmd)
    run(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(result), '-f', 'null', '-'])
    report = {'output': str(result), 'region': region, 'audio': audio,
              'method': ('easyocr+opencv per-frame spatial inpaint' if auto_text else
                         'ffmpeg delogo spatial interpolation' if region else 'no pixel editing'),
              'separation': 'Demucs htdemucs' if stem else None,
              'subtitle_tracks': 'excluded', 'verified': 'full decode only; visual/audio quality requires review'}
    (out / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description='고니 영상 정리: 지정 영역 지우기와 음성 선택')
    parser.add_argument('--input', required=True, help='영상 파일 또는 URL')
    parser.add_argument('--output', required=True, help='새 출력 폴더')
    parser.add_argument('--region', nargs=4, type=int, metavar=('X', 'Y', 'W', 'H'))
    parser.add_argument('--auto-text', action='store_true', help='화면 글자 OCR 자동 감지·지우기')
    parser.add_argument('--audio', choices=('keep', 'mute', 'remove_voice', 'voice_only'), default='keep')
    args = parser.parse_args()
    try:
        print(json.dumps(clean_video(args.input, args.output, args.region, args.audio, args.auto_text), ensure_ascii=False, indent=2))
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f'오류: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
