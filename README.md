# 🐾 Pet_Care 팀 GitHub 협업 가이드

우리 팀은 안정적인 코드 관리와 원활한 협업을 위해 **Git 브랜치 전략 및 Pull Request(PR) 기반의 협업 프로세스**를 엄수합니다. Git이 처음이더라도 아래 가이드를 차근차근 따라와 주세요.

---

## 📌 1. 핵심 원칙 (Ground Rules)

1. **`master` 브랜치는 팀의 공식 최신본**입니다. 절대 `master` 브랜치에서 직접 코드를 수정하거나 직접 `push`하지 않습니다.


2. 모든 작업은 반드시 개별 **`feature` 브랜치**에서 진행합니다.


3. 작업 완료 후 Pull Request(PR)를 생성하고, **다른 팀원의 검토(Review)와 승인(Approve)을 거친 뒤 Merge**합니다.



---

## 🚀 2. 전체 협업 흐름 (Workflow)

```text
[master 최신화] ➔ [feature 브랜치 생성] ➔ [코드 작업 및 테스트] 
      ➔ [add & commit] ➔ [push] ➔ [PR 생성] ➔ [팀원 검토 및 Approve] ➔ [Merge]

```

* **작업자**: 최신 `master` Pull ➔ 기능별 `feature` 브랜치 생성 ➔ 코드 작성 ➔ Commit & Push ➔ PR 생성


* **승인자**: PR 방향 및 변경 파일(Files changed) 검토 ➔ 이상 없으면 Approve 및 Merge



---

## 💻 3. 작업자 가이드 (Step-by-Step)

VS Code에서 프로젝트 폴더를 연 뒤, 터미널(PowerShell)을 켜고 **한 줄씩 정확하게** 입력합니다.

### ① 작업 시작 전 (최신 master 준비)

```powershell
# 1. 현재 상태 및 브랜치 확인 (*표시가 master에 있어야 함)
git status
git branch

# 2. master 브랜치로 이동
git switch master

# 3. 팀의 최신 코드 받기 (매일 새 작업 전 필수)
git pull origin master

```

### ② 내 작업 브랜치 만들기

```powershell
# 4. 기능별 작업 브랜치 생성 (예: feature/roi-analysis, feature/login)
git switch -c feature/작업명

# 5. 브랜치 생성 재확인 (*표시가 내 작업 브랜치에 있는지 확인)
git branch

```

### ③ 코드 작성 및 Commit

```powershell
# 6. VS Code에서 자유롭게 코드 작성 및 테스트 후 변경 확인
git status

# 7. Commit할 파일 선택 (모르는 파일이 있다면 절대 add 금지)
git add .
git status

# 8. 로컬 저장소에 기록 남기기 (메시지는 명확하게 작성)
git commit -m "작업 내용 요약"

```

### ④ GitHub에 올리기 (Push & PR)

```powershell
# 9. Push 전 브랜치 다시 확인 (*가 master면 절대 Push 금지!)
git branch

# 10. 내 브랜치를 원격 저장소에 업로드 (-u는 최초 1회만 사용)
git push -u origin feature/작업명

```

* **11. PR 생성**: GitHub 저장소 페이지로 이동하여 `Compare & pull request` 버튼을 누르고, `base: master` ⇄ `compare: feature/작업명`이 맞는지 확인 후 PR을 생성합니다. 팀원에게 검토를 요청합니다.



---

## 👀 4. 승인자(검토자) 가이드

PR을 리뷰하는 팀원은 다음 사항을 꼼꼼히 확인한 뒤 Merge를 진행합니다.

1. **방향 확인**: `feature` 브랜치의 내용이 `master`로 향하고 있는지 확인합니다.


2. **Files changed 확인**: 초록색(+)과 빨간색(-)을 통해 어떤 코드가 바뀌었는지 확인합니다.


3. **체크리스트**:
* PR 제목과 실제 변경 내용이 일치하는가?


* 작업과 무관한 파일, 민감정보(API Key, 비밀번호 등)가 포함되지 않았는가?


* 예상치 못한 대량 삭제나 충돌(Conflict)이 없는가?




4. **승인 및 병합**: 이상이 없다면 `Review changes ➔ Approve` 후 `Merge pull request ➔ Confirm merge`를 실행합니다.



---

## 🔄 5. 상황별 추가 가이드

* **같은 브랜치에 코드를 더 수정해서 올릴 때**
```powershell
git status
git add .
git commit -m "추가 작업 내용"
git push  # -u를 이미 설정했으므로 git push만 해도 열린 PR에 자동 반영됨

```


* **다른 팀원의 작업이 Merge된 후 새 작업을 시작할 때**
```powershell
git switch master
git pull origin master
git switch -c feature/새-작업명

```



---

## 🛑 6. STOP 규칙 (문제 발생 시 대처법)

터미널에 `CONFLICT`, `rejected`, `fatal`, `error` 등 빨간 글씨가 뜨거나 예상치 못한 상황이 발생했다면 **절대 임의로 해결(force push, 임의 충돌 해결 등)하지 말고 즉시 중단**합니다.

1. 아래 두 명령어만 입력해 현재 상태를 확인합니다.


```powershell
git status
git branch

```


2. **터미널에 나온 결과 화면을 캡처하거나 그대로 복사해서 팀 단톡방에 공유**하고 함께 해결합니다.

[AI 서버 연동 정보]
- 프레임워크: FastAPI (Python)
- 실행 포트: 8000
- API 엔드포인트: http://localhost:8000/api/coordinate
- 실행 방법: uvicorn server:app --reload --port 8000
