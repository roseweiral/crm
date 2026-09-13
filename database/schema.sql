BEGIN;

CREATE TYPE family_relationship_type AS ENUM (
  'child',
  'parent',
  'guardian',
  'other'
);

CREATE TYPE contact_status AS ENUM (
  'active',
  'inactive',
  'archived'
);

CREATE TYPE contact_award_status AS ENUM (
  'nominated',
  'approved',
  'presented',
  'declined'
);

CREATE TYPE user_account_status AS ENUM (
  'invited',
  'active',
  'suspended',
  'closed'
);

CREATE TYPE identity_provider AS ENUM (
  'google',
  'microsoft'
);

CREATE TABLE contacts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  first_name varchar NOT NULL,
  last_name varchar NOT NULL,
  email varchar UNIQUE,
  status contact_status NOT NULL DEFAULT 'active',
  can_login boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  modified_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX uq_contacts_email_normalized ON contacts (lower(btrim(email)));

CREATE TABLE user_accounts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  contact_id uuid NOT NULL UNIQUE,
  status user_account_status NOT NULL DEFAULT 'invited',
  created_at timestamptz NOT NULL DEFAULT now(),
  modified_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT fk_user_accounts_contact
    FOREIGN KEY (contact_id) REFERENCES contacts (id) ON DELETE RESTRICT
);

CREATE TABLE user_identities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_account_id uuid NOT NULL UNIQUE,
  provider identity_provider NOT NULL,
  issuer varchar NOT NULL,
  subject varchar NOT NULL,
  email varchar NOT NULL,
  email_verified boolean NOT NULL,
  last_signed_in_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  modified_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT fk_user_identities_user_account
    FOREIGN KEY (user_account_id) REFERENCES user_accounts (id) ON DELETE RESTRICT,
  CONSTRAINT uq_user_identities_issuer_subject UNIQUE (issuer, subject),
  CONSTRAINT chk_user_identities_email_normalised CHECK (email = lower(email))
);

CREATE TABLE invitations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_account_id uuid NOT NULL,
  invited_by_user_account_id uuid,
  email varchar NOT NULL,
  token_hash char(64) NOT NULL UNIQUE,
  expires_at timestamptz NOT NULL DEFAULT (now() + interval '7 days'),
  accepted_at timestamptz,
  revoked_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT fk_invitations_user_account
    FOREIGN KEY (user_account_id) REFERENCES user_accounts (id) ON DELETE RESTRICT,
  CONSTRAINT fk_invitations_invited_by_user_account
    FOREIGN KEY (invited_by_user_account_id) REFERENCES user_accounts (id)
      ON DELETE RESTRICT,
  CONSTRAINT chk_invitations_email_normalised CHECK (email = lower(email)),
  CONSTRAINT chk_invitations_token_hash
    CHECK (token_hash ~ '^[0-9a-f]{64}$'),
  CONSTRAINT chk_invitations_expiry CHECK (expires_at > created_at),
  CONSTRAINT chk_invitations_completion
    CHECK (accepted_at IS NULL OR revoked_at IS NULL)
);

CREATE INDEX idx_invitations_user_account_id ON invitations (user_account_id);
CREATE INDEX idx_invitations_active
  ON invitations (expires_at)
  WHERE accepted_at IS NULL AND revoked_at IS NULL;

CREATE TABLE user_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_account_id uuid NOT NULL,
  token_hash char(64) NOT NULL UNIQUE,
  expires_at timestamptz NOT NULL DEFAULT (now() + interval '12 hours'),
  last_seen_at timestamptz NOT NULL DEFAULT now(),
  revoked_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT fk_user_sessions_user_account
    FOREIGN KEY (user_account_id) REFERENCES user_accounts (id) ON DELETE RESTRICT,
  CONSTRAINT chk_user_sessions_token_hash
    CHECK (token_hash ~ '^[0-9a-f]{64}$'),
  CONSTRAINT chk_user_sessions_expiry CHECK (expires_at > created_at)
);

CREATE INDEX idx_user_sessions_user_account_id
  ON user_sessions (user_account_id);
CREATE INDEX idx_user_sessions_active
  ON user_sessions (expires_at)
  WHERE revoked_at IS NULL;

