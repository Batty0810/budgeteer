from tests.conftest import login


def test_member_cannot_access_admin_users(client, member_user):
    login(client, member_user.email)
    resp = client.get("/admin/users")
    assert resp.status_code == 403


def test_admin_can_view_and_create_users(client, admin_user, household):
    login(client, admin_user.email)
    resp = client.get("/admin/users")
    assert resp.status_code == 200

    resp = client.post(
        "/admin/users/new",
        data={
            "display_name": "New Person",
            "email": "newperson@example.com",
            "password": "supersecret1",
            "role": "member",
            "color": "#00d4ff",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"New Person" in resp.data

    # The new login actually works.
    resp = login(client, "newperson@example.com", password="supersecret1")
    assert b"Dashboard" in resp.data


def test_admin_cannot_deactivate_their_own_account(client, admin_user):
    login(client, admin_user.email)
    resp = client.post(f"/admin/users/{admin_user.id}/toggle-active", follow_redirects=True)
    assert b"can&#39;t deactivate your own account" in resp.data or b"can't deactivate your own account" in resp.data
