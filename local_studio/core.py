"""Local media pipeline. No third-party service or account is required."""
import copy
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import textwrap
import uuid

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
VIDEO_EXTENSIONS = {'.mp4', '.mov', '.mkv', '.webm', '.m4v', '.avi'}
from template_styles import CATALOG, PRESETS, timed_text, decorate
THEMES = {item['id']: tuple(item['palette']) for item in CATALOG}


def run(args, cwd=None, timeout=7200):
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=timeout,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise ValueError(result.stderr[-2400:] or '미디어 처리에 실패했습니다.')
    return result.stdout


def probe(path):
    info = json.loads(run(['ffprobe', '-v', 'error', '-show_format', '-show_streams',
                          '-of', 'json', str(path)], timeout=60))
    video = next((s for s in info['streams'] if s['codec_type'] == 'video'), None)
    duration = float(info.get('format', {}).get('duration', 0))
    if not video or not math.isfinite(duration) or duration <= 0:
        raise ValueError('길이를 확인할 수 있는 영상 파일을 선택하세요.')
    return {'duration': duration, 'width': video['width'], 'height': video['height'],
            'has_audio': any(s['codec_type'] == 'audio' for s in info['streams']),
            'codec': video['codec_name']}


def project_dir(project_id):
    if not re.fullmatch(r'[a-f0-9]{32}', project_id):
        raise ValueError('잘못된 프로젝트 번호입니다.')
    return DATA / project_id


def read_project(project_id):
    return json.loads((project_dir(project_id) / 'project.json').read_text(encoding='utf-8'))


def save_project(project):
    folder = project_dir(project['id'])
    folder.mkdir(parents=True, exist_ok=True)
    temp = folder / f'{uuid.uuid4().hex}.tmp'
    temp.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temp, folder / 'project.json')


def import_file(path, title=None, preview=True):
    path = Path(path).expanduser().resolve()
    if not path.is_file() or path.suffix.lower() not in VIDEO_EXTENSIONS:
        raise ValueError('MP4, MOV, MKV, WebM 영상 파일을 선택하세요.')
    meta = probe(path)
    project_id = uuid.uuid4().hex
    folder = project_dir(project_id)
    folder.mkdir(parents=True)
    source = folder / ('source' + path.suffix.lower())
    shutil.copy2(path, source)
    if preview:
        # Browser preview is optional for headless jobs, H.264/AAC for the editor.
        run(['ffmpeg', '-y', '-v', 'error', '-i', str(source), '-map', '0:v:0', '-map', '0:a:0?',
             '-vf', 'scale=960:960:force_original_aspect_ratio=decrease:force_divisible_by=2',
             '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '27', '-c:a', 'aac',
             '-movflags', '+faststart', str(folder / 'preview.mp4')])
        run(['ffmpeg', '-y', '-v', 'error', '-i', str(source), '-frames:v', '1',
             '-vf', 'scale=480:-2', str(folder / 'poster.jpg')])
    project = {'id': project_id, 'name': title or path.stem, 'source': source.name,
               'meta': meta, 'segments': [], 'candidates': [], 'exports': [],
               'edit': {'start': 0, 'end': min(meta['duration'], 40), 'speed': 1.0,
                        'layout': 'fit', 'theme': 'safe', 'title': '', 'footer': '', 'captions': True}}
    save_project(project)
    return project


def finite(value, label):
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError(f'{label}: 숫자를 입력하세요.') from None
    if not math.isfinite(value):
        raise ValueError(f'{label}: 유효한 숫자를 입력하세요.')
    return value


def validate_edit(edit, duration):
    start, end, speed = (finite(edit.get(k), k) for k in ('start', 'end', 'speed'))
    if start < 0 or end > duration + .02 or end - start < .25:
        raise ValueError('구간은 영상 안에 있어야 하며 0.25초 이상이어야 합니다.')
    if not .5 <= speed <= 2:
        raise ValueError('배속은 0.5~2.0 범위입니다.')
    if edit.get('layout') not in ('fit', 'crop'):
        raise ValueError('지원하지 않는 레이아웃입니다.')
    if edit.get('theme', 'dark') not in THEMES:
        raise ValueError('지원하지 않는 템플릿입니다.')
    title, footer = str(edit.get('title', '')), str(edit.get('footer', ''))
    if len(title) > 56 or len(footer) > 42:
        raise ValueError('상단 문구는 56자, 하단 문구는 42자까지입니다.')
    if title.count('\n') > 1 or footer.count('\n') > 1:
        raise ValueError('제목과 하단 문구는 직접 줄바꿈을 한 번까지 넣을 수 있습니다.')
    comment = str(edit.get('comment', ''))
    if len(comment) > 80:
        raise ValueError('댓글 문구는 80자까지입니다.')
    return {'comment': comment, 'start': start, 'end': min(end, duration), 'speed': speed,
            'layout': edit['layout'], 'theme': edit.get('theme', 'dark'), 'title': title, 'footer': footer,
            'captions': bool(edit.get('captions', True))}


