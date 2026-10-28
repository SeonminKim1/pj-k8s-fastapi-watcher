# 이슈 트래커 연동: GitHub Project (`gh` CLI)

`sdd-process.md`의 "이슈 트래커 연동"을 GitHub Project로 할 때의 명령이다. `CLAUDE.md`의 "GitHub Project" 항목(owner, Project 번호)이 채워져 있을 때만 쓴다. 다른 트래커를 쓰게 되면 같은 시점(이슈 생성·상태 변경·PR)을 담은 파일을 이 폴더에 따로 둔다.

## 준비 (최초 1회, 사용자가 실행)
- `gh` 설치 후 `gh auth login`, `gh auth refresh -s project` (Projects는 `project` 스코프가 필요)
- 저장소에 GitHub remote가 연결돼 있어야 한다.
- Project에 `Status` 필드(`Todo` / `In Progress` / `Done`)가 있어야 한다(GitHub 기본 템플릿).

## ID 조회 (`/feat` 실행 중 처음 필요할 때 한 번, `<owner>`·`<number>`는 `CLAUDE.md` 값)
```bash
gh project view <number> --owner <owner> --format json --jq '{id, title}'   # Project ID(PVT_...), 제목
gh project field-list <number> --owner <owner> --format json \
  --jq '.fields[] | select(.name=="Status") | {id, options}'                 # Status 필드 ID와 옵션 ID
```

## TASK: 이슈 생성 (사용자가 작업 계획을 확인한 뒤, 이슈가 없는 작업만)
```bash
gh issue create --title "T1 [<feature-name>] <작업 내용>" --assignee @me \
  --body "선행: <없음|#번호>"$'\n\n'"문서: docs/<feature-name>/task.md"   # 출력: 이슈 URL
gh project item-add <number> --owner <owner> --url <이슈 URL> --format json --jq .id   # 아이템 ID
```
- 담당자는 `--assignee @me`(`gh`에 로그인한 사용자 본인).
- 생성 후 Status를 `Todo`로 둔다(아래 상태 변경 명령).
- 아이템 ID는 저장하지 않는다. 필요할 때 `item-add`를 다시 실행하면 기존 아이템 ID가 그대로 반환된다.

## IMPLEMENT: 상태 변경
```bash
gh project item-edit --id <아이템 ID> --project-id <Project ID> \
  --field-id <Status 필드 ID> --single-select-option-id <옵션 ID>
gh issue close <이슈 번호> --comment "<바뀐 파일, 테스트 결과 한 줄>"
```
- `gh issue close`가 `Could not close the issue`를 내도 실제로는 닫혀 있을 수 있다. `gh issue view <번호> --json state`로 확인하고 판단한다.

## IMPLEMENT 완료: PR 생성
```bash
git push -u origin feature/<feature-name>
gh pr create --base main --head feature/<feature-name> \
  --title "<feature-name>: <한 줄 요약>" --body-file <본문 파일> \
  --assignee @me --project "<Project 제목>"
```
- 본문은 아래 템플릿을 따른다. 한 줄에 내용을 몰아 쓰지 않는다: 작업은 한 줄에 하나씩, 긴 설명은 쉼표로 잇지 말고 하위 항목으로 나눈다.

````markdown
## 요약

<무엇을 추가·변경했는지 1~2줄>
<operator 패턴 등 전체 구조에서의 위치 1줄>

- 문서: `docs/<feature-name>/` (PRD · SPEC · PLAN · TASK · IMPLEMENT)

## 작업

- [x] #<이슈> T1 <작업 요약>
- [x] #<이슈> T2 <작업 요약>

## 주요 변경

### <영역> — `<경로>`
- <항목 하나에 한 가지>
  - <세부 규칙은 하위 항목>

## 확인

- `uv run ruff check .` 통과
- `uv run pytest` <N> passed
- <직접 확인한 것>
- `/code-review` 지적 <N>건 반영

🤖 Generated with [Claude Code](https://claude.com/claude-code)
````
- 이미 닫힌 이슈도 작업 목록에 `#번호`로 참조만 한다(`Closes #` 불필요).
- PR은 `--project`로 직접 Project에 추가한다(Project 설정의 "Auto-add to project" 워크플로가 켜져 있지 않으면 자동으로 붙지 않는다).
- 머지는 사용자가 한다. 작업별 커밋을 보존하도록 일반 머지(`gh pr merge <번호> --merge --delete-branch`)를 안내한다(squash 금지).
