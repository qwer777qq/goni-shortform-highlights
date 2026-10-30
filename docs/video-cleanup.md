# 고니 영상 정리: 자막·목소리·배경음악

링크 또는 영상 파일을 넣고 옵션을 선택합니다. `launcher/영상정리-시작.bat`은 숏츠 편집 없이 원본을 정리하며, 기존 `start-goni.bat`은 정리 후 Claude 숏츠 작업을 시작합니다. 원본은 덮어쓰지 않고 바탕화면에 새 결과 폴더를 만듭니다.

## 처음 한 번 설치

1. Windows에서 Git, FFmpeg(`ffmpeg`, `ffprobe`), `yt-dlp`, Python 도구 [uv](https://docs.astral.sh/uv/getting-started/installation/)를 설치하고 터미널을 새로 엽니다.
2. 저장소 전체를 받습니다. `git clone https://github.com/qwer777qq/goni-shortform-highlights.git`
3. 저장소의 `launcher/영상정리-설치.bat`을 더블클릭합니다. Python 3.10 환경, CPU용 PyTorch, Demucs, EasyOCR과 OpenCV를 설치합니다. 첫 처리 때 모델 데이터도 인터넷으로 내려받습니다. 충분한 저장 공간과 시간이 필요합니다.
4. 다음부터 `launcher/영상정리-시작.bat`을 더블클릭합니다.

## 영상 한 편 처리

1. 영상 링크 또는 내 컴퓨터 영상 파일 경로를 붙여넣고 Enter를 누릅니다. URL의 재생목록 전체가 아닌 영상 하나를 가져옵니다. 접근 가능한 영상이어야 합니다.
2. 글자 지우기를 원하면 `1`, 그대로 두려면 Enter를 누릅니다.
3. 소리를 선택합니다: `1` 원본 유지, `2` 전체 무음, `3` 목소리 제거 시도, `4` 배경음악 제거 시도(목소리만 남기기). 둘 다 지우려면 `2`를 선택하세요.
4. 완료 메시지의 `cleaned.mp4`를 재생해 화면, 음성, 길이와 싱크를 확인합니다. 문제 시 원본은 유지되므로 다시 시도할 수 있습니다.

자막 옵션은 EasyOCR로 매 프레임의 한글·영어 글자를 찾아 OpenCV 공간 보간으로 가립니다. 자동 감지는 다른 화면 글자도 지울 수 있고, 작은 글자·흔들리는 자막은 놓칠 수 있습니다. 복잡한 배경, 사람 얼굴과 겹치거나 움직이는 자막에서는 흔적과 흔들림이 남을 수 있습니다. 영상 타임스탬프를 고정 프레임으로 다시 만들기 때문에 가변 프레임 원본은 길이와 싱크를 반드시 검수해야 합니다. 원본 화면을 완벽하게 복원하는 AI 영상 인페인팅이 아닙니다.

목소리·반주는 [Demucs](https://github.com/facebookresearch/demucs)의 보컬 분리를 사용합니다. 노래 중심 모델이어서 말소리, 효과음, 겹치는 음성이 정확히 분리되지 않을 수 있습니다. 첫 실행은 모델 다운로드가 필요하고 CPU에서는 오래 걸립니다. MP4에 별도 자막 트랙이 있다면 출력에서 제외합니다. API 키나 VMake는 사용하지 않습니다.

## Claude Code 또는 Codex에게 한 번에 요청

```text
고니 영상 정리 기능을 사용해 주세요.
원본: [영상 링크 또는 내 파일 경로]
글자·자막 지우기: [예 또는 아니요]
소리: [원본 유지 / 전체 무음 / 목소리 지우기 / 배경음악 지우기]

goni-reel MCP의 clean_source_video로 처리하거나 저장소의 erase_video.py를 실행하세요. 출력은 새 폴더에 저장하고 원본을 보존하세요. 결과 영상을 재생할 수 있는지, 길이·오디오·화면과 자막 지우기 품질을 확인하세요. 확인하지 못한 부분은 사실대로 알려주세요. 외부 게시하지 마세요.
```

MCP는 `clean_source_video(source, output_dir, region=null, audio='keep', auto_text=false)`를 제공합니다. `audio`는 `keep`, `mute`, `remove_voice`, `voice_only`입니다. MCP 프로세스를 재시작해야 새 도구가 보입니다. 모델 환경은 기본 `%LOCALAPPDATA%/Goni/erase-env`에서 찾으며, 별도 환경을 쓰려면 `GONI_ERASE_PYTHON`과 `GONI_DEMUCS_PYTHON`에 해당 Python 경로를 지정합니다. CLI 예시는 다음과 같습니다.

```powershell
& "$env:LOCALAPPDATA\Goni\erase-env\Scripts\python.exe" erase_video.py --input "C:\Videos\source.mp4" --output "C:\Videos\cleaned-new" --auto-text --audio remove_voice
```

## 테스트 범위

단색 배경에 한글·영문 글자가 있는 합성 영상에서 각각 자동 감지·제거를 검증했고, 기존 유튜브 쇼츠 링크에서 다운로드 후 무음 출력을 확인했습니다. Demucs는 합성 음원의 보컬 분리 두 모드 실행과 출력 파일을 확인했습니다. 실제 한국어 대화·배경음악 분리 품질, 다양한 영상의 자동 글자 제거 품질, 다른 링크별 다운로드와 가변 프레임 싱크는 보장하거나 전부 검증한 상태가 아닙니다.
