/**
 * Address book (organisation-wide directory) frontend types.
 *
 * Mirrors app/models/address_book.py and documents/api-contract.md
 * "Organisation-wide address book" — see web/README.md for the screens
 * that consume these shapes.
 */

export interface GroupPathEntry {
  id: string;
  name: string;
}

export interface AddressBookGroupRole {
  kind: "group_role";
  role_type_name: string;
  group_id: string;
  group_name: string;
  group_path: GroupPathEntry[];
}

export interface AddressBookAccessRole {
  kind: "access_role";
  access_role_name: string;
}

export type AddressBookRole = AddressBookGroupRole | AddressBookAccessRole;

export interface AddressBookEntry {
  contact_id: string;
  first_name: string;
  last_name: string;
  email: string | null;
  roles: AddressBookRole[];
}

export interface VisibilityGroupRole {
  id: string;
  kind: "group_role";
  role_type_name: string;
  group_name: string;
  hidden_from_directory: boolean;
}

export interface VisibilityAccessRole {
  id: string;
  kind: "access_role";
  access_role_name: string;
  hidden_from_directory: boolean;
}

export type VisibilityRole = VisibilityGroupRole | VisibilityAccessRole;

export interface DirectoryVisibility {
  hidden_from_directory: boolean;
  roles: VisibilityRole[];
}

export interface DirectoryVisibilityPatch {
  hidden_from_directory?: boolean;
  roles?: Array<{ id: string; hidden_from_directory: boolean }>;
}
