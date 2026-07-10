-- ============================================================
-- 동글랜드 런처 회원 / 화이트리스트 DB 스키마 (SQLite)
-- source of truth = 이 DB. whitelist.json 은 여기서 export 한다.
-- UUID 저장 규칙: 하이픈 없는 소문자 32자 (Mojang API 형식)
-- ============================================================

PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------
-- 1) members : 사람 단위. 핵심 테이블.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS members (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,

    -- 마인크래프트 정품 계정 식별 (필수)
    mc_uuid         TEXT    NOT NULL UNIQUE,          -- 하이픈 없는 32자
    mc_username     TEXT    NOT NULL,                 -- 최근 확인된 닉네임 (변경될 수 있음)

    -- 접속 권한 (화이트리스트 export 대상 여부)
    status          TEXT    NOT NULL DEFAULT 'active' -- active / suspended / banned / pending
                            CHECK (status IN ('active','suspended','banned','pending')),
    is_whitelisted  INTEGER NOT NULL DEFAULT 1        -- 1이면 whitelist.json 에 포함
                            CHECK (is_whitelisted IN (0,1)),

    -- 등급/역할 (부가 데이터, 지금은 기본값만)
    role            TEXT    NOT NULL DEFAULT 'member' -- member / vip / staff / admin
                            CHECK (role IN ('member','vip','staff','admin')),

    -- 가입/활동 메타
    joined_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    last_login_at   TEXT,                             -- 런처 로그인 시각 (NULL 허용)
    last_seen_at    TEXT,                             -- 마지막 접속/활동 (NULL 허용)
    login_count     INTEGER NOT NULL DEFAULT 0,

    -- 확장 여지: 운영 메모 / 임의 데이터
    note            TEXT,                             -- 운영자 메모 (NULL 허용)
    metadata        TEXT,                             -- 향후 임의 JSON 저장용 (NULL 허용)

    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_members_uuid    ON members(mc_uuid);
CREATE INDEX IF NOT EXISTS idx_members_status  ON members(status);
CREATE INDEX IF NOT EXISTS idx_members_wl      ON members(is_whitelisted);

-- updated_at 자동 갱신
CREATE TRIGGER IF NOT EXISTS trg_members_updated
AFTER UPDATE ON members
FOR EACH ROW
BEGIN
    UPDATE members SET updated_at = datetime('now') WHERE id = OLD.id;
END;

-- ------------------------------------------------------------
-- 2) login_events : 런처 로그인 이력 (통계/감사용, 선택)
--    지금 안 써도 되지만, "누가 언제 얼마나 쓰는지" 통계 요구가
--    생길 때를 대비해 열어둔다. 안 쓰면 그냥 비어있으면 됨.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS login_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    member_id       INTEGER NOT NULL,
    event_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    launcher_ver    TEXT,                             -- 런처 버전 (예: 2.1)
    mc_version      TEXT,                             -- 실행한 마크 버전 (NULL 허용)
    ip_hash         TEXT,                             -- IP 원문 저장 금지, 해시만 (선택)
    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_login_member ON login_events(member_id);
CREATE INDEX IF NOT EXISTS idx_login_time   ON login_events(event_at);

-- ------------------------------------------------------------
-- 3) uuid_hyphenate : UUID 하이픈 변환용 뷰 (whitelist.json export 편의)
--    32자 -> 8-4-4-4-12 형식으로 변환한 컬럼 제공
-- ------------------------------------------------------------
CREATE VIEW IF NOT EXISTS v_whitelist AS
SELECT
    mc_username AS name,
    substr(mc_uuid,1,8)  || '-' ||
    substr(mc_uuid,9,4)  || '-' ||
    substr(mc_uuid,13,4) || '-' ||
    substr(mc_uuid,17,4) || '-' ||
    substr(mc_uuid,21,12) AS uuid
FROM members
WHERE is_whitelisted = 1
  AND status = 'active';
