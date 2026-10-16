"""Loopback-only local Shorts editor, using Python's standard HTTP server."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import re
import shutil
import threading
import time
from urllib.parse import parse_qs, unquote, urlparse
import uuid

import core

JOBS = {}
LOCK = threading.RLock()
POOL = ThreadPoolExecutor(max_workers=1)
STATIC = core.ROOT / 'static'
PORT = 8767


def start_job(kind, work, project_id=None):
    job_id = uuid.uuid4().hex
    with LOCK:
        JOBS[job_id] = {'id': job_id, 'kind': kind, 'status': 'queued', 'progress': 0,
                        'message': '작업 대기 중', 'project_id': project_id}
    def update(progress, message):
        with LOCK:
            JOBS[job_id].update(progress=round(progress), message=message)
    def task():
        with LOCK:
            JOBS[job_id]['status'] = 'running'
        try:
            result = work(update)
            with LOCK:
                JOBS[job_id].update(status='done', progress=100, message='완료', result=result)
        except Exception as error:
            with LOCK:
                JOBS[job_id].update(status='error', message=str(error))
    POOL.submit(task)
    return JOBS[job_id].copy()


def busy(project_id):
    return any(j.get('project_id') == project_id and j['status'] in ('queued', 'running') for j in JOBS.values())


class Handler(BaseHTTPRequestHandler):
    server_version = 'LocalShorts/1.0'

    def log_message(self, format, *args):
        pass

    def guard(self, write=False):
        host = self.headers.get('Host', '')
        if host not in (f'127.0.0.1:{PORT}', f'localhost:{PORT}'):
            raise PermissionError('로컬 주소로 접속하세요.')
        origin = self.headers.get('Origin')
        if origin and origin not in (f'http://127.0.0.1:{PORT}', f'http://localhost:{PORT}'):
            raise PermissionError('다른 사이트에서 요청할 수 없습니다.')
        if self.headers.get('Sec-Fetch-Site') == 'cross-site':
            raise PermissionError('다른 사이트에서 요청할 수 없습니다.')
        if write and self.headers.get('X-Studio-Request') != '1':
            raise PermissionError('편집기에서 다시 요청하세요.')

    def json(self, value, code=200):
        data = json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def read_json(self):
        length = int(self.headers.get('Content-Length', 0))
        if not 0 < length <= 8 * 1024 * 1024:
            raise ValueError('요청 크기를 확인하세요.')
        return json.loads(self.rfile.read(length))

    def file(self, path, download=False):
        if not path.is_file():
            raise FileNotFoundError()
        size = path.stat().st_size
        start, end, partial = 0, size - 1, False
        request_range = self.headers.get('Range')
        if request_range:
            match = re.fullmatch(r'bytes=(\d*)-(\d*)', request_range)
            if not match or (not match[1] and not match[2]):
                self.send_error(416)
                return
            if match[1]:
                start = int(match[1])
                end = min(end, int(match[2])) if match[2] else end
            else:
                start = max(0, size - int(match[2]))
            if start > end or start >= size:
                self.send_response(416)
                self.send_header('Content-Range', f'bytes */{size}')
                self.end_headers()
                return
            partial = True
        self.send_response(206 if partial else 200)
        self.send_header('Content-Type', mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
        self.send_header('Content-Length', str(max(0, end - start + 1)))
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-cache')
        if partial:
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        if download:
            self.send_header('Content-Disposition', f'attachment; filename="{path.name}"')
        self.end_headers()
        with path.open('rb') as handle:
            handle.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                data = handle.read(min(1024 * 1024, remaining))
                if not data:
                    break
                self.wfile.write(data)
                remaining -= len(data)

    def do_GET(self):
        try:
            self.guard()
            parsed = urlparse(self.path)
            path = unquote(parsed.path)
            if path == '/api/config':
                self.json({'ffmpeg': bool(shutil.which('ffmpeg')), 'ffprobe': bool(shutil.which('ffprobe')),
                           'data_dir': str(core.DATA), 'demo_available': (core.ROOT / 'demo.mp4').exists()})
            elif path == '/api/projects':
                projects = []
                for item in sorted(core.DATA.glob('*/project.json'), key=lambda p: p.stat().st_mtime, reverse=True):
                    try:
                        p = json.loads(item.read_text(encoding='utf-8'))
                        projects.append({k: p[k] for k in ('id', 'name', 'meta')})
                    except (OSError, ValueError, KeyError):
                        continue
                self.json(projects)
            elif path.startswith('/api/projects/'):
                with LOCK:
                    self.json(core.read_project(path.rsplit('/', 1)[-1]))
            elif path.startswith('/api/jobs/'):
                with LOCK:
                    self.json(JOBS[path.rsplit('/', 1)[-1]])
            elif path.startswith('/media/'):
                parts = path.split('/')
                folder = core.project_dir(parts[2])
                relative = Path(*parts[3:])
                target = (folder / relative).resolve()
                if not target.is_relative_to(folder.resolve()) or target.suffix not in ('.mp4', '.jpg', '.srt', '.json'):
                    raise PermissionError('허용되지 않는 파일입니다.')
                self.file(target, 'download' in parse_qs(parsed.query))
            else:
                assets = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}
                if path not in assets:
                    raise FileNotFoundError()
                self.file(STATIC / assets[path])
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except PermissionError as error:
            self.json({'error': str(error)}, 403)
        except (FileNotFoundError, KeyError):
            self.json({'error': '항목을 찾지 못했습니다.'}, 404)
        except Exception as error:
            self.json({'error': str(error)}, 400)

    def do_POST(self):
        try:
            self.guard(write=True)
            parsed = urlparse(self.path)
            if parsed.path == '/api/upload':
                length = int(self.headers.get('Content-Length', 0))
                if not 0 < length <= 10 * 1024 ** 3:
                    raise ValueError('영상은 10GB 이하로 선택하세요.')
                filename = parse_qs(parsed.query).get('name', ['video.mp4'])[0]
                suffix = Path(filename).suffix.lower()
                if suffix not in core.VIDEO_EXTENSIONS:
                    raise ValueError('지원하는 영상 파일을 선택하세요.')
                staging = core.DATA / 'incoming'
                staging.mkdir(parents=True, exist_ok=True)
                path = staging / (uuid.uuid4().hex + suffix)
                self.connection.settimeout(300)
                try:
                    with path.open('wb') as handle:
                        remaining = length
                        while remaining:
                            chunk = self.rfile.read(min(4 * 1024 ** 2, remaining))
                            if not chunk:
                                raise ValueError('파일 전송이 끊겼습니다.')
                            handle.write(chunk)
                            remaining -= len(chunk)
                except Exception:
                    path.unlink(missing_ok=True)
                    raise
                def uploaded(progress):
                    try:
                        progress(10, '로컬 미리보기 준비 중')
                        return {'project': core.import_file(path, Path(filename).stem)}
                    finally:
                        path.unlink(missing_ok=True)
                self.json(start_job('import', uploaded), 202)
                return
            data = self.read_json()
            route = parsed.path
            if route == '/api/import':
                path = data.get('path', '')
                self.json(start_job('import', lambda progress: {'project': core.import_file(path)}), 202)
            elif route == '/api/demo':
                def demo(progress):
                    project = core.import_file(core.ROOT / 'demo.mp4', '편집 기능 테스트')
                    project['segments'] = core.parse_srt((core.ROOT / 'demo.srt').read_text(encoding='utf-8-sig'))
                    project['edit'].update(title='긴 영상에서\n한 장면을 꺼내세요', footer='로컬 쇼츠 스튜디오 · 기능 테스트')
                    core.save_project(project)
                    return {'project': project}
                self.json(start_job('import', demo), 202)
            elif route == '/api/youtube':
                url = str(data.get('url', ''))
                parsed_url = urlparse(url)
                if parsed_url.scheme != 'https' or parsed_url.hostname not in ('youtube.com', 'www.youtube.com', 'youtu.be'):
                    raise ValueError('https YouTube 영상 주소를 입력하세요.')
                def youtube(progress):
                    progress(5, 'YouTube 공개 영상 다운로드 중')
                    staging = core.DATA / 'incoming' / uuid.uuid4().hex
                    staging.mkdir(parents=True)
                    try:
                        core.run(['yt-dlp', '--no-playlist', '--max-filesize', '2G', '--socket-timeout', '30',
                                  '--retries', '2', '--no-overwrites', '-f', 'bv*[height<=1080]+ba/b[height<=1080]',
                                  '--merge-output-format', 'mp4', '-o', str(staging / 'source.%(ext)s'), url], timeout=1800)
                        file = next((p for p in staging.iterdir() if p.suffix in core.VIDEO_EXTENSIONS), None)
                        if not file:
                            raise ValueError('영상 다운로드에 실패했습니다. 로컬 파일로 불러오세요.')
                        progress(50, '로컬 미리보기 준비 중')
                        return {'project': core.import_file(file, 'YouTube 가져온 영상')}
                    finally:
                        shutil.rmtree(staging)
                self.json(start_job('import', youtube), 202)
            elif route in ('/api/save', '/api/srt', '/api/recommend', '/api/transcribe', '/api/render'):
                with LOCK:
                    project_id = data['id']
                    project = core.read_project(project_id)
                    if busy(project_id):
                        raise ValueError('이 프로젝트의 작업이 끝난 뒤 다시 시도하세요.')
                    if route == '/api/save':
                        project['edit'] = core.validate_edit(data['edit'], project['meta']['duration'])
                        if 'segments' in data:
                            project['segments'] = core.validate_segments(data['segments'], project['meta']['duration'])
                        core.save_project(project)
                        self.json(project)
                    elif route == '/api/srt':
                        project['segments'] = core.validate_segments(core.parse_srt(data['text']), project['meta']['duration'])
                        project['candidates'] = []
                        core.save_project(project)
                        self.json(project)
                    elif route == '/api/recommend':
                        project['candidates'] = core.recommend(project['segments'], project['meta']['duration'], data.get('target', 40))
                        core.save_project(project)
                        self.json(project)
                    elif route == '/api/transcribe':
                        def transcribe(progress):
                            project['segments'] = core.transcribe(project, data.get('model', 'small'), progress)
                            project['candidates'] = []
                            with LOCK:
                                core.save_project(project)
                            return {'project': project}
                        self.json(start_job('transcribe', transcribe, project_id), 202)
                    else:
                        def render(progress):
                            result = core.render(project, progress)
                            with LOCK:
                                project['exports'].insert(0, result)
                                core.save_project(project)
                            return {'project': project, 'export': result}
                        self.json(start_job('render', render, project_id), 202)
            else:
                raise ValueError('지원하지 않는 요청입니다.')
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except PermissionError as error:
            self.json({'error': str(error)}, 403)
        except Exception as error:
            self.json({'error': str(error)}, 400)


def main():
    global PORT
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8767)
    parser.add_argument('--data-dir', type=Path, default=core.DATA)
    args = parser.parse_args()
    PORT = args.port
    core.DATA = args.data_dir.resolve()
    core.DATA.mkdir(parents=True, exist_ok=True)
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        raise SystemExit('FFmpeg와 ffprobe가 PATH에 필요합니다.')
    print(f'Local Shorts Studio: http://127.0.0.1:{PORT}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()


if __name__ == '__main__':
    main()
