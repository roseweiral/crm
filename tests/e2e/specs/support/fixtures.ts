/**
 * Signed-in-session test fixtures for Playwright specs.
 *
 * Mirrors tests/api/conftest.py's `records` / `person` / `session_token`
 * fixtures: mint short-lived rows and a real application session directly
 * against the test database (the same technique
 * documents/authentication-operations.md describes for e2e tests), rather
 * than adding a test-only login endpoint or authentication bypass to the
 * application. Every row a test creates is removed in teardown, even when
 * the test fails, and specs create their own throwaway contacts/roles
 * rather than mutating seed or demo data — the same rule
 * tests/README.md states for the API suite.
 */
import { createHash, randomBytes, randomUUID } from "node:crypto";

import { test as base, expect, type BrowserContext } from "@playwright/test";
import { Pool } from "pg";

const FRONTEND_URL = process.env.FRONTEND_URL ?? "http://frontend:8080";

let pool: Pool | undefined;

function db(): Pool {
  pool ??= new Pool({ connectionString: process.env.DATABASE_URL });
  return pool;
}

function quoteIdent(name: string): string {
  return `"${name.replace(/"/g, '""')}"`;
}

export type Row = Record<string, unknown> & { id: string };

async function insertRow(table: string, values: Record<string, unknown>): Promise<Row> {
  const columns = Object.keys(values);
  const columnSql = columns.map(quoteIdent).join(", ");
  const placeholders = columns.map((_, index) => `$${index + 1}`).join(", ");
  const result = await db().query(
    `INSERT INTO ${quoteIdent(table)} (${columnSql}) VALUES (${placeholders}) RETURNING *`,
    columns.map((column) => values[column]),
  );
  return result.rows[0] as Row;
}

/** `SELECT id FROM role_types WHERE name = ...` — role_types is seed data, stable across runs. */
export async function roleTypeId(name: string): Promise<string> {
  const result = await db().query<{ id: string }>("SELECT id FROM role_types WHERE name = $1", [name]);
  if (result.rows.length === 0) {
    throw new Error(`No seeded role_types row named "${name}"`);
  }
  return result.rows[0].id;
}

export type RecordsFixture = (table: string, values: Record<string, unknown>) => Promise<Row>;

export interface PersonFixture {
  (): Promise<{ contact: Row; account: Row }>;
}

export interface Fixtures {
  records: RecordsFixture;
  person: PersonFixture;
  sessionToken: (accountId: string) => Promise<string>;
  signedInContext: (accountId: string) => Promise<BrowserContext>;
}

export const test = base.extend<Fixtures>({
  records: async ({}, use) => {
    const created: Array<[string, string]> = [];
    const insert: RecordsFixture = async (table, values) => {
      const row = await insertRow(table, values);
      created.push([table, row.id]);
      return row;
    };
    await use(insert);

    for (const [table, id] of [...created].reverse()) {
      if (table === "user_accounts") {
        // These can be created by the endpoint under test rather than by
        // this fixture directly, so clean up whatever accumulated.
        for (const dependent of ["audit_events", "user_sessions", "user_identities", "invitations"]) {
          await db().query(`DELETE FROM ${quoteIdent(dependent)} WHERE user_account_id = $1`, [id]);
        }
      }
      if (table === "contacts") {
        await db().query(
          "DELETE FROM audit_events WHERE details->>'invited_contact_id' = $1 OR details->>'contact_id' = $1",
          [id],
        );
      }
      await db().query(`DELETE FROM ${quoteIdent(table)} WHERE id = $1`, [id]);
    }
  },

  person: async ({ records }, use) => {
    const create: PersonFixture = async () => {
      const suffix = randomUUID();
      const contact = await records("contacts", {
        first_name: "E2E",
        last_name: suffix,
        email: `${suffix}@example.test`,
        can_login: true,
      });
      const account = await records("user_accounts", { contact_id: contact.id, status: "active" });
      return { contact, account };
    };
    await use(create);
  },

  sessionToken: async ({ records }, use) => {
    const create = async (accountId: string) => {
      const token = randomBytes(36).toString("base64url");
      const tokenHash = createHash("sha256").update(token, "utf8").digest("hex");
      await records("user_sessions", { user_account_id: accountId, token_hash: tokenHash });
      return token;
    };
    await use(create);
  },

  // eslint-disable-next-line no-empty-pattern
  signedInContext: async ({ browser, sessionToken }, use) => {
    const contexts: BrowserContext[] = [];
    const create = async (accountId: string) => {
      const token = await sessionToken(accountId);
      const context = await browser.newContext();
      await context.addCookies([
        {
          name: "crm_session",
          value: token,
          url: FRONTEND_URL,
          httpOnly: true,
          sameSite: "Lax",
        },
      ]);
      contexts.push(context);
      return context;
    };
    await use(create);
    for (const context of contexts) {
      await context.close();
    }
  },
});

export { expect };
