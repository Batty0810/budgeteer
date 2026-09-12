from tests.conftest import login


def test_dashboard_redirects_to_login_when_anonymous(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_login_with_wrong_password_shows_error(client, member_user):
    resp = login(client, member_user.email, password="wrong-password")
    assert resp.status_code == 200
    assert b"Incorrect email or password" in resp.data


def test_login_with_correct_password_reaches_dashboard(client, member_user):
    resp = login(client, member_user.email)
    assert resp.status_code == 200
    assert b"Dashboard" in resp.data


def test_deactivated_user_cannot_log_in(client, member_user, db):
    member_user.is_active_flag = False
    db.session.commit()
    resp = login(client, member_user.email)
    assert b"deactivated" in resp.data
