$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new()
try {
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw 'uv가 필요합니다. https://docs.astral.sh/uv/getting-started/installation/ 에서 설치하세요.' }
    foreach ($tool in @('ffmpeg','ffprobe','yt-dlp')) {
        if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "$tool 이 필요합니다. 설치 안내를 참고하세요." }
    }
    $venv = Join-Path $env:LOCALAPPDATA 'Goni\erase-env'
    $python = Join-Path $venv 'Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        & uv venv --python 3.10 $venv
        if ($LASTEXITCODE -ne 0) { throw 'Python 환경 생성 실패' }
    }
    & uv pip install --python $python torch==2.2.2 torchaudio==2.2.2 torchvision==0.17.2 --index-url https://download.pytorch.org/whl/cpu
    if ($LASTEXITCODE -ne 0) { throw 'PyTorch 설치 실패' }
    & uv pip install --python $python 'numpy<2' demucs==4.1.0 easyocr==1.7.2
    if ($LASTEXITCODE -ne 0) { throw '영상 정리 도구 설치 실패' }
    & $python -c 'import cv2, easyocr, demucs; print("영상 정리 도구 확인 완료")'
    if ($LASTEXITCODE -ne 0) { throw '설치 확인 실패' }
    Write-Host '설치 완료! 영상정리-시작.bat을 더블클릭하세요. 모델은 첫 사용 시 다운로드됩니다.' -ForegroundColor Green
} catch { Write-Host "설치 오류: $($_.Exception.Message)" -ForegroundColor Red; exit 1 }