CREATE TABLE role_types (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name varchar NOT NULL UNIQUE,
  description text,
  created_at timestamptz NOT NULL DEFAULT now(),
  modified_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE group_types (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name varchar NOT NULL UNIQUE,
  description text,
  created_at timestamptz NOT NULL DEFAULT now(),
  modified_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE groups (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  group_type_id uuid NOT NULL,
  name varchar NOT NULL,
  description text,
  parent_id uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  modified_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT fk_groups_group_type
    FOREIGN KEY (group_type_id) REFERENCES group_types (id) ON DELETE RESTRICT,
  CONSTRAINT fk_groups_parent
    FOREIGN KEY (parent_id) REFERENCES groups (id) ON DELETE RESTRICT,
  CONSTRAINT chk_groups_not_own_parent
    CHECK (parent_id IS NULL OR parent_id <> id)
);

-- PostgreSQL permits multiple NULL values in a normal unique constraint, so
-- root and child group names are constrained separately.
CREATE UNIQUE INDEX uq_groups_root_name
  ON groups (name)
  WHERE parent_id IS NULL;

CREATE UNIQUE INDEX uq_groups_parent_name
  ON groups (parent_id, name)
  WHERE parent_id IS NOT NULL;

CREATE INDEX idx_groups_group_type_id ON groups (group_type_id);
CREATE INDEX idx_groups_parent_id ON groups (parent_id);

CREATE TABLE family_units (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at timestamptz NOT NULL DEFAULT now(),
  modified_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE award_types (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name varchar NOT NULL UNIQUE,
  description text,
  created_at timestamptz NOT NULL DEFAULT now(),
  modified_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE contact_roles_groups (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  contact_id uuid NOT NULL,
  role_type_id uuid NOT NULL,
  group_id uuid NOT NULL,
  start_date date NOT NULL,
  end_date date,
  created_at timestamptz NOT NULL DEFAULT now(),
  modified_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT fk_contact_roles_groups_contact
    FOREIGN KEY (contact_id) REFERENCES contacts (id) ON DELETE RESTRICT,
  CONSTRAINT fk_contact_roles_groups_role_type
    FOREIGN KEY (role_type_id) REFERENCES role_types (id) ON DELETE RESTRICT,
  CONSTRAINT fk_contact_roles_groups_group
    FOREIGN KEY (group_id) REFERENCES groups (id) ON DELETE RESTRICT,
  CONSTRAINT uq_contact_roles_groups_assignment
    UNIQUE (contact_id, role_type_id, group_id, start_date),
  CONSTRAINT chk_contact_roles_groups_dates
    CHECK (end_date IS NULL OR end_date >= start_date)
);

CREATE INDEX idx_contact_roles_groups_role_type_id
  ON contact_roles_groups (role_type_id);
CREATE INDEX idx_contact_roles_groups_group_id
  ON contact_roles_groups (group_id);

CREATE TABLE contact_family_units (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  contact_id uuid NOT NULL,
  family_unit_id uuid NOT NULL,
  relationship family_relationship_type NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  modified_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT fk_contact_family_units_contact
    FOREIGN KEY (contact_id) REFERENCES contacts (id) ON DELETE RESTRICT,
  CONSTRAINT fk_contact_family_units_family_unit
    FOREIGN KEY (family_unit_id) REFERENCES family_units (id) ON DELETE RESTRICT,
  CONSTRAINT uq_contact_family_units_relationship
    UNIQUE (contact_id, family_unit_id, relationship)
);

CREATE INDEX idx_contact_family_units_family_unit_id
  ON contact_family_units (family_unit_id);

CREATE TABLE contact_awards (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  contact_id uuid NOT NULL,
  award_type_id uuid NOT NULL,
  status contact_award_status NOT NULL DEFAULT 'nominated',
  nomination_date date NOT NULL,
  presented_date date,
  notes text,
  created_at timestamptz NOT NULL DEFAULT now(),
  modified_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT fk_contact_awards_contact
    FOREIGN KEY (contact_id) REFERENCES contacts (id) ON DELETE RESTRICT,
  CONSTRAINT fk_contact_awards_award_type
    FOREIGN KEY (award_type_id) REFERENCES award_types (id) ON DELETE RESTRICT,
  CONSTRAINT uq_contact_awards_contact_award_type
    UNIQUE (contact_id, award_type_id),
  CONSTRAINT chk_contact_awards_dates
    CHECK (presented_date IS NULL OR presented_date >= nomination_date)
);

CREATE INDEX idx_contact_awards_award_type_id
  ON contact_awards (award_type_id);

CREATE TABLE permissions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name varchar NOT NULL UNIQUE,
  description text,
  created_at timestamptz NOT NULL DEFAULT now(),
  modified_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE access_roles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name varchar NOT NULL UNIQUE,
  description text,
  is_global boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  modified_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE access_role_permissions (
  access_role_id uuid NOT NULL,
  permission_id uuid NOT NULL,
  PRIMARY KEY (access_role_id, permission_id),
  CONSTRAINT fk_access_role_permissions_role
    FOREIGN KEY (access_role_id) REFERENCES access_roles (id) ON DELETE RESTRICT,
  CONSTRAINT fk_access_role_permissions_permission
    FOREIGN KEY (permission_id) REFERENCES permissions (id) ON DELETE RESTRICT
);

CREATE TABLE user_access_role_assignments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_account_id uuid NOT NULL,
  access_role_id uuid NOT NULL,
  group_id uuid,
  start_date date NOT NULL DEFAULT current_date,
  end_date date,
  created_at timestamptz NOT NULL DEFAULT now(),
  modified_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT fk_user_access_role_assignments_account
    FOREIGN KEY (user_account_id) REFERENCES user_accounts (id) ON DELETE RESTRICT,
  CONSTRAINT fk_user_access_role_assignments_role
    FOREIGN KEY (access_role_id) REFERENCES access_roles (id) ON DELETE RESTRICT,
  CONSTRAINT fk_user_access_role_assignments_group
    FOREIGN KEY (group_id) REFERENCES groups (id) ON DELETE RESTRICT,
  CONSTRAINT chk_user_access_role_assignments_dates
    CHECK (end_date IS NULL OR end_date >= start_date),
  CONSTRAINT uq_user_access_role_assignments
    UNIQUE NULLS NOT DISTINCT
      (user_account_id, access_role_id, group_id, start_date)
);

CREATE INDEX idx_user_access_role_assignments_account
  ON user_access_role_assignments (user_account_id);
CREATE INDEX idx_user_access_role_assignments_group
  ON user_access_role_assignments (group_id);

CREATE TABLE audit_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_account_id uuid,
  event_type varchar NOT NULL,
  outcome varchar NOT NULL,
  provider identity_provider,
  subject varchar,
  ip_address inet,
  user_agent text,
  details jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT fk_audit_events_user_account
    FOREIGN KEY (user_account_id) REFERENCES user_accounts (id) ON DELETE RESTRICT,
  CONSTRAINT chk_audit_events_outcome
    CHECK (outcome IN ('success', 'failure'))
);

CREATE INDEX idx_audit_events_user_account_created
  ON audit_events (user_account_id, created_at DESC);
CREATE INDEX idx_audit_events_event_created
  ON audit_events (event_type, created_at DESC);

CREATE FUNCTION set_modified_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.modified_at = now();
  RETURN NEW;
END;
$$;

CREATE TRIGGER contacts_set_modified_at
BEFORE UPDATE ON contacts
FOR EACH ROW EXECUTE FUNCTION set_modified_at();

CREATE TRIGGER user_accounts_set_modified_at
BEFORE UPDATE ON user_accounts
FOR EACH ROW EXECUTE FUNCTION set_modified_at();

CREATE TRIGGER user_identities_set_modified_at
BEFORE UPDATE ON user_identities
FOR EACH ROW EXECUTE FUNCTION set_modified_at();

CREATE TRIGGER role_types_set_modified_at
BEFORE UPDATE ON role_types
FOR EACH ROW EXECUTE FUNCTION set_modified_at();

CREATE TRIGGER group_types_set_modified_at
BEFORE UPDATE ON group_types
FOR EACH ROW EXECUTE FUNCTION set_modified_at();

CREATE TRIGGER groups_set_modified_at
BEFORE UPDATE ON groups
FOR EACH ROW EXECUTE FUNCTION set_modified_at();

CREATE TRIGGER family_units_set_modified_at
BEFORE UPDATE ON family_units
FOR EACH ROW EXECUTE FUNCTION set_modified_at();

CREATE TRIGGER award_types_set_modified_at
BEFORE UPDATE ON award_types
FOR EACH ROW EXECUTE FUNCTION set_modified_at();

CREATE TRIGGER contact_roles_groups_set_modified_at
BEFORE UPDATE ON contact_roles_groups
FOR EACH ROW EXECUTE FUNCTION set_modified_at();

CREATE TRIGGER contact_family_units_set_modified_at
BEFORE UPDATE ON contact_family_units
FOR EACH ROW EXECUTE FUNCTION set_modified_at();

CREATE TRIGGER contact_awards_set_modified_at
BEFORE UPDATE ON contact_awards
FOR EACH ROW EXECUTE FUNCTION set_modified_at();

CREATE TRIGGER permissions_set_modified_at
BEFORE UPDATE ON permissions
FOR EACH ROW EXECUTE FUNCTION set_modified_at();

CREATE TRIGGER access_roles_set_modified_at
BEFORE UPDATE ON access_roles
FOR EACH ROW EXECUTE FUNCTION set_modified_at();

CREATE TRIGGER user_access_role_assignments_set_modified_at
BEFORE UPDATE ON user_access_role_assignments
FOR EACH ROW EXECUTE FUNCTION set_modified_at();

COMMIT;
