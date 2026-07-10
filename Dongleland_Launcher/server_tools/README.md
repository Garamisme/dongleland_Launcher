# server_tools — 운영자/서버 측 전용 도구

> ⚠️ **런처 배포물(exe/zip)에 이 폴더를 절대 포함하지 말 것.**
> DB·화이트리스트 원본은 운영자 측에서만 관리한다 (클라이언트 불신 원칙).
> 현재 .spec 은 assets/frontend 만 번들하고 이 폴더는 임포트되지 않으므로
> 기본적으로 exe 에 안 들어간다 — 배포 zip 을 손으로 만들 때만 주의.

## 구성
- `schema.sql` — members / login_events / v_whitelist 뷰 (source of truth 스키마)
- `dongleland_members.py` — 멤버 관리 + whitelist.json export CLI (표준 라이브러리만 사용)
- `members.db` — 실행하면 생성됨. **git/배포에 포함 금지, 백업 대상.**

## 일상 운영 흐름
```
py dongleland_members.py init                      # 최초 1회
py dongleland_members.py add <마크닉네임>          # UUID 는 Mojang 자동 조회
py dongleland_members.py set-status <닉> suspended # 정지 (삭제 없음 — 이력 보존)
py dongleland_members.py export --server-dir <마크서버폴더>
(서버 콘솔) /whitelist reload
```

## 원칙 리마인드 (HANDOFF_AUTH_WHITELIST.md)
- 접속 통제는 100% 마크 서버 whitelist.json. 런처는 판단하지 않는다.
- 멤버 삭제 명령은 의도적으로 없다. status 변경만.
- 라이선스 키 시스템은 폐기됨. 다시 만들지 말 것.
