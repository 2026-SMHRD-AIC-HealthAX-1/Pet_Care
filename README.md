# 🐶 Zzonggeut (Pet Care & Monitoring)

## 📌 팀 깃허브 및 협업 규칙
1. **평일 작업 시작**: 오전 9시 팀회의 후 `git pull origin master` 및 오늘 담당 도메인 공유
2. **주말 작업 예외 룰**: 
   - 주말 작업 시 **시작 전 톡방에 "주말 작업 시작 [도메인/할일] - 이름"** 반드시 공지
   - 주말 간 병합(Merge) 충돌 방지를 위해 작업 전후 `pull`/`push` 상태 꼼꼼히 체크하기
3. **영역 분담 준수**: 본인 담당 도메인 패키지(`domain/pet`, `domain/monitoring`, `domain/analysis`, `domain/user`) 위주로 수정
4. **공통 파일 소통**: `application.properties` 등 공통 설정 수정 시 반드시 사전 공유
5. **Push 전 테스트**: 로컬 서버 기동(`port 9090`) 확인 후 push
6. **Push 알림**: 톡방에 `[푸시] 도메인/기능 요약 - 이름` 남기기
7. **커밋 메시지**: `[타입(도메인)]: 설명 - 이름` (예: `feat(pet): 펫 등록 로직 구현 - 세인`)
