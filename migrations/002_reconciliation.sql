CREATE TABLE claim_reconciliations(id TEXT PRIMARY KEY,property_id TEXT NOT NULL REFERENCES properties(id),field TEXT NOT NULL,selected_claim_id TEXT NOT NULL REFERENCES claims(id),considered_claim_ids TEXT NOT NULL,reason TEXT NOT NULL,reviewer_id TEXT NOT NULL REFERENCES users(id),created_at TEXT NOT NULL);
CREATE TRIGGER reconciliation_no_update BEFORE UPDATE ON claim_reconciliations BEGIN SELECT RAISE(ABORT,'Append-only reconciliation'); END;
CREATE TRIGGER reconciliation_no_delete BEFORE DELETE ON claim_reconciliations BEGIN SELECT RAISE(ABORT,'Append-only reconciliation'); END;
