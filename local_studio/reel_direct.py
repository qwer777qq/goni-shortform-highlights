"""Headless local engine. No HTTP server, browser or account is used."""
from concurrent.futures import ThreadPoolExecutor
import copy
from pathlib import Path
import shutil
import threading
import uuid

import core
import reel


DEFAULT_DATA = Path.home() / '.goni-reel' / 'projects'


class Engine:
    def __init__(self, data_dir=None):
        # One Engine per process: the shared renderer has a process-wide data root.
        core.DATA = Path(data_dir or DEFAULT_DATA).expanduser().resolve()
        core.DATA.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.jobs = {}
        self.pool = ThreadPoolExecutor(max_workers=1)

    def status(self):
        return dict(mode='standalone', server_required=False, browser_required=False,
                    ffmpeg=bool(shutil.which('ffmpeg')), ffprobe=bool(shutil.which('ffprobe')),
                    data_dir=str(core.DATA), jobs_persisted=False)

    def list_projects(self):
        return {'projects': [core.read_project(p.parent.name) for p in
                             sorted(core.DATA.glob('*/project.json'),
                                    key=lambda p: p.stat().st_mtime, reverse=True)]}

    def busy(self, project_id):
        return any(j['project_id'] == project_id and j['status'] in ('queued', 'running')
                   for j in self.jobs.values())

    def start(self, kind, work, project_id=None):
        with self.lock:
            if project_id and self.busy(project_id):
                raise ValueError('이 프로젝트의 작업이 진행 중입니다.')
            job_id = uuid.uuid4().hex
            job = dict(id=job_id, kind=kind, project_id=project_id, status='queued',
                       progress=0, message='작업 대기 중')
            self.jobs[job_id] = job

            def update(progress, message):
                with self.lock:
                    job.update(progress=round(progress), message=message)

            def task():
                with self.lock:
                    job['status'] = 'running'
                try:
                    result = work(update)
                    with self.lock:
                        job.update(status='done', progress=100, message='완료', result=result)
                except Exception as error:
                    with self.lock:
                        job.update(status='error', message=str(error))

            self.pool.submit(task)
            return copy.deepcopy(job)

    def import_video(self, path):
        return self.start('import', lambda progress: {'project': core.import_file(path, preview=False)})

    def save(self, project_id, plan):
        with self.lock:
            if self.busy(project_id):
                raise ValueError('렌더 중에는 편집 설정을 변경할 수 없습니다.')
            return reel.save(project_id, plan)

    def render(self, project_id):
        with self.lock:
            # Snapshot the validated plan before queueing; later edits cannot change it.
            project = core.read_project(project_id)
            plan = reel.validate(project.get('reel', {}), project['meta']['duration'])
            return self.start('render', lambda progress: reel.render(project_id, plan, progress), project_id)

    def job_status(self, job_id):
        with self.lock:
            if job_id not in self.jobs:
                raise ValueError('이 MCP 세션의 작업 ID가 아닙니다. 완료 출력은 get_project로 확인하세요.')
            return copy.deepcopy(self.jobs[job_id])

    def close(self):
        self.pool.shutdown(wait=True)
