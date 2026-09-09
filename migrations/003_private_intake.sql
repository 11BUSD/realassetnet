CREATE TABLE property_intake_records(property_id TEXT PRIMARY KEY REFERENCES properties(id),data_classification TEXT NOT NULL,source_reference TEXT NOT NULL,rights_attested INTEGER NOT NULL,contributor_id TEXT REFERENCES users(id),created_at TEXT NOT NULL);
CREATE TABLE artifact_blobs(artifact_id TEXT PRIMARY KEY REFERENCES artifacts(id),raw_bytes BLOB NOT NULL,byte_length INTEGER NOT NULL,mime_type TEXT NOT NULL);
CREATE TRIGGER intake_no_update BEFORE UPDATE ON property_intake_records BEGIN SELECT RAISE(ABORT,'Immutable intake provenance'); END;
CREATE TRIGGER intake_no_delete BEFORE DELETE ON property_intake_records BEGIN SELECT RAISE(ABORT,'Immutable intake provenance'); END;
CREATE TRIGGER blobs_no_update BEFORE UPDATE ON artifact_blobs BEGIN SELECT RAISE(ABORT,'Immutable original bytes'); END;
CREATE TRIGGER blobs_no_delete BEFORE DELETE ON artifact_blobs BEGIN SELECT RAISE(ABORT,'Immutable original bytes'); END;