def validate_segments(segments, duration):
    if not isinstance(segments, list) or len(segments) > 25000:
        raise ValueError('자막 목록이 잘못되었습니다.')
    result = []
    for item in segments:
        start, end = finite(item['start'], '자막 시작'), finite(item['end'], '자막 끝')
        text = str(item.get('text', '')).strip()
        if start < 0 or end <= start or end > duration + .1 or len(text) > 1000:
            raise ValueError('자막 시간을 영상 범위 안에서 순서대로 입력하세요. 한 항목은 1,000자까지입니다.')
        if text:
            result.append({'start': start, 'end': min(end, duration), 'text': text})
    return sorted(result, key=lambda x: x['start'])


def parse_srt(text):
    result = []
    def seconds(value):
        h, m, s, ms = map(int, re.split('[:,.]', value))
        if m > 59 or s > 59:
            raise ValueError('SRT 시간 형식을 확인하세요.')
        return h * 3600 + m * 60 + s + ms / 1000
    for block in re.split(r'\n\s*\n', text.replace('\r', '').strip().lstrip('\ufeff')):
        lines = block.splitlines()
        timing = next((i for i, line in enumerate(lines) if '-->' in line), None)
        if timing is None:
            continue
        match = re.fullmatch(r'\s*(\d+:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d+:\d{2}:\d{2}[,.]\d{3})\s*', lines[timing])
        if not match:
            raise ValueError('SRT 시간 형식을 확인하세요.')
        result.append({'start': seconds(match[1]), 'end': seconds(match[2]),
                       'text': '\n'.join(lines[timing + 1:])})
    if not result:
        raise ValueError('SRT 자막을 찾지 못했습니다.')
    return result


def clip_segments(segments, edit):
    clipped = []
    for segment in segments:
        start, end = max(segment['start'], edit['start']), min(segment['end'], edit['end'])
        if end > start:
            clipped.append({'start': (start - edit['start']) / edit['speed'],
                            'end': (end - edit['start']) / edit['speed'], 'text': segment['text']})
    return clipped


def timestamp(seconds, ass=False):
    units = int(round(seconds * (100 if ass else 1000)))
    scale = 100 if ass else 1000
    total, frac = divmod(units, scale)
    minutes, sec = divmod(total, 60)
    hours, minute = divmod(minutes, 60)
    return f'{hours:01d}:{minute:02d}:{sec:02d}.{frac:02d}' if ass else f'{hours:02d}:{minute:02d}:{sec:02d},{frac:03d}'


def to_srt(segments):
    return '\n\n'.join(f'{i+1}\n{timestamp(s["start"])} --> {timestamp(s["end"])}\n{s["text"]}'
                       for i, s in enumerate(segments)) + '\n'


def recommend(segments, duration, target=40):
    target = max(5, min(90, finite(target, '추천 길이')))
    if not segments:
        raise ValueError('먼저 음성을 인식하거나 SRT를 불러오세요.')
    keywords = ['방법', '중요', '이유', '문제', '왜', '비결', '핵심', '직접', '자동', '결과', '하지만', '실제로']
    choices = []
    for i, first in enumerate(segments):
        selected = []
        for s in segments[i:]:
            if s['end'] - first['start'] > target * 1.3:
                break
            selected.append(s)
            if s['end'] - first['start'] >= target:
                break
        if not selected:
            continue
        start, end = first['start'], min(duration, selected[-1]['end'])
        if end - start < min(8, target * .5):
            continue
        text = ' '.join(s['text'] for s in selected)
        matches = [k for k in keywords if k in text]
        score = len(matches) * 3 + min(len(text) / 50, 8) - abs(end - start - target) / 6
        choices.append({'start': start, 'end': end, 'label': first['text'][:52],
                        'reason': ('키워드: ' + ', '.join(matches[:4])) if matches else '발화 밀도와 문장 경계 기준',
                        'score': round(score, 2)})
    result = []
    for candidate in sorted(choices, key=lambda s: s['score'], reverse=True):
        if all(max(0, min(candidate['end'], old['end']) - max(candidate['start'], old['start']))
               < .25 * min(candidate['end'] - candidate['start'], old['end'] - old['start']) for old in result):
            result.append(candidate)
        if len(result) == 5:
            break
    return result


