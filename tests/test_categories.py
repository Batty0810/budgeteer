from tests.conftest import login
from app.models.category import DEFAULT_CATEGORY_COLORS
from app.utils.charts import next_category_color


def test_next_category_color_cycles_through_the_validated_palette():
    colors = [next_category_color(i) for i in range(len(DEFAULT_CATEGORY_COLORS) + 2)]
    assert colors[: len(DEFAULT_CATEGORY_COLORS)] == DEFAULT_CATEGORY_COLORS
    # Wraps back to the start rather than inventing a new hue.
    assert colors[len(DEFAULT_CATEGORY_COLORS)] == DEFAULT_CATEGORY_COLORS[0]


def test_new_category_gets_the_next_colour_in_sequence(client, member_user, household, groceries_category):
    login(client, member_user.email)
    resp = client.post(
        "/transactions/categories/new",
        data={"name": "Transport", "type": "expense", "monthly_budget": "", "color": DEFAULT_CATEGORY_COLORS[1]},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Transport" in resp.data


def test_categories_are_reachable_from_the_admin_page(client, admin_user):
    login(client, admin_user.email)
    resp = client.get("/admin/users")
    assert resp.status_code == 200
    assert b'href="/transactions/categories"' in resp.data

    resp = client.get("/transactions/categories")
    assert resp.status_code == 200
    assert b'href="/admin/users"' in resp.data  # the tab back to Users is present for an admin


def test_a_regular_member_can_still_manage_categories_without_seeing_the_admin_tabs(client, member_user, groceries_category):
    login(client, member_user.email)
    resp = client.get("/transactions/categories")
    assert resp.status_code == 200
    assert b"Groceries" in resp.data
    assert b'href="/admin/users"' not in resp.data  # not an admin, so no dangling link to a 403
