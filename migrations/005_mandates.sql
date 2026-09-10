-- Structured deal introductions only. This schema deliberately has no wallet,
-- closing, ownership, instrument, or automated outreach authority.
CREATE TABLE IF NOT EXISTS mandates(
 id TEXT PRIMARY KEY,
 organization_id TEXT NOT NULL REFERENCES organizations(id),
 created_by TEXT NOT NULL REFERENCES users(id),
 property_id TEXT REFERENCES properties(id),
 kind TEXT NOT NULL CHECK(kind IN ('OPPORTUNITY','CAPITAL_REQUEST')),
 asset_class TEXT NOT NULL CHECK(asset_class IN ('REAL_ESTATE','ART_COLLECTIBLE','OTHER_PRIVATE_ASSET')),
 asset_subtype TEXT NOT NULL,
 jurisdiction TEXT NOT NULL,
 market TEXT NOT NULL,
 intent TEXT NOT NULL,
 value_min REAL,
 value_max REAL,
 currency TEXT NOT NULL DEFAULT 'CAD',
 timeline TEXT NOT NULL,
 requirements TEXT NOT NULL,
 data_classification TEXT NOT NULL CHECK(data_classification IN ('DEMO_SYNTHETIC','REAL_PRIVATE')),
 rights_attested INTEGER NOT NULL DEFAULT 0,
 consent_to_matching INTEGER NOT NULL DEFAULT 0,
 state TEXT NOT NULL DEFAULT 'DRAFT' CHECK(state IN ('DRAFT','SUBMITTED','WITHDRAWN')),
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS mandates_tenant ON mandates(organization_id,state);
CREATE TABLE IF NOT EXISTS mandate_matches(
 id TEXT PRIMARY KEY,
 left_mandate_id TEXT NOT NULL REFERENCES mandates(id),
 right_mandate_id TEXT NOT NULL REFERENCES mandates(id),
 proposed_by TEXT NOT NULL REFERENCES users(id),
 rationale TEXT NOT NULL,
 state TEXT NOT NULL DEFAULT 'PROPOSED' CHECK(state IN ('PROPOSED','LEFT_ACCEPTED','RIGHT_ACCEPTED','MUTUALLY_ACCEPTED','DECLINED')),
 left_accepted_at TEXT,
 right_accepted_at TEXT,
 created_at TEXT NOT NULL,
 UNIQUE(left_mandate_id,right_mandate_id)
);
CREATE TABLE IF NOT EXISTS mandate_room_invitations(
 id TEXT PRIMARY KEY,
 match_id TEXT NOT NULL REFERENCES mandate_matches(id),
 property_id TEXT NOT NULL REFERENCES properties(id),
 invited_user_id TEXT NOT NULL REFERENCES users(id),
 invited_by TEXT NOT NULL REFERENCES users(id),
 level INTEGER NOT NULL DEFAULT 3 CHECK(level BETWEEN 3 AND 3),
 state TEXT NOT NULL DEFAULT 'PENDING' CHECK(state IN ('PENDING','ACCEPTED','REVOKED')),
 created_at TEXT NOT NULL,
 accepted_at TEXT
);
CREATE INDEX IF NOT EXISTS mandate_invites_user ON mandate_room_invitations(invited_user_id,state);
