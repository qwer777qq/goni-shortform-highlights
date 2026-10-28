"""Versioned multi-cut reels. Numeric FFmpeg filters only; no shell execution."""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import uuid

import core

SIZES = {'landscape': (1920, 1080), 'portrait': (1080, 1920)}


def number(value, label, low, high):
    value = core.finite(value, label)
    if not low <= value <= high:
        raise ValueError(f'{label}: {low}~{high} 범위로 입력하세요.')
    return value


def validate(plan, duration):
    if not isinstance(plan, dict):
        raise ValueError('편집 설정은 객체여야 합니다.')
    ratio = plan.get('ratio', 'landscape')
    if ratio not in SIZES:
        raise ValueError('화면 비율은 landscape 또는 portrait입니다.')
    layout = plan.get('layout', 'fit')
    if layout not in ('fit', 'crop'):
        raise ValueError('배치는 fit 또는 crop입니다.')
    audio = plan.get('audio', 'source')
    if audio not in ('source', 'continuous', 'mute'):
        raise ValueError('음성 모드를 확인하세요.')
    clips = plan.get('clips')
    if not isinstance(clips, list) or not 1 <= len(clips) <= 40:
        raise ValueError('장면은 1~40개로 구성하세요.')
    clean = []
    for clip in clips:
        if not isinstance(clip, dict):
            raise ValueError('장면 설정을 확인하세요.')
        start = number(clip.get('start'), '시작', 0, duration)
        end = number(clip.get('end'), '끝', 0, duration)
        if end - start < .1:
            raise ValueError('각 장면은 0.1초 이상이어야 합니다.')
        speed = number(clip.get('speed', 1), '배속', .5, 2)
        frames = max(1, round((end - start) / speed * 30))
        seconds = frames / 30
        effects = {}
        for effect in ('invert', 'flash'):
            windows = clip.get(effect, [])
            if not isinstance(windows, list) or len(windows) > 8:
                raise ValueError('효과 구간은 종류별 최대 8개입니다.')
            effects[effect] = []
            for window in windows:
                if not isinstance(window, list) or len(window) != 2:
                    raise ValueError('효과 구간은 [시작, 끝] 초입니다.')
                a = number(window[0], '효과 시작', 0, seconds)
                b = number(window[1], '효과 끝', 0, seconds)
                if a >= b:
                    raise ValueError('효과 끝은 시작보다 커야 합니다.')
                effects[effect].append([a, b])
        clean.append(dict(start=start, end=end, speed=speed, frames=frames,
                          zoom=number(clip.get('zoom', 1), '확대', 1, 1.3),
                          contrast=number(clip.get('contrast', 1), '대비', .5, 1.8),
                          brightness=number(clip.get('brightness', 0), '밝기', -.2, .2),
                          saturation=number(clip.get('saturation', 1), '채도', 0, 2), **effects))
    total = sum(c['frames'] for c in clean) / 30
    if total > 180:
        raise ValueError('릴스 편집은 최대 180초입니다.')
    audio_start = number(plan.get('audio_start', 0), '연속 음원 시작', 0, duration)
    if audio == 'continuous' and audio_start + total > duration + .04:
        raise ValueError('연속 음원 길이가 부족합니다. 시작 위치 또는 편집 길이를 줄이세요.')
    return dict(version=1, ratio=ratio, layout=layout, audio=audio, audio_start=audio_start,
                clips=clean, duration=total, fps=30)


def preset(duration, ratio='landscape'):
    """Evenly sampled demo, never claimed to infer semantics or beats."""
    if duration < 1:
        raise ValueError('프리셋은 1초 이상 영상에 적용하세요.')
    count, width = 4, min(duration / 4, 2)
    clips = []
    for i in range(count):
        start = i * (duration - width) / (count - 1)
        clips.append(dict(start=round(start, 4), end=round(start + width, 4), speed=1,
                          zoom=1.03, contrast=1.08, brightness=-.005, saturation=.9,
                          invert=[[0, min(.067, width)]] if i in (0, 2) else [], flash=[]))
    return validate(dict(ratio=ratio, layout='fit', audio='continuous', clips=clips), duration)


def save(project_id, plan):
    project = core.read_project(project_id)
    plan = validate(plan, project['meta']['duration'])
    project['reel'] = plan
    core.save_project(project)
    return plan


def expression(windows):
    # Half-open windows: avoids applying an extra frame at the end.
    return '+'.join(f'gte(t,{a:.6f})*lt(t,{b:.6f})' for a, b in windows)


def filters(clip, plan):
    w, h = SIZES[plan['ratio']]
    if plan['layout'] == 'fit':
        fit = f'scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black'
    else:
        fit = f'scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}'
    result = [f'setpts=(PTS-STARTPTS)/{clip["speed"]:.6f}', 'fps=30', fit, 'setsar=1']
    if clip['zoom'] > 1:
        # A subtle static crop; it is not a camera-tracking/zoom-ramp algorithm.
        cw, ch = int(w / clip['zoom']) // 2 * 2, int(h / clip['zoom']) // 2 * 2
        result.extend([f'crop={cw}:{ch}:(iw-ow)/2:(ih-oh)/2', f'scale={w}:{h}'])
    result.append(f'eq=contrast={clip["contrast"]}:brightness={clip["brightness"]}:saturation={clip["saturation"]}')
    if clip['invert']:
        result.append(f"negate=enable='{expression(clip['invert'])}'")
    if clip['flash']:
        result.append(f"drawbox=x=0:y=0:w=iw:h=ih:color=white@0.45:t=fill:enable='{expression(clip['flash'])}'")
    result.extend(['tpad=stop_mode=clone:stop_duration=0.1', f'trim=end_frame={clip["frames"]}', 'setpts=PTS-STARTPTS', 'format=yuv420p'])
    return ','.join(result)


