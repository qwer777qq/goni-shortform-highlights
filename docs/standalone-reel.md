# 고니 독립 영상 엔진

장면집 화면·웹 서버를 켤 필요 없이 원본 파일과 편집 JSON을 받아 MP4를 만듭니다. Codex·Claude는 MCP로 호출하거나 CLI 한 줄로 실행할 수 있습니다. 영상 처리는 같은 로컬 렌더러를 재사용하며, 다른 제작자의 비공개 코드나 프로젝트를 복원한 것은 아닙니다.

## 준비

Python 3.11 이상, FFmpeg/ffprobe가 필요합니다. API 키·로그인·유료 편집기는 필요하지 않습니다. 설치 파일을 받는 과정에는 인터넷이 필요하지만 설치 후 로컬 파일 렌더는 오프라인으로 가능합니다.

```powershell
git clone https://github.com/qwer777qq/goni-shortform-highlights.git
cd goni-shortform-highlights
python -m venv .venv-reel
.\.venv-reel\Scripts\python -m pip install -r local_studio/requirements-mcp.txt
```

## CLI: 한 번에 출력

실제 원본 길이에 맞는 `plan.json`을 준비합니다. [편집 JSON 형식](reel-studio.md#편집-json과-cli)을 참고하세요.

```powershell
.\.venv-reel\Scripts\python goni_reel.py --input "C:/Videos/source.mp4" --plan plan.json --output "C:/Videos/result-v1"
```

`--output`은 **새 폴더**여야 합니다. 기존 폴더는 덮어쓰지 않고 거절합니다. 출력 폴더 맨 위에 `reel.mp4`, `edit.json`, `poster.jpg`, `verification.json`, `commands.json`, `result.json`이 생깁니다. `projects/`에는 원본 복사·중간 파일·재현용 프로젝트가 남습니다. 실패하면 `failure.json`에 원인을 남기고 오류로 종료합니다.

## MCP: Codex·Claude에서 바로 호출

```powershell
$reelPython = (Resolve-Path '.venv-reel/Scripts/python.exe').Path
$reelMcp = (Resolve-Path 'local_studio/reel_mcp.py').Path
codex mcp add goni-reel -- $reelPython $reelMcp
claude mcp add --scope user --transport stdio goni-reel -- $reelPython $reelMcp
```

기존 등록에 `--port`가 있다면 HTTP 연결 방식입니다. 먼저 `codex mcp get goni-reel`, `claude mcp get goni-reel`로 확인하고 해당 등록만 제거한 뒤 위 명령으로 등록합니다. 다른 MCP 설정은 변경하지 않습니다.

```powershell
codex mcp remove goni-reel
claude mcp remove goni-reel -s user
# 이후 위 add 명령을 실행하세요.
```

새 채팅에서 도구를 불러오세요. `studio_status` 결과가 `mode: standalone`, `server_required: false`이면 독립 모드입니다. 별도로 서버를 띄우거나 브라우저를 열지 않습니다. 기본 자료 폴더는 사용자 홈의 `.goni-reel/projects`이며 `--data-dir`로 바꿀 수 있습니다. 기존 UI 자료와는 분리됩니다.

도구는 기존 8개와 같습니다. `import_video`와 `render_reel`은 작업 ID를 반환하므로 `job_status`가 `done` 또는 `error`가 될 때까지 확인합니다. 완료 파일은 디스크에 남지만 진행 중인 작업 상태는 MCP 프로세스 메모리에만 있습니다. 작업 중 강제 종료 시 자동 복구되지 않습니다. 완료 결과는 다음 세션의 `get_project`에서 찾을 수 있습니다. 동일한 자료 폴더·프로젝트를 여러 에이전트나 편집기에서 동시에 수정하지 마세요.

```text
goni-reel-studio 스킬로 장면집을 열지 말고 독립 엔진에서 작업해 줘.
원본: [내 영상 파일 경로]
참고: [스타일 참고 영상]
길이: 8~12초 / 비율: 16:9 / 소리: 원음 연속 유지
studio_status의 standalone 모드를 먼저 확인해라.
import_video로 가져온 뒤 실제 프레임을 보고 구간을 선정해라.
구간별 시작·끝·배속·명암·확대·반전 시간을 save_reel로 저장해라.
render_reel 후 job_status가 done인지 확인하고 MP4와 검증 JSON을 전달해라.
컷 경계와 첫·중간·끝 화면을 확인하고 확인하지 못한 음성 품질은 밝혀라.
기존 파일을 덮어쓰거나 외부에 게시하지 마라.
```

## 실제 지원 범위와 검증

여러 구간 연결, 구간별 고정 배속·명암·중앙 확대, 화면 전체 반전·플래시, 가로/세로 출력, 원음 처리를 지원합니다. 인물 분리·복제 합성, 자동 비트 싱크, 연속 속도 램프, 외부 BGM 혼합, 다중 원본·릴스 자막은 미구현입니다.

18개 회귀 검사와 실제 독립 MCP 렌더를 검증했습니다. MCP 검증에서는 Python의 네트워크 연결을 거절하는 래퍼를 사용했습니다. Windows asyncio의 내부 socketpair 생성만 예외이며 웹 서버에 접속하지 않습니다. 이는 Python 코드의 HTTP 의존성 검증이지 운영체제 전체 네트워크 차단 실험은 아닙니다. FFmpeg는 로컬 파일을 처리합니다.

```powershell
.\.venv-reel\Scripts\python scripts/reel_mcp_smoke.py --deny-network --video source.mp4 --plan plan.json --output mcp-proof.json
```

제공된 완성 릴스의 재편집 테스트는 약 7.69초, 1920×1080, H.264/AAC로 출력했습니다. 원래 들어 있던 신체 합성 효과까지 새로 재현한 결과는 아닙니다. 원본·시험 미디어와 개인 실행 기록은 GitHub에 올리지 않습니다.
