# 대시보드 쿼리

Obsidian에서 Dataview 플러그인을 설치한 뒤 이 노트를 열면 아래 쿼리가 바로 실행됩니다.

## 재검토일 도래 카드

```dataview
TABLE review_date, status
FROM "knowledge-cards"
WHERE date(review_date) <= date(today) AND status = "confirmed"
SORT review_date ASC
```

## 이번 달 확정 카드 중 판단 미기입 확인 (품질 체크)

```dataview
LIST
FROM "knowledge-cards"
WHERE status = "confirmed" AND !contains(file.content, "## 나의 판단")
```

## 재사용률(백링크 수 기준) 상위 카드

```dataview
TABLE length(file.inlinks) as "참조횟수"
FROM "knowledge-cards"
SORT length(file.inlinks) DESC
```

세 번째 쿼리가 카드의 재사용률(질 지표)을 별도 스크립트 없이 자동으로 보여줍니다.
