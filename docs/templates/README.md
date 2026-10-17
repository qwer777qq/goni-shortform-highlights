# 고니 로컬 숏폼 템플릿

2026-10-17 EasyCut [공개 템플릿 목록](https://www.easycut.co.kr/templates)에서 확인한 7종을 참고하여 로컬 편집기용으로 독립 구현했습니다. 기존 4종을 보존해 선택 항목은 총 11종입니다.

로그인 후 생성·편집·재렌더링·개별 미디어 다운로드까지 추가 확인한 내용은 [고니 기능 분석](goni-feature-analysis.md)과 [실제 출력 검증](goni-runtime-verification.json)에 정리했습니다. 생성 화면의 SNS·커뮤니티 beta는 관찰 항목이며 로컬 구현 수에 추가하지 않습니다. 유료 기능과 서버 AI는 미확인 범위를 별도로 표시합니다.

![7종 출력 미리보기](previews/all-templates.jpg)

| 종류 | ID | 구현 | 미리보기 |
|---|---|---|---|
| 자막 팝형 | `subtitle-pop` | 어절 하나씩 확대 애니메이션 | [이미지](previews/subtitle-pop.jpg) · [MP4](previews/subtitle-pop.mp4) |
| 자막 강조형 | `subtitle-highlight` | 현재 어절을 민트색으로 강조 | [이미지](previews/subtitle-highlight.jpg) · [MP4](previews/subtitle-highlight.mp4) |
| 댓글 카드형 | `comment-capture` | 직접 입력한 질문·문구를 흰 카드에 표시 | [이미지](previews/comment-capture.jpg) · [MP4](previews/comment-capture.mp4) |
| 다크 레드 | `dark-red` | 검정 바탕과 붉은 제목·선 | [이미지](previews/dark-red.jpg) · [MP4](previews/dark-red.mp4) |
| 화이트 옐로 | `white-yellow` | 밝은 바탕과 노란 제목 카드 | [이미지](previews/white-yellow.jpg) · [MP4](previews/white-yellow.mp4) |
| 다크 미니멀 | `dark-minimal` | 검정 바탕과 흰 제목 | [이미지](previews/dark-minimal.jpg) · [MP4](previews/dark-minimal.mp4) |
| 페이퍼 | `paper-story` | 종이색 바탕과 갈색 제목·구분선 | [이미지](previews/paper-story.jpg) · [MP4](previews/paper-story.mp4) |

## 적용 순서

1. `local_studio/start.cmd` 실행 후 로컬 앱에서 영상을 불러옵니다.
2. 자막을 생성하거나 SRT를 가져오고 시작·끝 구간을 선택합니다.
3. 템플릿 목록에서 종류를 선택하고 제목·하단 문구를 입력합니다.
4. 댓글 카드형은 추가 입력란에 최대 80자의 문구를 직접 작성합니다.
5. 저장 후 MP4로 출력하고 출력 영상을 재생해 확인합니다.

제목은 최대 56자, 직접 줄바꿈 1회, 최대 두 줄로 크기를 줄여 상단 영역에 맞춥니다. 9:16 영상에서의 배치이며 다른 비율로 잘라 게시할 때까지 보장하는 규칙은 아닙니다.

## 확인 범위와 한계

- 공개 목록의 자막 팝형·자막 강조형·댓글 캡처·다크 레드·화이트 옐로·다크 미니멀·페이퍼 7종을 확인했습니다. 상세 설정 링크는 로그인이 필요하므로 내부 수치나 개인·유료 템플릿 전체를 확인했다고 주장하지 않습니다.
- 이름과 사용자 경험을 참고한 독립 구현입니다. EasyCut 원본 HTML/CSS/JavaScript 번들, 로고, 예시 영상 및 비공개 데이터를 이 패키지에 포함하지 않습니다.
- 자막 팝형·강조형의 어절 시각은 자막 구간을 어절 수로 균등 배분한 추정값입니다. 실제 발음에 맞춘 단어 정렬이나 서버 AI 복제 기능은 아닙니다.
- 댓글 카드형은 실제 댓글 수집·후기 생성 기능이 아닙니다. 직접 입력한 문구임을 카드에 표시하며 작성자·좋아요 수를 만들지 않습니다.
- 모든 예제 영상은 이 프로젝트에서 만든 합성 테스트 화면과 작은 신호음입니다. 사용자 강의·클론 음성·상품 자료는 포함하지 않습니다.
- Python 렌더와 브라우저 Canvas의 글꼴 표현에는 차이가 있을 수 있습니다. 최종 출력 영상을 기준으로 검수하세요.

## 검증

```powershell
python -m unittest discover -s local_studio/tests -v
python local_studio/smoke_test.py
python local_studio/template_smoke.py
node --check local_studio/static/app.js
```

7종 각각 1080×1920 MP4 출력 후 FFmpeg 전체 디코드를 검사합니다. 종류별 SHA-256과 출력 정보는 [검증 기록](verification.json)에 있습니다.

메타데이터: [템플릿 카탈로그](../../local_studio/template_catalog.json). 동일 카탈로그를 서버·렌더·브라우저에서 사용합니다.

## 텍스트와 설정 목록

- [공개 템플릿 이름·분류·설명 요약·버튼 목록](public-text-inventory.json)
- [로컬 편집기 전체 화면 문구·입력란·11종 설정](local-editor-texts.json)

공개 화면의 설명은 고니용으로 요약했으며 원본 설명과 동일한 문구라고 표시하지 않습니다. 원본 화면과 비교할 때는 위 출처를 사용하세요. 로그인된 개인 템플릿·상세 편집 문구·AI 내부 프롬프트는 아직 확인하지 못했습니다.

이미 로컬 서버가 실행 중이면 종료 후 다시 실행하고 브라우저를 새로고침해야 신규 카탈로그가 반영됩니다.
