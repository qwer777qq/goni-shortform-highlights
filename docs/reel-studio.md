# 고니 릴스 스튜디오 · 실제 기능과 연결 방법

기본 자막 편집기는 유지하고 **릴스 다중 장면 편집**을 추가했습니다. 한 원본의 여러 구간을 연결하고 배속·중앙 확대·대비·밝기·채도·짧은 반전·플래시를 설정합니다. MCP는 FFmpeg 기반 로컬 렌더러에 연결합니다. After Effects/Blender 플러그인을 설치하거나 자동 제어하는 방식은 아닙니다.

**장면집을 켜지 않고 사용:** [독립 실행 안내](standalone-reel.md). MCP 기본값은 이제 서버가 필요 없는 독립 모드입니다. 아래 서버 실행은 화면을 사용하는 경우에만 필요합니다.

## 설치와 시작

Python 3.11 이상, FFmpeg와 ffprobe가 필요합니다. 영상 처리는 로컬에서 수행하며 API 키가 필요하지 않습니다.

```powershell
git clone https://github.com/qwer777qq/goni-shortform-highlights.git
cd goni-shortform-highlights
python -m venv .venv-reel
.\.venv-reel\Scripts\python -m pip install -r local_studio\requirements-mcp.txt
.\.venv-reel\Scripts\python local_studio\server.py --port 8769
```

`http://127.0.0.1:8769/reel`을 엽니다. 기본 서버 8767을 사용한다면 주소·MCP 설정의 포트도 8767로 맞추세요. 음성 인식은 별도 `requirements.txt`와 모델 설치가 필요하며 이 최소 설치에 포함되지 않습니다.

## 화면 사용법

1. **영상 가져오기**에서 파일을 고릅니다. 원본 복사와 미리보기를 준비합니다.
2. **장면 추가**로 행을 추가하고 원본 시작·끝 초를 입력합니다. ↑/↓로 순서를 바꿉니다.
3. 배속·확대·대비·밝기·채도를 입력합니다. 반전·플래시 칸은 `0:0.067`처럼 입력합니다. 여러 구간은 `0:0.067,0.3:0.367`처럼 쉼표로 나눕니다. 빈칸은 효과 없음입니다.
4. **화면 비율**과 **배치**를 선택합니다. 가운데 채움은 원본 가장자리를 자르므로 출력에서 확인하세요.
5. 음원은 장면별 원음, 연속 원본 음원, 음소거 중 선택합니다. 연속 음원은 시작점부터 편집 길이만큼 충분한 길이가 있어야 합니다.
6. **편집 저장** 후 **MP4 만들기**를 누릅니다. 진행률과 오류가 표시됩니다. 원본 미리보기에는 효과가 적용되지 않으며 **출력 재생**에서 확인합니다.
7. MP4·편집 JSON을 저장합니다. 프로젝트 폴더의 exports 안에 포스터·검증 JSON·재현 명령도 남습니다. 렌더마다 새 버전이 생성됩니다.

`4컷 반전 프리셋`은 영상을 균등하게 나누는 출발점입니다. AI가 맥락을 읽거나 음악 박자를 찾은 결과가 아닙니다.

## Codex·Claude Code MCP 연결

서버 없이 저장소 루트의 PowerShell에 입력합니다. 화면과 같은 프로젝트에 연결하려는 경우에만 마지막에 `--port 8769`를 추가합니다.

```powershell
$reelPython = (Resolve-Path '.venv-reel/Scripts/python.exe').Path
$reelMcp = (Resolve-Path 'local_studio/reel_mcp.py').Path
codex mcp add goni-reel -- $reelPython $reelMcp
claude mcp add --scope user --transport stdio goni-reel -- $reelPython $reelMcp
codex mcp get goni-reel
claude mcp get goni-reel
```

동일한 이름이 이미 있으면 기존 경로·포트를 먼저 확인하세요. 올바른 등록이면 다시 추가할 필요가 없습니다. Codex·Claude의 새 세션에서 도구를 로드합니다. `Connected` 또는 등록 상태와 **실제 도구 호출 성공은 구분**합니다.

| 도구 | 동작 |
|---|---|
| studio_status | 독립/HTTP 모드·FFmpeg 상태 |
| list_projects / get_project | 프로젝트 목록/설정/출력 조회 |
| import_video | 사용자가 지정한 로컬 영상 복사, 작업 ID 반환 |
| reel_preset | 균등 4컷 계획 반환 |
| save_reel | 입력 검증 후 편집 설정 저장 |
| render_reel | 비동기 렌더 작업 ID 반환 |
| job_status | queued/running/done/error 및 결과 조회 |