def render(project_id, plan=None, progress=lambda *args: None):
    project = core.read_project(project_id)
    plan = validate(plan if plan is not None else project.get('reel', {}), project['meta']['duration'])
    folder = core.project_dir(project_id).resolve()
    source = (folder / project['source']).resolve()
    if not source.is_relative_to(folder) or not source.is_file():
        raise ValueError('프로젝트 원본을 찾지 못했습니다.')
    version = 'reel-' + uuid.uuid4().hex[:12]
    out = folder / 'exports' / version
    out.mkdir(parents=True)
    (out / 'edit.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    commands, timeline, cursor = [], [], 0

    def run(args):
        commands.append(args)
        core.run(args)

    try:
        for i, clip in enumerate(plan['clips']):
            progress(5 + 65 * i / len(plan['clips']), f'장면 {i+1}/{len(plan["clips"])} 렌더링')
            seconds = clip['frames'] / 30
            args = ['ffmpeg', '-v', 'error', '-nostdin', '-n', '-ss', str(clip['start']),
                    '-t', str(clip['end'] - clip['start']), '-i', str(source)]
            real_audio = project['meta']['has_audio'] and plan['audio'] == 'source'
            if not real_audio:
                args += ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo']
            args += ['-map', '0:v:0', '-map', '0:a:0' if real_audio else '1:a:0',
                     '-vf', filters(clip, plan), '-af',
                     (f'atempo={clip["speed"]},' if real_audio else '') +
                     f'apad,atrim=duration={seconds:.6f},asetpts=PTS-STARTPTS',
                     '-t', f'{seconds:.6f}', '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
                     '-threads', '4', '-c:a', 'aac', '-ar', '48000', '-ac', '2',
                     '-video_track_timescale', '90000', str(out / f'part-{i:02d}.mp4')]
            run(args)
            timeline.append(dict(index=i, source_start=clip['start'], source_end=clip['end'],
                                 output_start=cursor, output_end=cursor + seconds, speed=clip['speed']))
            cursor += seconds
        manifest = out / 'concat.txt'
        manifest.write_text(''.join(f"file 'part-{i:02d}.mp4'\n" for i in range(len(plan['clips']))), encoding='utf-8')
        progress(75, '장면 연결 및 음원 처리')
        args = ['ffmpeg', '-v', 'error', '-nostdin', '-n', '-f', 'concat', '-safe', '1', '-i', str(manifest)]
        if plan['audio'] == 'continuous' and project['meta']['has_audio']:
            args += ['-ss', str(plan['audio_start']), '-i', str(source), '-map', '0:v:0', '-map', '1:a:0',
                     '-af', f'apad,atrim=duration={cursor:.6f},asetpts=PTS-STARTPTS,afade=t=out:st={max(0,cursor-.12):.6f}:d=0.12']
        else:
            args += ['-map', '0:v:0', '-map', '0:a:0']
        video = out / 'reel.mp4'
        args += ['-t', f'{cursor:.6f}', '-c:v', 'copy', '-c:a', 'aac', '-ar', '48000', '-ac', '2', '-movflags', '+faststart', str(video)]
        run(args)
        progress(88, '전체 디코딩 및 규격 검사')
        run(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(video), '-f', 'null', '-'])
        meta = core.probe(video)
        expected_size = SIZES[plan['ratio']]
        if (meta['width'], meta['height']) != expected_size or abs(meta['duration'] - cursor) > .15:
            raise ValueError('출력 규격/길이 검증에 실패했습니다.')
        run(['ffmpeg', '-v', 'error', '-nostdin', '-n', '-i', str(video), '-frames:v', '1', '-vf', 'scale=960:-2', str(out / 'poster.jpg')])
        report = dict(status='verified_decode', meta=meta, expected_duration=cursor, timeline=timeline,
                      note='자동 디코드·규격 검사. 시각 품질·음악 박자 검수와 별도입니다.',
                      created_at=datetime.now(timezone.utc).isoformat())
        (out / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        result = dict(id=version, video=f'exports/{version}/reel.mp4', poster=f'exports/{version}/poster.jpg',
                      settings=f'exports/{version}/edit.json', verification=f'exports/{version}/verification.json',
                      duration=meta['duration'], path=str(video))
        # Never rewrite a potentially concurrently edited project from an old snapshot.
        latest = core.read_project(project_id)
        latest.setdefault('reel_exports', []).insert(0, result)
        core.save_project(latest)
        progress(100, '완료')
        return result
    except Exception as error:
        (out / 'failure.json').write_text(json.dumps({'status': 'failed', 'error': str(error)}, ensure_ascii=False), encoding='utf-8')
        raise
    finally:
        (out / 'commands.json').write_text(json.dumps(commands, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description='고니 릴스 편집 CLI')
    parser.add_argument('--data-dir', type=Path)
    sub = parser.add_subparsers(dest='action', required=True)
    imp = sub.add_parser('import'); imp.add_argument('path')
    ren = sub.add_parser('render'); ren.add_argument('project_id'); ren.add_argument('plan', type=Path)
    pre = sub.add_parser('preset'); pre.add_argument('project_id')
    args = parser.parse_args()
    if args.data_dir:
        core.DATA = args.data_dir.resolve()
    if args.action == 'import':
        result = core.import_file(args.path)
    elif args.action == 'preset':
        result = preset(core.read_project(args.project_id)['meta']['duration'])
    else:
        plan = json.loads(args.plan.read_text(encoding='utf-8-sig'))
        save(args.project_id, plan)
        result = render(args.project_id, plan)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
