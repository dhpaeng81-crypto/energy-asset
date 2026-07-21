# energy-asset-agent

에너지·전력시장 전문성 자산화를 위한 자동화 파이프라인. Obsidian(로컬 markdown vault) + GitHub Actions 기반.

원본 스펙: 자동화 에이전트 설계 스펙 v2 (Obsidian 기준).

## 원칙

AI는 수집·분류·초안까지만 담당한다. "나의 판단"과 "판단이 틀릴 조건"은 항상 사용자가 직접 작성하며,
`src/card_draft.py`는 이 두 섹션을 애초에 AI 프롬프트/응답 스키마에 포함하지 않고, 최종 마크다운
조립 시에도 코드가 직접 빈 헤더로 고정한다 (이중 방어).

## 구조

```
vault/
├── news-inbox/        # 뉴스 자동 수집함 (news_fetch → filter → summarize → md_writer)
├── knowledge-cards/    # 지식DB 카드 (card_draft.py 결과물)
├── analysis-memos/     # 화요일 분석메모 원본 (사용자 작성)
├── flagship-reports/   # 분기 플래그십 보고서
├── templates/          # Obsidian 템플릿 (news-item.md, knowledge-card.md)
├── dashboards/         # Dataview 쿼리 모음 (queries.md)
└── .obsidian/          # Obsidian 설정

src/
├── news_fetch.py        # RSS 수집
├── news_filter.py        # 키워드 1차 필터 + 카테고리 부여
├── gemini_summarize.py   # Gemini API 요약/분류/관련도 점수
├── md_writer.py           # news-inbox에 frontmatter markdown 저장
├── card_draft.py          # 분석메모 → 지식카드 초안 (판단 필드 코드 레벨 제외)
├── git_commit.py          # 생성 파일 자동 커밋/푸시
└── run_daily_news.py      # 일일 파이프라인 진입점 (fetch→filter→summarize→write→commit)

config/
├── rss_sources.yaml   # RSS 피드 목록 (실사용 전 URL 검증 필요)
└── keywords.yaml      # 카테고리별 키워드
```

## 설치

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=...
```

## 로컬 실행

```bash
# 일일 뉴스 파이프라인 전체 실행 (수집 → 필터 → 요약 → 저장 → 커밋)
python src/run_daily_news.py

# 지식카드 초안 생성
python src/card_draft.py vault/analysis-memos/2026-07-22-메모.md \
  --title "지역별 전력가격제 도입" \
  --source-news "2026-07-21-전력시장개편안"
```

## GitHub Actions

`.github/workflows/daily_news.yml`이 매일 07:00(KST)에 뉴스 파이프라인을 실행하고
결과를 자동 커밋/푸시한다. 저장소 Settings → Secrets에 `GEMINI_API_KEY`를 등록해야 한다.
수동 실행은 Actions 탭에서 `workflow_dispatch`로 가능하다.

## Obsidian 연결

1. Obsidian에서 `vault/` 폴더를 vault로 열기
2. 설정 → 커뮤니티 플러그인에서 **Dataview** 설치 및 활성화
3. `vault/dashboards/queries.md`에서 재검토 대상 / 참조횟수 상위 카드를 바로 확인
4. (선택) Obsidian Git 플러그인으로 자동 pull/push 설정 시 멀티기기 동기화 가능

카드 간 `[[백링크]]`가 곧 재사용률(질 지표)이므로 별도 트래킹 스크립트가 필요 없다 —
`vault/dashboards/queries.md`의 세 번째 쿼리가 이를 자동으로 보여준다.

## 다음 단계

- [ ] `config/rss_sources.yaml`의 URL을 실제 서비스로 검증
- [ ] `GEMINI_API_KEY`를 저장소 Secrets에 등록 후 워크플로 첫 실행 확인
- [ ] 뉴스 파이프라인 안정화 후 카드 초안 자동화(2단계) 운영 반영
