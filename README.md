# energy-asset-agent

에너지·전력시장 전문성 자산화를 위한 자동화 파이프라인. Obsidian(로컬 markdown vault) + GitHub Actions 기반.

원본 스펙: 자동화 에이전트 설계 스펙 v3 (Obsidian 기준). v3에서 short-article
파이프라인(기사요약 + 사용자 의견 종합, 발행 전 게이트)이 추가됐다.

## 원칙

AI는 수집·분류·초안까지만 담당한다. "나의 판단"/"판단이 틀릴 조건"(지식카드), "나의 의견"/
"이 판단이 틀릴 조건"(short article)은 항상 사용자가 직접 작성하며, `src/card_draft.py`와
`src/short_article_draft.py`는 이 섹션들을 애초에 AI 프롬프트/응답 스키마에 포함하지 않고,
최종 마크다운 조립 시에도 코드가 직접 빈 헤더로 고정한다 (이중 방어).

## 구조

```
vault/
├── news-inbox/        # 뉴스 자동 수집함 (news_fetch → filter → summarize → md_writer)
├── knowledge-cards/    # 지식DB 카드 (card_draft.py 결과물)
├── short-articles/     # 기사요약+의견 종합 short article (short_article_draft.py 결과물)
├── analysis-memos/     # 화요일 분석메모 원본 (사용자 작성, memo_scaffold.py로 틀만 생성 가능)
├── weekly-digests/     # 주간 다이제스트 (weekly_digest.py 결과물)
├── flagship-reports/   # 분기 플래그십 보고서
├── templates/          # Obsidian 템플릿 (news-item.md, knowledge-card.md, short-article.md)
├── dashboards/         # Dataview 쿼리 모음 (queries.md)
└── .obsidian/          # Obsidian 설정

src/
├── news_fetch.py            # RSS 수집
├── google_news_fallback.py  # Reuters/Bloomberg 등 공식 RSS 없는 매체용 Google News 검색 RSS 우회 수집
├── news_filter.py            # 키워드 1차 필터 + 카테고리 부여
├── gemini_summarize.py       # Gemini API 요약/분류/관련도 점수
├── gemini_utils.py            # Gemini rate limit(429) 스로틀/재시도 공통 유틸
├── md_writer.py               # news-inbox에 frontmatter markdown 저장
├── weekly_digest.py            # 미검토 뉴스를 관련도순으로 정리한 주간 다이제스트 생성
├── run_weekly_digest.py         # 주간 다이제스트 진입점 (생성→커밋)
├── memo_scaffold.py             # 선택한 뉴스 항목으로 분석메모 틀 생성 (수동 CLI)
├── card_draft.py              # 분석메모 → 지식카드 초안 (판단 필드 코드 레벨 제외)
├── short_article_draft.py      # 뉴스 항목 → short article 초안 (의견 필드 코드 레벨 제외)
├── validate_short_articles.py  # 발행 게이트(opinion_ratio_check) 검증
├── git_commit.py              # 생성 파일 자동 커밋/푸시
└── run_daily_news.py          # 일일 파이프라인 진입점 (RSS+Google News→필터→요약→저장→커밋)

config/
├── rss_sources.yaml          # RSS 피드 목록 (실사용 전 URL 검증 필요)
├── google_news_sources.yaml  # Google News 검색 우회용 매체별 쿼리 (site: 연산자)
└── keywords.yaml             # 카테고리별 키워드
```

## 설치

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=...
```

무료 티어는 모델당 분당 요청 수(RPM)뿐 아니라 **일일 요청 수도 낮다**(예: `gemini-2.5-flash`
하루 20회). 뉴스 1건당 API 호출 1번으로는 하루치 뉴스도 처리할 수 없으므로,
`gemini_summarize.py`는 뉴스를 `GEMINI_BATCH_SIZE`개씩(기본 10건) 묶어 한 번의 호출로 처리한다.
`src/gemini_utils.py`는 호출 간 최소 간격을 두고(기본 분당 4회, `GEMINI_REQUESTS_PER_MINUTE`로 조정)
쿼터 초과(429) 시 자동 재시도한다 — 단, 분당 제한은 재시도로 극복 가능하지만 **일일 제한은
같은 실행 안에서 재시도로 해결되지 않으므로** 배치 크기를 필터 통과 건수에 맞게 조정하거나
유료 플랜으로 전환해야 한다.

## 로컬 실행

```bash
# 일일 뉴스 파이프라인 전체 실행 (수집 → 필터 → 요약 → 저장 → 커밋)
python src/run_daily_news.py

# 지식카드 초안 생성
python src/card_draft.py vault/analysis-memos/2026-07-22-메모.md \
  --title "지역별 전력가격제 도입" \
  --source-news "2026-07-21-전력시장개편안"

# 주간 다이제스트 수동 생성
python src/run_weekly_digest.py

# 분석메모 틀 생성 (news-inbox 파일명을 확장자 없이 지정)
python src/memo_scaffold.py "2026-07-21-전력시장-개편안-발표"