def transcribe(project, model_name, progress):
    if model_name not in ('tiny', 'base', 'small', 'medium'):
        raise ValueError('지원하지 않는 음성 모델입니다.')
    if not project['meta']['has_audio']:
        raise ValueError('음성 트랙이 없는 영상입니다. SRT를 불러오세요.')
    from faster_whisper import WhisperModel
    progress(5, '로컬 음성 모델 불러오는 중')
    try:
        model = WhisperModel(model_name, device='cpu', compute_type='int8', cpu_threads=4,
                             local_files_only=True)
    except Exception as error:
        raise ValueError('음성 모델 캐시가 없거나 읽을 수 없습니다. SRT를 불러오거나 README의 모델 준비 명령을 실행하세요.') from error
    segments, _ = model.transcribe(str(project_dir(project['id']) / project['source']),
                                    language='ko', vad_filter=True, beam_size=3)
    result = []
    for s in segments:
        if s.text.strip():
            result.append({'start': max(0, s.start), 'end': min(project['meta']['duration'], s.end),
                           'text': s.text.strip()})
        progress(min(95, 10 + s.end / project['meta']['duration'] * 85), '한국어 자막 만드는 중')
    return validate_segments(result, project['meta']['duration'])


def title_layout(text, draw, font_path):
    """Fit the complete title into two lines inside the top 9:16 safe band."""
    from PIL import ImageFont
    for size in range(76, 23, -2):
        font = ImageFont.truetype(str(font_path), size)
        lines = []
        for paragraph in text.split('\n'):
            line = ''
            for word in paragraph.split():
                candidate = f'{line} {word}' if line else word
                if draw.textlength(candidate, font=font) <= 880:
                    line = candidate
                    continue
                if line:
                    lines.append(line)
                    line = ''
                for char in word:
                    if line and draw.textlength(line + char, font=font) > 880:
                        lines.append(line)
                        line = char
                    else:
                        line += char
            lines.append(line)
        if len(lines) > 2:
            continue
        height = size * len(lines) + 16 * (len(lines) - 1)
        y = round(225 - height / 2)
        boxes = [draw.textbbox((540, y + i * (size + 16)), line, font=font,
                               anchor='mt', stroke_width=2) for i, line in enumerate(lines)]
        if all(left >= 90 and right <= 990 and top >= 90 and bottom <= 360
               for left, top, right, bottom in boxes):
            return font, lines, y, boxes
    raise ValueError('제목이 상단 안전영역에 들어가지 않습니다. 제목을 줄여주세요.')


def make_overlay(edit, path):
    from PIL import Image, ImageDraw, ImageFont
    font_path = Path('C:/Windows/Fonts/malgunbd.ttf')
    if not font_path.exists():
        raise ValueError('한글 폰트를 찾을 수 없습니다: C:/Windows/Fonts/malgunbd.ttf')
    canvas = Image.new('RGBA', (1080, 1920))
    draw = ImageDraw.Draw(canvas)
    def draw_block(text, y, size, fill):
        if not text.strip():
            return
        font = ImageFont.truetype(str(font_path), size)
        lines = []
        for paragraph in text.splitlines():
            line = ''
            for char in paragraph:
                if draw.textlength(line + char, font=font) > 900 and line:
                    lines.append(line)
                    line = char
                else:
                    line += char
            lines.append(line)
        while len(lines) > 3 and size > 36:
            return draw_block(text, y, size - 6, fill)
        for i, line in enumerate(lines):
            draw.text((540, y + i * (size + 18)), line, font=font, anchor='mt', fill=fill,
                      stroke_width=0 if edit.get('theme') in ('paper', 'white-yellow', 'paper-story') else 2,
                      stroke_fill=(0, 0, 0, 255))
    decorate(draw, edit, font_path)
    palette = THEMES[edit.get('theme', 'dark')]
    if edit['title'].strip():
        title_font, title_lines, title_y, _ = title_layout(edit['title'], draw, font_path)
        for i, line in enumerate(title_lines):
            draw.text((540, title_y + i * (title_font.size + 16)), line,
                      font=title_font, anchor='mt', fill=palette[1],
                      stroke_width=0 if edit.get('theme') in ('paper', 'white-yellow', 'paper-story') else 2,
                      stroke_fill=(0, 0, 0, 255))
    if edit.get('theme') == 'comment-capture':
        footer = edit['footer'].replace('\n', ' ')
        size = 32
        footer_font = ImageFont.truetype(str(font_path), size)
        while draw.textlength(footer, font=footer_font) > 900 and size > 16:
            size -= 1
            footer_font = ImageFont.truetype(str(font_path), size)
        draw.text((540, 1830), footer, font=footer_font, fill=palette[2], anchor='mt')
    else:
        draw_block(edit['footer'], 1580, 46, palette[2])
    canvas.save(path)


