# 테스트

```bash
python3 tests/run_all.py     # 전체 (권장)
node tests/e2e.js            # 개별
```

## 필요한 것

```bash
npm install jsdom
```

`node_modules`가 `tests/` 또는 상위 폴더에 있으면 된다.

## 무엇을 잡는가

| 파일 | 범위 |
|---|---|
| `e2e.js` | 부팅 → 탭 이동 → 설치 → 모달, 20단계 |
| `boot2.js` | 약관 게이트 → 로그인 흐름. **무한 로딩 회귀 방지** |
| `modui.js` | 모드 카드/모달 버튼 배치, 버전 표시 |
| `libtest.js` | 라이브러리 제거 버튼이 업데이트를 실행하지 않는지 |
| `vertest.js` / `vermenu.js` | 버전 롤백, 드롭다운 |
| `scroll.js` | 버전 선택 후 스크롤 보존 |
| `upd.js` | 런처 업데이트 확인 3상태 (최신/업데이트/확인 불가) |
| `terms.js` | 약관 동의 게이트 |
| `canceltest.js` | 설치 진행률·취소 |
| `fix5.js` `logo.js` `memtest.js` `beta.js` | 개별 회귀 |

## 주의

- 프론트 최상위 `const`는 `window` 프로퍼티가 아니다 → `w.eval('DATA')`
- `node --check`는 문법만 본다. 미선언 변수는 스위트가 잡는다.
