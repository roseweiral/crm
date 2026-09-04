import type { ApiRecord } from "../services/api";

export interface ResourceDefinition {
  key: string;
  title: string;
  path: string;
  describe: (item: ApiRecord) => string;
}

function text(value: unknown): string {
  return typeof value === "string" && value.length > 0 ? value : "—";
}

export const resources: ResourceDefinition[] = [
  {
    key: "contacts",
    title: "Contacts",
    path: "/api/v1/contacts",
    describe: (item) => `${text(item.first_name)} ${text(item.last_name)}`,
  },
  {
    key: "family-units",
    title: "Family Units",
    path: "/api/v1/family-units",
    describe: (item) => `Family ${text(item.id)}`,
  },
  {
    key: "role-types",
    title: "Role Types",
    path: "/api/v1/role-types",
    describe: (item) => text(item.name),
  },
  {
    key: "group-types",
    title: "Group Types",
    path: "/api/v1/group-types",
    describe: (item) => text(item.name),
  },
  {
    key: "groups",
    title: "Groups",
    path: "/api/v1/groups",
    describe: (item) => `${text(item.name)} (${text(item.group_type_name)})`,
  },
  {
    key: "contact-role-groups",
    title: "Contact Role Groups",
    path: "/api/v1/contact-role-groups",
    describe: (item) =>
      `${text(item.contact_first_name)} ${text(item.contact_last_name)} — ${text(item.role_type_name)} at ${text(item.group_name)}`,
  },
];
