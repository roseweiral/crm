"""Behavioral contract for contact creation and partial editing."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from uuid import uuid4

import httpx
import psycopg
import pytest

from .support import API_URL, DATABASE_URL, database_rows

pytestmark = pytest.mark.contract


@pytest.fixture
def writer(callback_client, records, monkeypatch):
    client, _ = callback_client
    client.cookies.set("crm_session", os.environ["AUTH_TEST_SESSION_TOKEN"])
    client.headers.update({"Origin": "http://localhost:5173", "X-CRM-CSRF": "1"})
    original_post = client.post

    def post(url, **kwargs):
        response = original_post(url, **kwargs)
        if response.status_code == 201 and str(url) == "/api/v1/contacts":
            records.track("contacts", response.json()["id"])
        return response

    monkeypatch.setattr(client, "post", post)
    return client


def payload(**values):
    return {
        "first_name": " Alice ",
        "last_name": " Example ",
        "email": f"{uuid4()}@example.org",
        **values,
    }


def tag(client, contact):
    response = client.get(f"/api/v1/contacts/{contact['id']}")
    assert response.status_code == 200
    assert response.headers.get("etag"), "Detail GET must expose an ETag"
    return response.headers["etag"]


def events(contact_id):
    return database_rows(
        "SELECT * FROM audit_events WHERE details->>'contact_id' = %s ORDER BY created_at",
        (str(contact_id),),
    )


def test_contact_post_normalizes_persists_and_audits(writer):
    data = payload(email=f"  {uuid4()}@EXAMPLE.ORG  ")
    response = writer.post("/api/v1/contacts", json=data)
    assert response.status_code == 201
    body = response.json()
    assert body["first_name"] == "Alice"
    assert body["last_name"] == "Example"
    assert body["email"] == data["email"].strip().lower()
    assert body["status"] == "active" and body["can_login"] is False
    assert response.headers["location"] == f"/api/v1/contacts/{body['id']}"
    fetched = writer.get(response.headers["location"])
    assert fetched.json() == body
    assert fetched.headers["etag"] == response.headers["etag"]
    assert (
        database_rows(
            "SELECT id FROM user_accounts WHERE contact_id = %s", (body["id"],)
        )
        == []
    )
    audit = events(body["id"])
    assert len(audit) == 1 and audit[0]["event_type"] == "contact.created"
    assert audit[0]["details"] == {"contact_id": body["id"]}
    assert (
        str(audit[0]["user_account_id"])
        == writer.get("/api/v1/me").json()["account_id"]
    )


def test_contact_post_allows_multiple_null_emails(writer):
    for _ in range(2):
        response = writer.post(
            "/api/v1/contacts", json={"first_name": "A", "last_name": "B"}
        )
        assert response.status_code == 201
        assert response.json()["email"] is None


@pytest.mark.parametrize(
    "change",
    [
        {"first_name": ""},
        {"first_name": "   "},
        {"first_name": None},
        {"first_name": 3},
        {"first_name": "a" * 101},
        {"last_name": None},
        {"email": ""},
        {"email": "not-an-email"},
        {"status": None},
        {"status": "deleted"},
        {"can_login": True},
        {"id": str(uuid4())},
        {"modified_at": "2020-01-01"},
        {"access_roles": ["Global System Administrator"]},
        {"unexpected": 1},
    ],
)
def test_contact_post_rejects_invalid_and_protected_fields(writer, change):
    response = writer.post("/api/v1/contacts", json=payload(**change))
    assert response.status_code == 422


def test_contact_post_requires_names(writer):
    assert (
        writer.post(
            "/api/v1/contacts", json={"email": f"{uuid4()}@example.org"}
        ).status_code
        == 422
    )


def test_contact_post_rejects_normalized_duplicate(writer, records):
    email = f"{uuid4()}@example.org"
    records(
        "contacts", first_name="Legacy", last_name="Email", email=f" {email.upper()} "
    )
    response = writer.post("/api/v1/contacts", json=payload(email=email))
    assert response.status_code == 409
    assert response.json() == {"detail": "Email is already assigned to a contact"}


def test_contact_patch_distinguishes_omission_and_null(writer, person):
    contact, _ = person()
    path = f"/api/v1/contacts/{contact['id']}"
    before = tag(writer, contact)
    response = writer.patch(
        path, headers={"If-Match": before}, json={"first_name": " Changed "}
    )
    assert response.status_code == 200
    assert response.json()["first_name"] == "Changed"
    assert response.json()["email"] == contact["email"]
    assert response.headers["etag"] != before
    cleared = writer.patch(
        path, headers={"If-Match": response.headers["etag"]}, json={"email": None}
    )
    assert cleared.status_code == 200
    assert cleared.json()["email"] is None
    assert cleared.json()["last_name"] == contact["last_name"]
    assert writer.get(path).json() == cleared.json()
    assert [a["details"]["fields"] for a in events(contact["id"])] == [
        ["first_name"],
        ["email"],
    ]


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"first_name": None},
        {"last_name": ""},
        {"status": None},
        {"email": ""},
        {"can_login": False},
        {"created_at": None},
        {"other": 1},
    ],
)
def test_contact_patch_rejects_invalid_fields(writer, person, body):
    contact, _ = person()
    response = writer.patch(
        f"/api/v1/contacts/{contact['id']}",
        headers={"If-Match": tag(writer, contact)},
        json=body,
    )
    assert response.status_code == 422
    assert events(contact["id"]) == []


@pytest.mark.parametrize(
    "header,expected",
    [
        (None, 428),
        ("*", 422),
        ('W/"x"', 422),
        ('"x", "y"', 422),
        ("unquoted", 422),
        ('"stale"', 412),
    ],
)
def test_contact_patch_requires_current_single_strong_tag(
    writer, person, header, expected
):
    contact, _ = person()
    response = writer.patch(
        f"/api/v1/contacts/{contact['id']}",
        json={"first_name": "New"},
        headers={} if header is None else {"If-Match": header},
    )
    assert response.status_code == expected
    assert (
        database_rows(
            "SELECT first_name FROM contacts WHERE id = %s", (contact["id"],)
        )[0]["first_name"]
        == contact["first_name"]
    )
    assert events(contact["id"]) == []


def test_contact_patch_stale_tag_cannot_overwrite(writer, person):
    contact, _ = person()
    old = tag(writer, contact)
    path = f"/api/v1/contacts/{contact['id']}"
    assert (
        writer.patch(
            path, headers={"If-Match": old}, json={"first_name": "First"}
        ).status_code
        == 200
    )
    assert (
        writer.patch(
            path, headers={"If-Match": old}, json={"first_name": "Second"}
        ).status_code
        == 412
    )
    assert writer.get(path).json()["first_name"] == "First"
    assert len(events(contact["id"])) == 1


def test_contact_patch_duplicate_rolls_back(writer, person, records):
    contact, _ = person()
    other = records(
        "contacts",
        first_name="Other",
        last_name="Person",
        email=f"{uuid4()}@example.org",
    )
    before = tag(writer, contact)
    response = writer.patch(
        f"/api/v1/contacts/{contact['id']}",
        headers={"If-Match": before},
        json={"first_name": "Should roll back", "email": other["email"].upper()},
    )
    assert response.status_code == 409
    assert tag(writer, contact) == before
    assert events(contact["id"]) == []


@pytest.mark.parametrize("method", ["post", "patch"])
def test_contact_writes_require_authentication_and_admin(
    writer, person, session_token, method
):
    contact, account = person()
    url = (
        "/api/v1/contacts" if method == "post" else f"/api/v1/contacts/{contact['id']}"
    )
    headers = {"If-Match": tag(writer, contact)}
    writer.cookies.clear()
    assert (
        getattr(writer, method)(url, json=payload(), headers=headers).status_code == 401
    )
    writer.cookies.set("crm_session", session_token(account["id"]))
    assert (
        getattr(writer, method)(url, json=payload(), headers=headers).status_code == 403
    )
    if method == "patch":
        assert (
            writer.patch(
                f"/api/v1/contacts/{uuid4()}", json={"first_name": "X"}, headers=headers
            ).status_code
            == 403
        )


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": ""},
        {"Origin": "null"},
        {"Origin": "https://evil.example"},
        {"X-CRM-CSRF": ""},
        {"X-CRM-CSRF": "wrong"},
    ],
)
@pytest.mark.parametrize("method", ["post", "patch"])
def test_contact_write_csrf_rejected(writer, person, headers, method):
    contact, _ = person()
    path = (
        "/api/v1/contacts" if method == "post" else f"/api/v1/contacts/{contact['id']}"
    )
    headers = {"If-Match": tag(writer, contact), **headers}
    assert (
        getattr(writer, method)(path, json=payload(), headers=headers).status_code
        == 403
    )
    assert events(contact["id"]) == []


def test_contact_write_rejects_simple_content_type(writer):
    response = writer.post(
        "/api/v1/contacts",
        content='{"first_name":"A","last_name":"B"}',
        headers={"Content-Type": "text/plain"},
    )
    assert response.status_code == 415


def test_contact_patch_missing_and_malformed_id(writer):
    headers = {"If-Match": '"tag"'}
    assert (
        writer.patch(
            f"/api/v1/contacts/{uuid4()}", json={"first_name": "A"}, headers=headers
        ).status_code
        == 404
    )
    assert (
        writer.patch(
            "/api/v1/contacts/not-a-uuid", json={"first_name": "A"}, headers=headers
        ).status_code
        == 422
    )


def test_archive_revokes_sessions_and_preserves_identity(
    writer, person, session_token, records
):
    contact, account = person()
    identity = records(
        "user_identities",
        user_account_id=account["id"],
        provider="google",
        issuer="https://issuer.example",
        subject=str(uuid4()),
        email=contact["email"],
        email_verified=True,
    )
    token = session_token(account["id"])
    path = f"/api/v1/contacts/{contact['id']}"
    response = writer.patch(
        path,
        headers={"If-Match": tag(writer, contact)},
        json={"status": "archived", "email": f"{uuid4()}@example.org"},
    )
    assert response.status_code == 200
    assert all(
        row["revoked_at"]
        for row in database_rows(
            "SELECT revoked_at FROM user_sessions WHERE user_account_id = %s",
            (account["id"],),
        )
    )
    assert (
        database_rows(
            "SELECT email FROM user_identities WHERE id = %s", (identity["id"],)
        )[0]["email"]
        == contact["email"]
    )
    assert (
        database_rows(
            "SELECT status FROM user_accounts WHERE id = %s", (account["id"],)
        )[0]["status"]
        == "active"
    )
    assert (
        writer.patch(
            path,
            headers={"If-Match": response.headers["etag"]},
            json={"status": "active"},
        ).status_code
        == 200
    )
    with httpx.Client(cookies={"crm_session": token}) as client:
        assert client.get(f"{API_URL}/api/v1/me").status_code == 401


def test_contact_update_rolls_back_if_audit_fails(
    writer, person, session_token, monkeypatch
):
    from routers import contacts as routes

    contact, account = person()
    session_token(account["id"])
    before = tag(writer, contact)

    def fail(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(routes, "audit_event", fail)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        writer.patch(
            f"/api/v1/contacts/{contact['id']}",
            headers={"If-Match": before},
            json={"status": "archived"},
        )
    assert tag(writer, contact) == before
    assert (
        database_rows(
            "SELECT revoked_at FROM user_sessions WHERE user_account_id = %s",
            (account["id"],),
        )[0]["revoked_at"]
        is None
    )


def test_contact_create_rolls_back_if_audit_fails(writer, monkeypatch):
    from routers import contacts as routes

    data = payload()

    def fail(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(routes, "audit_event", fail)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        writer.post("/api/v1/contacts", json=data)
    assert (
        database_rows("SELECT id FROM contacts WHERE email = %s", (data["email"],))
        == []
    )


def test_contact_write_cors_preflight_and_exposed_headers():
    origin = "http://localhost:5174"
    response = httpx.options(
        f"{API_URL}/api/v1/contacts/{uuid4()}",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "content-type,if-match,x-crm-csrf",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    contact = database_rows("SELECT id FROM contacts ORDER BY id LIMIT 1")[0]
    response = httpx.get(
        f"{API_URL}/api/v1/contacts/{contact['id']}", headers={"Origin": origin}
    )
    exposed = response.headers.get("access-control-expose-headers", "").lower()
    assert "etag" in exposed and "location" in exposed


def test_simultaneous_contact_updates_allow_one_winner(person, session_token, records):
    # Distinct admin sessions ensure session last_seen locking cannot serialize the requests.
    _, actor = person()
    role = database_rows(
        "SELECT id FROM access_roles WHERE name = 'Global System Administrator'"
    )[0]
    from datetime import date

    records(
        "user_access_role_assignments",
        user_account_id=actor["id"],
        access_role_id=role["id"],
        start_date=date.today(),
    )
    contact, _ = person()
    tokens = [session_token(actor["id"]), session_token(actor["id"])]
    url = f"{API_URL}/api/v1/contacts/{contact['id']}"
    response = httpx.get(url, cookies={"crm_session": tokens[0]})
    assert "etag" in response.headers
    old = response.headers["etag"]
    from threading import Barrier

    barrier = Barrier(2)

    def update(index):
        with httpx.Client(cookies={"crm_session": tokens[index]}) as client:
            barrier.wait(timeout=5)
            return client.patch(
                url,
                headers={
                    "Origin": "http://localhost:5174",
                    "X-CRM-CSRF": "1",
                    "If-Match": old,
                },
                json={"first_name": f"Writer {index}"},
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(update, [0, 1]))
    assert sorted(codes) == [200, 412]
    assert len(events(contact["id"])) == 1


@pytest.mark.parametrize("name", ["Bad\x00Name", "Bad\nName"])
def test_contact_names_reject_control_characters(writer, name):
    assert (
        writer.post("/api/v1/contacts", json=payload(first_name=name)).status_code
        == 422
    )


def test_self_archive_does_not_deadlock_concurrent_sessions(
    person, session_token, records, monkeypatch
):
    from datetime import date
    from threading import Barrier

    from authentication import get_current_user
    from authorization import (
        AuthorizationService,
        get_authorization_service,
        load_policy,
    )
    from fastapi import Depends
    from fastapi.testclient import TestClient
    from main import app

    from database import get_connection

    contact, account = person()
    role = database_rows(
        "SELECT id FROM access_roles WHERE name = 'Global System Administrator'"
    )[0]
    records(
        "user_access_role_assignments",
        user_account_id=account["id"],
        access_role_id=role["id"],
        start_date=date.today(),
    )
    tokens = [session_token(account["id"]), session_token(account["id"])]
    path = f"/api/v1/contacts/{contact['id']}"
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        client.cookies.set("crm_session", tokens[0])
        old = client.get(path).headers["etag"]
    barrier = Barrier(2)

    def synchronized_authorization(
        user=Depends(get_current_user), connection=Depends(get_connection)
    ):
        # Both authentications finish before either PATCH locks the contact row.
        barrier.wait(timeout=5)
        return AuthorizationService(user, connection, load_policy())

    monkeypatch.setitem(
        app.dependency_overrides, get_authorization_service, synchronized_authorization
    )

    def archive(index):
        with TestClient(
            app, client=("127.0.0.1", 50000), raise_server_exceptions=False
        ) as client:
            client.cookies.set("crm_session", tokens[index])
            return client.patch(
                path,
                headers={
                    "Origin": "http://localhost:5173",
                    "X-CRM-CSRF": "1",
                    "If-Match": old,
                },
                json={"status": "archived"},
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(archive, [0, 1]))
    assert sorted(codes) == [200, 412]


def test_contact_openapi_describes_write_contract(writer):
    schema = writer.get("/openapi.json").json()
    paths = schema["paths"]
    create = paths["/api/v1/contacts"]["post"]
    patch = paths["/api/v1/contacts/{contact_id}"]["patch"]
    assert {"201", "401", "403", "409", "415", "422"} <= create["responses"].keys()
    assert {"200", "404", "412", "428", "422"} <= patch["responses"].keys()
    assert "ETag" in create["responses"]["201"]["headers"]
    assert "Location" in create["responses"]["201"]["headers"]
    assert any(
        p["name"] == "if-match" and p["in"] == "header" for p in patch["parameters"]
    )
    model = schema["components"]["schemas"]["ContactPatch"]
    assert model["additionalProperties"] is False
    assert model["properties"]["first_name"]["type"] == "string"
    assert {"type": "null"} in model["properties"]["email"]["anyOf"]
    assert "can_login" not in model["properties"]


def test_contact_database_enforces_normalized_email_uniqueness(records):
    email = f"{uuid4()}@example.org"
    records("contacts", first_name="Existing", last_name="Contact", email=email)
    with psycopg.connect(DATABASE_URL) as connection:
        with pytest.raises(psycopg.errors.UniqueViolation):
            connection.execute(
                "INSERT INTO contacts (first_name, last_name, email) VALUES (%s, %s, %s)",
                ("Duplicate", "Contact", f" {email.upper()} "),
            )
        connection.rollback()


def test_contact_email_migration_fails_on_collisions_and_can_be_repeated():
    from pathlib import Path

    migration = Path(
        "/database/migrations/001_contact_email_uniqueness.sql"
    ).read_text()
    # A temporary contacts table isolates migration testing from the application.
    with psycopg.connect(DATABASE_URL, autocommit=True) as connection:
        connection.execute("CREATE TEMP TABLE contacts (email text)")
        connection.execute(
            "INSERT INTO contacts VALUES ('a@example.org'), (' A@EXAMPLE.ORG ')"
        )
        with pytest.raises(psycopg.errors.UniqueViolation):
            connection.execute(migration)
        connection.execute("ROLLBACK")
        assert connection.execute("SELECT count(*) FROM contacts").fetchone()[0] == 2
        connection.execute("TRUNCATE contacts")
        connection.execute(
            "INSERT INTO contacts VALUES ('a@example.org'), (NULL), (NULL)"
        )
        connection.execute(migration)
        connection.execute(migration)
        with pytest.raises(psycopg.errors.UniqueViolation):
            connection.execute("INSERT INTO contacts VALUES (' A@EXAMPLE.ORG ')")


@pytest.mark.parametrize("header", ["Origin", "X-CRM-CSRF"])
def test_contact_write_requires_security_headers(writer, header):
    del writer.headers[header]
    assert writer.post("/api/v1/contacts", json=payload()).status_code == 403


# --- Group-Leader-exact-group write scope -----------------------------------
# See documents/api-contract.md "Write authorization and CSRF" and
# documents/open-questions.md #4.


def role_type_id(name):
    return database_rows("SELECT id FROM role_types WHERE name = %s", (name,))[0]["id"]


@pytest.fixture
def hierarchy(records):
    group_type = records("group_types", name=f"Write-scope hierarchy {uuid4()}")
    root = records("groups", group_type_id=group_type["id"], name=f"Root {uuid4()}")
    child = records(
        "groups", group_type_id=group_type["id"], name=f"Child {uuid4()}", parent_id=root["id"]
    )
    unrelated = records("groups", group_type_id=group_type["id"], name=f"Unrelated {uuid4()}")
    return root, child, unrelated


@pytest.fixture
def group_leader_writer(callback_client, records, person, session_token):
    """Authenticate the routed client as a fresh Group Leader of the given group."""

    def become_leader_of(group_id):
        leader, account = person()
        records(
            "contact_roles_groups",
            contact_id=leader["id"],
            role_type_id=role_type_id("Group Leader"),
            group_id=group_id,
            start_date=date.today(),
        )
        client, _ = callback_client
        client.cookies.set("crm_session", session_token(account["id"]))
        client.headers.update({"Origin": "http://localhost:5173", "X-CRM-CSRF": "1"})
        return client

    return become_leader_of


def test_group_leader_can_update_a_contact_in_their_exact_group(
    records, person, group_leader_writer, hierarchy
):
    root, _child, _unrelated = hierarchy
    client = group_leader_writer(root["id"])
    member, _ = person()
    records(
        "contact_roles_groups",
        contact_id=member["id"],
        role_type_id=role_type_id("Group Helper"),
        group_id=root["id"],
        start_date=date.today(),
    )

    response = client.patch(
        f"/api/v1/contacts/{member['id']}",
        json={"first_name": "Updated"},
        headers={"If-Match": tag(client, member)},
    )
    assert response.status_code == 200
    assert response.json()["first_name"] == "Updated"


def test_group_leader_can_archive_a_contact_in_their_exact_group(
    records, person, group_leader_writer, hierarchy
):
    """"Full Read/Write/Archive" per open-questions.md #4 - no restricted subset."""
    root, _child, _unrelated = hierarchy
    client = group_leader_writer(root["id"])
    member, _ = person()
    records(
        "contact_roles_groups",
        contact_id=member["id"],
        role_type_id=role_type_id("Group Helper"),
        group_id=root["id"],
        start_date=date.today(),
    )

    response = client.patch(
        f"/api/v1/contacts/{member['id']}",
        json={"status": "archived"},
        headers={"If-Match": tag(client, member)},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "archived"


def test_group_leader_cannot_update_a_contact_in_a_descendant_group(
    records, person, group_leader_writer, hierarchy
):
    root, child, _unrelated = hierarchy
    client = group_leader_writer(root["id"])
    member, _ = person()
    records(
        "contact_roles_groups",
        contact_id=member["id"],
        role_type_id=role_type_id("Group Helper"),
        group_id=child["id"],
        start_date=date.today(),
    )

    # Existing read scope (group_descendants, unchanged) still admits this
    # contact - the point of this test is that write access does not.
    assert client.get(f"/api/v1/contacts/{member['id']}").status_code == 200

    response = client.patch(
        f"/api/v1/contacts/{member['id']}",
        json={"first_name": "Updated"},
        headers={"If-Match": '"placeholder"'},
    )
    assert response.status_code == 403


def test_group_leader_cannot_update_a_contact_in_an_unrelated_group(
    records, person, group_leader_writer, hierarchy
):
    root, _child, unrelated = hierarchy
    client = group_leader_writer(root["id"])
    outsider, _ = person()
    records(
        "contact_roles_groups",
        contact_id=outsider["id"],
        role_type_id=role_type_id("Group Helper"),
        group_id=unrelated["id"],
        start_date=date.today(),
    )

    response = client.patch(
        f"/api/v1/contacts/{outsider['id']}",
        json={"first_name": "Updated"},
        headers={"If-Match": '"placeholder"'},
    )
    assert response.status_code == 403


def test_group_leader_cannot_create_contacts(group_leader_writer, hierarchy):
    root, _child, _unrelated = hierarchy
    client = group_leader_writer(root["id"])

    response = client.post("/api/v1/contacts", json=payload())
    assert response.status_code == 403


@pytest.mark.parametrize("role", ["Area Manager", "Group Helper"])
def test_other_roles_cannot_write_contacts_even_in_their_own_group(
    records, person, session_token, hierarchy, role
):
    root, _child, _unrelated = hierarchy
    holder, holder_account = person()
    records(
        "contact_roles_groups",
        contact_id=holder["id"],
        role_type_id=role_type_id(role),
        group_id=root["id"],
        start_date=date.today(),
    )
    member, _ = person()
    records(
        "contact_roles_groups",
        contact_id=member["id"],
        role_type_id=role_type_id("Group Helper"),
        group_id=root["id"],
        start_date=date.today(),
    )

    with httpx.Client(cookies={"crm_session": session_token(holder_account["id"])}) as client:
        response = client.patch(
            f"{API_URL}/api/v1/contacts/{member['id']}",
            json={"first_name": "Updated"},
            headers={
                "If-Match": '"placeholder"',
                "Origin": "http://localhost:5173",
                "X-CRM-CSRF": "1",
            },
            timeout=5,
        )
    assert response.status_code == 403


# --- Group-role-to-family extension (Prerequisite 3) -------------------------
# See documents/contact-data-expansion-design.md and the "Write authorization
# and CSRF" section's group_and_family note.


def test_group_leader_can_update_a_family_member_of_someone_in_their_group(
    records, person, group_leader_writer, hierarchy
):
    root, _child, _unrelated = hierarchy
    client = group_leader_writer(root["id"])
    member, _ = person()
    records(
        "contact_roles_groups",
        contact_id=member["id"],
        role_type_id=role_type_id("Group Helper"),
        group_id=root["id"],
        start_date=date.today(),
    )
    family = records("family_units", id=uuid4())
    records(
        "contact_family_units",
        contact_id=member["id"],
        family_unit_id=family["id"],
        relationship="child",
    )
    parent, _ = person()
    records(
        "contact_family_units",
        contact_id=parent["id"],
        family_unit_id=family["id"],
        relationship="parent",
    )

    response = client.patch(
        f"/api/v1/contacts/{parent['id']}",
        json={"first_name": "Updated"},
        headers={"If-Match": tag(client, parent)},
    )
    assert response.status_code == 200
    assert response.json()["first_name"] == "Updated"


def test_group_leader_can_update_a_non_parent_family_member_too(
    records, person, group_leader_writer, hierarchy
):
    """"Family members", not just parents - any contact_family_units row."""
    root, _child, _unrelated = hierarchy
    client = group_leader_writer(root["id"])
    member, _ = person()
    records(
        "contact_roles_groups",
        contact_id=member["id"],
        role_type_id=role_type_id("Group Helper"),
        group_id=root["id"],
        start_date=date.today(),
    )
    family = records("family_units", id=uuid4())
    records(
        "contact_family_units",
        contact_id=member["id"],
        family_unit_id=family["id"],
        relationship="child",
    )
    guardian, _ = person()
    records(
        "contact_family_units",
        contact_id=guardian["id"],
        family_unit_id=family["id"],
        relationship="guardian",
    )

    response = client.patch(
        f"/api/v1/contacts/{guardian['id']}",
        json={"first_name": "Updated"},
        headers={"If-Match": tag(client, guardian)},
    )
    assert response.status_code == 200


def test_group_leader_cannot_update_a_family_member_of_an_unrelated_contact(
    records, person, group_leader_writer, hierarchy
):
    root, _child, unrelated = hierarchy
    client = group_leader_writer(root["id"])
    outsider, _ = person()
    records(
        "contact_roles_groups",
        contact_id=outsider["id"],
        role_type_id=role_type_id("Group Helper"),
        group_id=unrelated["id"],
        start_date=date.today(),
    )
    family = records("family_units", id=uuid4())
    records(
        "contact_family_units",
        contact_id=outsider["id"],
        family_unit_id=family["id"],
        relationship="child",
    )
    outsiders_parent, _ = person()
    records(
        "contact_family_units",
        contact_id=outsiders_parent["id"],
        family_unit_id=family["id"],
        relationship="parent",
    )

    response = client.patch(
        f"/api/v1/contacts/{outsiders_parent['id']}",
        json={"first_name": "Updated"},
        headers={"If-Match": '"placeholder"'},
    )
    assert response.status_code == 403