# short article 초안 생성
python src/short_article_draft.py "2026-07-21-전력시장-개편안-발표" \
  --title "지역별 전력가격제, 실제로 산업용 요금 차등까지 갈까" \
  --opinion-file vault/analysis-memos/2026-07-22-메모.md \
  --source-card "지역별-전력가격제-도입"

# 발행 게이트 검증 (published인데 게이트 미통과인 글이 있으면 실패)
python src/validate_short_articles.py
```

## 월요일/화요일 루틴 보조 (다이제스트·메모 스캐폴드)

"무엇을 고를지"와 "어떻게 분석할지"는 항상 사람이 직접 한다 — 이 두 스크립트는
그 앞뒤의 반복 작업(정렬/집계, 사실관계 옮겨 적기)만 자동화한다.

- **`weekly_digest.py`**: `news-inbox`에서 `status: unread`이고 최근 7일 이내인 뉴스를
  모아 카테고리별·관련도순으로 정리한 **HTML** 페이지를 `vault/weekly-digests/`에 생성한다
  (Obsidian 밖에서도 바로 읽기 편하도록 각 항목이 원문 `source_url`로 직접 연결되는
  클릭 가능한 링크). 순위·링크만 나열할 뿐 "이걸 고르세요" 같은 판단은 넣지 않는다.
  `run_weekly_digest.py`가 생성 후 자동 커밋까지 하며, `.github/workflows/weekly_digest.yml`이
  매주 금요일 07:00(KST)에 자동 실행한다.
  - **선별**: RSS+Google News 중복 수집으로 같은 제목의 기사가 여러 번 들어오는 경우가 많아
    제목 기준으로 중복을 제거하고, 관련도(`DIGEST_MIN_RELEVANCE`, 기본 4점 이상)로 걸러낸다.
    카테고리별로도 너무 길어지지 않도록 관련도 상위 `DIGEST_MAX_PER_CATEGORY`(기본 15건)만
    보여주고 나머지는 "N건 생략"으로 표시한다 — 어떤 개별 기사를 읽을지는 여전히 사람이
    고르지만, 리뷰할 가치가 있는 규모로 후보군만 추려준다.
- **`memo_scaffold.py`**: 다이제스트에서 고른 뉴스 파일명을 넣으면, 그 뉴스의 제목·요약·
  `[[백링크]]`가 미리 채워진 분석메모 틀을 `vault/analysis-memos/`에 만든다. "나의 분석"
  섹션은 항상 빈 채로 남으며, 새로운 분석을 생성하지 않고 이미 news-inbox에 있는 요약을
  그대로 옮겨 적을 뿐이다 — 화요일 메모 작성의 시작 마찰만 줄이는 용도다. 자동화 워크플로에는
  연결하지 않았다(어떤 뉴스로 메모를 쓸지는 사람이 결정해야 하므로 수동 CLI로만 제공).

## Short Article 파이프라인 (기사요약 + 의견 종합, 발행 전 게이트)

`vault/short-articles/`는 뉴스인박스 기사 하나를 골라 "요약(AI 초안) + 나의 의견 + 이
판단이 틀릴 조건"으로 구성된 짧은 글을 쓰기 위한 공간이다. 지식카드와 동일한 원칙 —
의견/판단은 항상 사람이 직접 쓴다 — 이 여기에도 그대로 적용된다.

- **`short_article_draft.py`**: 뉴스인박스 항목과 (선택) 사용자가 준비 중인 의견 메모를
  입력받아 "요약" 섹션만 생성한다. 의견 메모는 요약이 어떤 사실관계에 초점을 맞출지
  참고하는 용도로만 Gemini에게 전달될 뿐, 그 내용 자체는 결과물의 어디에도 들어가지
  않는다 — "나의 의견"/"이 판단이 틀릴 조건" 섹션은 응답 스키마에 존재하지 않고, 최종
  마크다운 조립 시 코드가 항상 빈 헤더로 고정한다(card_draft.py와 동일한 이중 방어 +
  헤더 누출 방지 정규식). 요약은 뉴스인박스의 기존 2줄 요약을 그대로 베끼지 않고 완전히
  재구성하도록 프롬프트에 명시한다.
- **발행 전 게이트**: `opinion_ratio_check`(기본 `false`) 필드가 있다. 아래 체크리스트를
  사람이 직접 확인한 뒤에만 `true`로 바꾸고, 그 다음에 `status`를 `published`로 바꿔야
  한다.
  - [ ] "나의 의견" 분량이 "요약" 분량보다 많거나 같은가
  - [ ] "이 판단이 틀릴 조건"이 최소 한 문장 이상 채워졌는가
  - [ ] 원문 문장을 그대로 옮긴 부분이 없는가 (사실관계는 반드시 재구성)
- **`validate_short_articles.py`**: `status: published`인데 `opinion_ratio_check: false`인
  글이 있으면 실패 처리한다. 현재는 체크리스트 자체가 수동 확인이라 완전한 실시간 차단은
  아니지만, `.github/workflows/validate_short_articles.yml`이 `vault/short-articles/`
  변경 시 자동 실행되어 게이트를 건너뛴 발행을 커밋 이후에라도 잡아낸다. (의견/요약
  비율의 AI 자동 판정은 아직 없음 — 스펙 문서의 다음 단계 항목.)
- 지식카드와의 연결: `source_card` 필드에 관련 지식카드를 `[[백링크]]`로 남길 수 있다.
  분기말에는 `vault/dashboards/queries.md`의 "승격 후보" 쿼리로 `published`인데
  `source_card`가 비어 있는 글(아직 지식카드로 안 이어진 것)을 찾아 플래그십 보고서
  승격을 검토한다.

## Google News 우회 수집 (Reuters/Bloomberg)

Reuters(2020년경 공개 RSS 종료)와 Bloomberg(애초에 공개 RSS 없음)는 `news_fetch.py`의
일반 RSS 방식으로 수집할 수 없다. `src/google_news_fallback.py`가 Google News 검색
RSS(`news.google.com/rss/search`)를 `site:` 연산자와 함께 사용해 간접 수집하며,
`run_daily_news.py`에서 RSS 결과와 합쳐진 뒤 동일한 필터/요약 파이프라인을 탄다.
대상 매체·검색어는 `config/google_news_sources.yaml`에서 관리한다.

**반드시 인지할 리스크** (`google_news_fallback.py` 상단 docstring 참고):
- 비공식 우회이며 Google이 URL 패턴/정책을 바꾸면 언제든 깨질 수 있다. 프로덕션에 넣기 전
  로컬에서 `curl -sI "https://news.google.com/rss/search?q=site:reuters.com+energy&hl=en-US&gl=US&ceid=US:en"`로
  재확인할 것.
- Google News RSS의 `<link>`는 대부분 Google 리다이렉트 URL이라 `resolve_original_url()`이
  best-effort로 실제 매체 원문 URL을 따라가지만, 항상 성공하지는 않는다.
- **저작권**: 제목·요약·링크만 수집하는 용도로 제한한다. 본문은 절대 스크래핑하지 않으며,
  카드/콘텐츠 작성 시에도 반드시 자기 언어로 paraphrase해야 한다.
- 이 우회가 불안정해지면 Reuters Connect, Bloomberg API 같은 공식 유료 구독 전환을 검토한다.
- 워크플로에서 Google News 수집이 실패해도(`run_daily_news.collect_entries()`가 예외를 흡수)
  RSS 수집 결과는 그대로 유지되고 파이프라인이 죽지 않는다.

## GitHub Actions

`.github/workflows/daily_news.yml`이 매일 07:00(KST)에 뉴스 파이프라인을 실행하고
결과를 자동 커밋/푸시한다. `.github/workflows/weekly_digest.yml`이 매주 금요일
07:00(KST)에 주간 다이제스트를 생성한다. `.github/workflows/validate_short_articles.yml`은
`vault/short-articles/` 변경이 `main`에 push되거나 PR에 포함될 때마다 발행 게이트를
검증한다(API 호출이 없어 `PyYAML`만 설치, 가장 가벼움). 저장소 Settings → Secrets에
`GEMINI_API_KEY`를 등록해야 한다(다이제스트·게이트 검증은 API 호출이 없어 필요 없음).
수동 실행은 Actions 탭에서 `workflow_dispatch`로 가능하다.

`schedule` 트리거(daily_news, weekly_digest)는 **`main` 브랜치에 있는 워크플로 파일
기준으로만 동작**한다 — feature 브랜치에만 있는 상태에서는 자동 실행되지 않으니, 반드시
`main`에 머지된 뒤 예정된 시각을 기다리거나 `workflow_dispatch`로 수동 확인할 것.

## Obsidian 연결

1. Obsidian에서 `vault/` 폴더를 vault로 열기
2. 설정 → 커뮤니티 플러그인에서 **Dataview** 설치 및 활성화
3. `vault/dashboards/queries.md`에서 재검토 대상 / 참조횟수 상위 카드 / 발행 게이트
   미통과 draft / 지식카드 승격 후보를 바로 확인
4. (선택) Obsidian Git 플러그인으로 자동 pull/push 설정 시 멀티기기 동기화 가능

카드 간 `[[백링크]]`가 곧 재사용률(질 지표)이므로 별도 트래킹 스크립트가 필요 없다 —
`vault/dashboards/queries.md`의 세 번째 쿼리가 이를 자동으로 보여준다.

## 다음 단계

- [ ] `config/rss_sources.yaml`의 URL을 실제 서비스로 검증
- [ ] `GEMINI_API_KEY`를 저장소 Secrets에 등록 후 워크플로 첫 실행 확인
- [ ] 뉴스 파이프라인 안정화 후 카드 초안 자동화(2단계) 운영 반영
- [ ] short article 발행 전 게이트는 현재 사람이 체크리스트를 보고 `opinion_ratio_check`를
      수동으로 바꾸는 방식 — 안정화되면 Gemini로 "의견/요약 비율" 자동 판정을 추가하는 것도
      고려 (스펙 v3 다음 단계 항목)
