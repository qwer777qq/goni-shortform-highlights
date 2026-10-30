$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new()
$OutputEncoding = [Text.UTF8Encoding]::new()
try {
    $root = Split-Path -Parent $PSScriptRoot
    $python = Join-Path $env:LOCALAPPDATA 'Goni\erase-env\Scripts\python.exe'
    $engine = Join-Path $root 'erase_video.py'
    if (-not (Test-Path -LiteralPath $python)) { throw '먼저 영상정리-설치.bat을 실행하세요.' }
    if (-not (Test-Path -LiteralPath $engine)) { throw '고니 저장소 안의 실행기를 사용하세요.' }
    $source = (Read-Host '영상 링크 또는 파일 경로').Trim().Trim('"')
    if (-not $source) { Write-Host '취소했습니다.'; exit 0 }
    $erase = Read-Host '화면 글자·자막 지우기? 1=예, Enter=아니요'
    if ($erase -and $erase -ne '1') { throw '1 또는 Enter를 입력하세요.' }
    Write-Host '소리 선택: 1=원본 유지 / 2=전체 무음 / 3=목소리 지우기 / 4=배경음악 지우기'
    $choice = Read-Host '선택 (Enter=원본 유지)'
    $modes = @{''='keep'; '1'='keep'; '2'='mute'; '3'='remove_voice'; '4'='voice_only'}
    if (-not $modes.ContainsKey($choice)) { throw '1~4 또는 Enter를 입력하세요.' }
    $output = Join-Path ([Environment]::GetFolderPath('Desktop')) ('고니 영상정리 ' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0,6))
    $argsList = @($engine, '--input', $source, '--output', $output, '--audio', $modes[$choice])
    if ($erase -eq '1') { $argsList += '--auto-text' }
    Write-Host '처리 시작. 처음에는 모델을 다운로드하고, CPU에서는 시간이 오래 걸릴 수 있습니다.' -ForegroundColor Cyan
    & $python @argsList
    if ($LASTEXITCODE -ne 0) { throw "처리 실패. 확인할 폴더: $output" }
    Write-Host "완료: $output\cleaned.mp4" -ForegroundColor Green
    Write-Host '화면 글자와 음성 분리 결과를 직접 검수하세요.'
    Start-Process explorer.exe -ArgumentList @($output)
} catch { Write-Host "오류: $($_.Exception.Message)" -ForegroundColor Red; exit 1 }