def make_ass(segments, theme='safe'):
    header = '''[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Malgun Gothic,64,&H00FFFFFF,&H00FFFFFF,&H00000000,&H90000000,-1,0,0,0,100,100,0,0,1,4,0,2,100,100,460,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    rows = []
    style = PRESETS[theme]['caption_style']
    for segment in segments:
        for start, end, text in timed_text(segment, style):
            if style == 'standard':
                lines = []
                for line in text.splitlines():
                    lines.extend(textwrap.wrap(line, width=16, break_long_words=True) or [''])
                text = r'\N'.join(lines)
            rows.append(f'Dialogue: 0,{timestamp(start, True)},{timestamp(end, True)},Default,,0,0,0,,{text}')
    return header + '\n'.join(rows)


def render(project, progress):
    project = copy.deepcopy(project)
    edit = validate_edit(project['edit'], project['meta']['duration'])
    folder = project_dir(project['id'])
    export_id = uuid.uuid4().hex[:12]
    output = folder / 'exports' / export_id
    output.mkdir(parents=True)
    segments = clip_segments(project['segments'], edit)
    (output / 'captions.srt').write_text(to_srt(segments), encoding='utf-8-sig')
    (output / 'captions.ass').write_text(make_ass(segments, edit['theme']), encoding='utf-8-sig')
    (output / 'edit.json').write_text(json.dumps({'edit': edit, 'segments': project['segments']},
                                               ensure_ascii=False, indent=2), encoding='utf-8')
    make_overlay(edit, output / 'overlay.png')
    progress(10, '1080 × 1920 영상 인코딩 중')
    fit = ('scale=1080:1080:force_original_aspect_ratio=decrease:force_divisible_by=2,'
           'pad=1080:1080:(ow-iw)/2:(oh-ih)/2:black')
    crop = 'scale=1080:1080:force_original_aspect_ratio=increase,crop=1080:1080'
    background = THEMES[edit.get('theme', 'dark')][0].replace('#', '0x')
    chain = f'[0:v]setpts=(PTS-STARTPTS)/{edit["speed"]},{fit if edit["layout"] == "fit" else crop},pad=1080:1920:0:400:{background},setsar=1[base];[base][1:v]overlay=0:0'
    if edit['captions'] and segments:
        chain += ",ass=captions.ass"
    chain += '[v]'
    command = ['ffmpeg', '-y', '-v', 'error', '-ss', str(edit['start']), '-t', str(edit['end'] - edit['start']),
               '-i', str(folder / project['source']), '-i', 'overlay.png', '-filter_complex', chain,
               '-map', '[v]']
    if project['meta']['has_audio']:
        command += ['-map', '0:a:0', '-af', f'asetpts=PTS-STARTPTS,atempo={edit["speed"]}', '-c:a', 'aac', '-b:a', '192k']
    command += ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-threads', '4', '-r', '30',
                '-pix_fmt', 'yuv420p', '-t', str((edit['end'] - edit['start']) / edit['speed']),
                '-movflags', '+faststart', 'short.mp4']
    run(command, cwd=output)
    progress(90, '출력 파일 전체 디코딩 검증 중')
    run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(output / 'short.mp4'), '-f', 'null', '-'])
    meta = probe(output / 'short.mp4')
    expected = (edit['end'] - edit['start']) / edit['speed']
    if meta['width'] != 1080 or meta['height'] != 1920 or abs(meta['duration'] - expected) > .2:
        raise ValueError('출력 규격 검증에 실패했습니다.')
    run(['ffmpeg', '-y', '-v', 'error', '-i', str(output / 'short.mp4'), '-frames:v', '1', str(output / 'thumbnail.jpg')])
    return {'id': export_id, 'duration': meta['duration'], 'edit': edit, 'has_audio': meta['has_audio']}
