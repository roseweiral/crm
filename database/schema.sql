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

CREATE TABLE contacts (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  first_name varchar NOT NULL,
  last_name varchar NOT NULL,
  email varchar UNIQUE,
  status contact_status NOT NULL DEFAULT 'active',
  can_login boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  modified_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE role_types (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name varchar NOT NULL UNIQUE,
  description text,
  created_at timestamptz NOT NULL DEFAULT now(),
  modified_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE group_types (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name varchar NOT NULL UNIQUE,
  description text,
  created_at timestamptz NOT NULL DEFAULT now(),
  modified_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE groups (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  group_type_id bigint NOT NULL,
  name varchar NOT NULL,
  description text,
  parent_id bigint,
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

CREATE TABLE families (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name varchar NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  modified_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE award_types (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name varchar NOT NULL UNIQUE,
  description text,
  created_at timestamptz NOT NULL DEFAULT now(),
  modified_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE contact_roles_groups (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  contact_id bigint NOT NULL,
  role_type_id bigint NOT NULL,
  group_id bigint NOT NULL,
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

CREATE TABLE contact_families (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  contact_id bigint NOT NULL,
  family_id bigint NOT NULL,
  relationship family_relationship_type NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  modified_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT fk_contact_families_contact
    FOREIGN KEY (contact_id) REFERENCES contacts (id) ON DELETE RESTRICT,
  CONSTRAINT fk_contact_families_family
    FOREIGN KEY (family_id) REFERENCES families (id) ON DELETE RESTRICT,
  CONSTRAINT uq_contact_families_relationship
    UNIQUE (contact_id, family_id, relationship)
);

CREATE INDEX idx_contact_families_family_id
  ON contact_families (family_id);

CREATE TABLE contact_awards (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  contact_id bigint NOT NULL,
  award_type_id bigint NOT NULL,
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

CREATE TRIGGER role_types_set_modified_at
BEFORE UPDATE ON role_types
FOR EACH ROW EXECUTE FUNCTION set_modified_at();

CREATE TRIGGER group_types_set_modified_at
BEFORE UPDATE ON group_types
FOR EACH ROW EXECUTE FUNCTION set_modified_at();

CREATE TRIGGER groups_set_modified_at
BEFORE UPDATE ON groups
FOR EACH ROW EXECUTE FUNCTION set_modified_at();

CREATE TRIGGER families_set_modified_at
BEFORE UPDATE ON families
FOR EACH ROW EXECUTE FUNCTION set_modified_at();

CREATE TRIGGER award_types_set_modified_at
BEFORE UPDATE ON award_types
FOR EACH ROW EXECUTE FUNCTION set_modified_at();

CREATE TRIGGER contact_roles_groups_set_modified_at
BEFORE UPDATE ON contact_roles_groups
FOR EACH ROW EXECUTE FUNCTION set_modified_at();

CREATE TRIGGER contact_families_set_modified_at
BEFORE UPDATE ON contact_families
FOR EACH ROW EXECUTE FUNCTION set_modified_at();

CREATE TRIGGER contact_awards_set_modified_at
BEFORE UPDATE ON contact_awards
FOR EACH ROW EXECUTE FUNCTION set_modified_at();

COMMIT;
