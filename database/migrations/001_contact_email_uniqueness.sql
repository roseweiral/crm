-- Safe to rerun. Existing collisions fail the whole transaction for manual review.
BEGIN;
CREATE UNIQUE INDEX IF NOT EXISTS uq_contacts_email_normalized
    ON contacts (lower(btrim(email)));
COMMIT;