MCP는 stdio로 실행합니다. 기본 독립 모드는 렌더러를 직접 호출하며 HTTP 접속이 없습니다. 명시적으로 `--port`를 준 구형 연결만 로컬 127.0.0.1에 접속합니다. 공개 인터넷에 서버를 개방할 필요가 없습니다. 실제 MCP 왕복 검사는 `scripts/reel_mcp_smoke.py`로 수행할 수 있습니다.

## 편집 JSON과 CLI

아래는 길이 6초 이상 원본에 쓸 수 있는 예시입니다. 다른 영상에는 실제 길이에 맞춰 바꾸세요.

```json
{
  "ratio": "landscape",
  "layout": "fit",
  "audio": "source",
  "audio_start": 0,
  "clips": [
    {"start": 0, "end": 2, "speed": 1, "zoom": 1.03,
     "contrast": 1.05, "brightness": 0, "saturation": 0.95,
     "invert": [[0, 0.067]], "flash": []},
    {"start": 4, "end": 6, "speed": 1.2,
     "flash": [[0, 0.034]]}
  ]
}
```

- 시작/끝은 **원본 영상 시간**입니다. 위 예시는 0~2초 다음에 4~6초가 나옵니다.
- 효과 시간은 **각 장면의 배속 적용 후 출력 시간**입니다. `[0, 0.067)`이면 장면 처음 약 2~3프레임에 적용됩니다.
- 출력은 30fps로 양자화합니다. AAC 인코딩으로 컨테이너 길이가 계획과 수십 ms 다를 수 있습니다.
- 현재 확대는 중앙 고정 크롭입니다. 자동 피사체 추적이나 움직이는 줌 키프레임이 아닙니다.

```powershell
python local_studio/reel.py import "C:/Videos/my-video.mp4"
# 위 결과의 id를 아래 PROJECT_ID 자리에 넣으세요.
python local_studio/reel.py preset PROJECT_ID
python local_studio/reel.py render PROJECT_ID plan.json
```

## 복사 프롬프트

```text
goni-reel-studio 스킬을 적용해 내 원본으로 테스트 릴스를 만들어줘.
원본: [내 로컬 영상 경로]
참고: [스타일 참고 링크 또는 파일]
목표: 약 8~10초, 가로 16:9, 어두운 명암과 짧은 반전 효과.
참고 영상과 제작 원본을 구분하고 실제 화면에서 구간을 골라줘.
studio_status → import_video → 작업 완료 확인 → save_reel → render_reel → job_status 순서로 실제 MCP 도구를 써줘.
원음 또는 내가 제공한 음원을 유지하고 자동 비트 분석을 했다고 추정하지 마.
MP4, 편집 JSON, 컷별 타임라인과 검수 결과를 전달해줘.
인물 마스킹이나 복제 합성처럼 미지원 효과는 구현된 것으로 설명하지 마.
```

## 검증과 한계

`python -m unittest discover -s local_studio/tests -v`는 총 18개 검사를 실행합니다(기존 11개, 렌더 5개, 독립 작업 상태 2개). 새 검사는 잘못된 구간/숫자 거절, 배속 시간 계산, 재배열 후 실제 픽셀색, 반전 구간, 무음 입력, 세로 출력, 버전 보존을 확인합니다.

실제 제공된 릴스를 로컬에서 7구간으로 재편집해 약 7.69초 1920×1080 H.264/AAC 출력, 전체 디코드, 표본 프레임을 확인했습니다. 이 테스트는 이미 편집된 참고 영상을 입력으로 사용했으므로 원본에 있던 합성 효과가 포함됩니다. **새로 촬영한 독립 작품이나 원작 효과 전체의 재구현이 아닙니다.** 해당 미디어·음원·개인 경로는 공개 저장소에 포함하지 않습니다.

브라우저에서 장면 추가/삭제, 저장/재열기, 실제 MP4 만들기와 출력 로드를 확인했습니다. MCP stdio의 도구 목록·가져오기·저장·조회·렌더·작업 완료 응답도 확인했습니다. 자동 검사는 미적 품질이나 음악 박자의 정확도를 인증하지 않습니다.

아직 미지원: 인물 마스킹/팔·몸 복제 합성, 연속 속도 램프, 자동 비트 싱크, 외부 BGM 트랙 혼합, 다중 원본 파일, 릴스 모드 자막 합성, 자동 게시.
