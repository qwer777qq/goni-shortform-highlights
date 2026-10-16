# REA 실행과 증거

출처 https://github.com/morluto/rea — MIT, Copyright 2026 morluto. 엔진은 번들하지 않는다. 아래는 2026-10-16 로컬에서 확인한 6.5.0 CLI 기준이다.

## JavaScript
```powershell
python scripts/rea_cli.py analyze-javascript-application "C:/analysis/public-scripts" --source-path app.js --max-semantic-nodes 12000 --max-semantic-nodes-per-file 6000 --format json
```
stdout 증거는 파일로, stderr 진행은 따로 보관한다. 결과는 수십 MB일 수 있으므로 전부 출력하지 않는다. normalized_result.statistics, source_selection, graph, semantic_graph.coverage, limitations를 필요한 범위만 요약한다. vendor 전체 분석 timeout이면 오류를 보관하고 범위를 좁힌다. 같은 대형 요청을 반복하지 않는다.

## 저장된 네트워크
```powershell
python scripts/rea_cli.py inspect-web-network-capture "C:/analysis/capture.har" har --format json
```
HAR 출처·수집 시각·본문/헤더 생략·타이밍 의미를 명시한다. 메타데이터로 가공한 HAR은 완전한 원시 캡처가 아니다. HTTP 200만으로 기능 전체나 다운로드 성공을 판단하지 않는다. recorded URL을 임의로 다시 요청하지 않는다.

## 연결 문제가 있을 때
공식 패키지가 없으면 `npx --yes rea-agents@6.5.0 --help`로 확보할 수 있다. npm 캐시 사용이며 MCP 등록은 아니다. MCP가 필요하면 `doctor --client codex --json`, 필요한 경우 `setup --client codex --dry-run --json`으로 변경 계획을 확인한다. 적용 후 재시작하고 실제 도구 노출을 확인한다. Claude는 지원 client ID를 help에서 확인한다. 브라우저 디버깅 차단·npm 부재·MCP 미등록·분석 엔진 부재의 해결책은 서로 다르다.

## EasyCut 조사에서 재사용할 기준
프로젝트/원본/초안/출력 버전을 분리한다. 원본 시각과 출력 시각을 구분하고 자막은 구간 교집합 후 배속 반영한다. 미리보기 변경·되돌리기와 서버 렌더는 다르다. 선택하지 않은 파일/동적 참조/서버 동작은 미확인이다. Windows에서 Linux 전용 source recovery 제공자를 쓸 수 있다고 가정하지 않는다.
