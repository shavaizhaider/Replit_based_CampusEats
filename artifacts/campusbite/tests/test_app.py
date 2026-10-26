from datetime import time, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.extensions import db
from app.models import Admin, FoodItem, MenuSchedule, Review
from app.public.routes import campus_today


def test_public_pages_and_menu_filters(client, app, sample_records):
    assert client.get("/").status_code == 200
    response = client.get(
        f"/menu?date={sample_records['today']}&meal=Lunch&budget=200&vegetarian=1&available=1"
    )
    assert response.status_code == 200
    assert b"Daal Chawal" in response.data
    assert b"Chicken Biryani" not in response.data
    assert client.get("/weekly-menu").status_code == 200
    assert client.get(f"/food/{sample_records['vegetarian_id']}").status_code == 200


def test_live_availability_endpoint_returns_saved_stock(client, sample_records):
    response = client.get(
        f"/api/menu/availability?date={sample_records['today']}&meal=Lunch"
    )
    assert response.status_code == 200
    items = {item["food_id"]: item for item in response.json["items"]}
    assert items[sample_records["vegetarian_id"]]["quantity"] == 5
    assert items[sample_records["vegetarian_id"]]["stock_status"] == "Low Stock"
    assert items[sample_records["vegetarian_id"]]["availability"] == "Available now"
    assert items[sample_records["chicken_id"]]["availability"] == "Sold Out"
    assert client.get("/api/menu/availability?date=bad&meal=Lunch").status_code == 400


def test_bad_budget_is_rejected_and_empty_state_is_helpful(client, sample_records):
    response = client.get(f"/menu?date={sample_records['today']}&meal=Lunch&budget=0")
    assert response.status_code == 200
    assert b"Enter a valid budget greater than Rs. 0." in response.data

    empty = client.get(
        f"/menu?date={sample_records['today']}&meal=Breakfast&budget=150"
    )
    assert b"No matching food found within your budget." in empty.data


def test_admin_authentication_and_login_hash(app, client, sample_records):
    protected = client.get("/admin/dashboard")
    assert protected.status_code == 302
    assert "/admin/login" in protected.headers["Location"]

    bad_login = client.post(
        "/admin/login",
        data={"username": "campus-admin", "password": "incorrect-password"},
    )
    assert bad_login.status_code == 200
    assert b"Invalid username or password." in bad_login.data

    assert client.post(
        "/admin/login",
        data={"username": "campus-admin", "password": "correct-horse-battery"},
    ).status_code == 302
    assert client.get("/admin/dashboard").status_code == 200
    with app.app_context():
        admin = db.session.scalar(select(Admin).where(Admin.username == "campus-admin"))
        assert admin is not None
        assert admin.password_hash != "correct-horse-battery"
        assert admin.check_password("correct-horse-battery")


def test_stock_updates_are_persisted_and_negative_values_rejected(
    app, client, sample_records
):
    client.post(
        "/admin/login",
        data={"username": "campus-admin", "password": "correct-horse-battery"},
    )
    response = client.post(
        f"/admin/stock/{sample_records['daal_schedule_id']}",
        data={"stock": "0"},
    )
    assert response.status_code == 302
    with app.app_context():
        schedule = db.session.get(MenuSchedule, sample_records["daal_schedule_id"])
        assert schedule.quantity_available == 0
        updated_at = schedule.updated_at

    client.post(
        f"/admin/stock/{sample_records['daal_schedule_id']}",
        data={"stock": "-1"},
    )
    with app.app_context():
        schedule = db.session.get(MenuSchedule, sample_records["daal_schedule_id"])
        assert schedule.quantity_available == 0
        assert schedule.updated_at >= updated_at


def test_reviews_validate_and_limit_repeat_submissions(app, client, sample_records):
    food_id = sample_records["vegetarian_id"]
    bad = client.post(f"/food/{food_id}/reviews", data={"rating": "6"})
    assert bad.status_code == 400

    posted = client.post(
        f"/food/{food_id}/reviews",
        data={"rating": "5", "comment": "", "student_name": ""},
        follow_redirects=True,
    )
    assert posted.status_code == 200
    assert b"Thank you! Your rating has been submitted." in posted.data
    repeated = client.post(
        f"/food/{food_id}/reviews",
        data={"rating": "4", "comment": "again"},
    )
    assert repeated.status_code == 400
    with app.app_context():
        count = db.session.scalar(
            select(func.count(Review.id)).where(Review.food_item_id == food_id)
        )
        assert count == 1


def test_hidden_review_does_not_affect_public_rating(app, client, sample_records):
    food_id = sample_records["vegetarian_id"]
    with app.app_context():
        from app.models import Review

        db.session.add_all(
            [
                Review(
                    food_item_id=food_id,
                    rating=5,
                    review_text="Visible",
                    device_hash="visible-device",
                ),
                Review(
                    food_item_id=food_id,
                    rating=1,
                    review_text="Hidden",
                    device_hash="hidden-device",
                    is_hidden=True,
                ),
            ]
        )
        db.session.commit()
    response = client.get(f"/food/{food_id}")
    assert b"Visible" in response.data
    assert b"Hidden" not in response.data
    assert b"5.0" in response.data


def test_staff_can_hide_and_restore_reviews(app, client, sample_records):
    with app.app_context():
        review = Review(
            food_item_id=sample_records["vegetarian_id"],
            rating=2,
            review_text="A moderation test note.",
            device_hash="moderation-test-device",
        )
        db.session.add(review)
        db.session.commit()
        review_id = review.id

    client.post(
        "/admin/login",
        data={"username": "campus-admin", "password": "correct-horse-battery"},
    )
    assert client.post(
        f"/admin/reviews/{review_id}/moderate",
        data={"is_approved": "0"},
    ).status_code == 302
    with app.app_context():
        assert db.session.get(Review, review_id).is_hidden
    hidden_page = client.get(f"/food/{sample_records['vegetarian_id']}")
    assert b"A moderation test note." not in hidden_page.data
    assert b"No reviews yet" in hidden_page.data or b"First review gets bragging rights." in hidden_page.data

    assert client.post(
        f"/admin/reviews/{review_id}/moderate",
        data={"is_approved": "1"},
    ).status_code == 302
    visible_page = client.get(f"/food/{sample_records['vegetarian_id']}")
    assert b"A moderation test note." in visible_page.data
    assert b"2.0" in visible_page.data


def test_schedule_quantity_is_independent_by_occurrence(app, sample_records):
    with app.app_context():
        food = db.session.get(FoodItem, sample_records["vegetarian_id"])
        second = MenuSchedule(
            food_item_id=food.id,
            menu_date=campus_today() + timedelta(days=1),
            meal_type="Lunch",
            serving_start=time(12, 0),
            serving_end=time(15, 0),
            quantity_available=11,
        )
        db.session.add(second)
        db.session.commit()
        original = db.session.get(MenuSchedule, sample_records["daal_schedule_id"])
        original.quantity_available = 2
        db.session.commit()
        assert second.quantity_available == 11
        assert Decimal(str(original.effective_price)) == Decimal("180.00")


def test_admin_pages_food_and_schedule_creation(app, client, sample_records):
    client.post(
        "/admin/login",
        data={"username": "campus-admin", "password": "correct-horse-battery"},
    )
    for path in (
        "/admin/foods",
        "/admin/foods/new",
        "/admin/categories",
        "/admin/categories/new",
        "/admin/schedules",
        "/admin/schedules/new",
        "/admin/stock",
        "/admin/reviews",
    ):
        assert client.get(path).status_code == 200, path

    created_food = client.post(
        "/admin/foods/new",
        data={
            "name": "Campus Toast",
            "category_id": str(sample_records["category_id"]),
            "price": "125.50",
            "description": "Toast for a test.",
            "ingredients": "Bread",
            "allergens": "Contains wheat.",
            "spice_level": "none",
            "dietary_tags": "vegetarian",
            "is_vegetarian": "1",
            "is_active": "1",
        },
    )
    assert created_food.status_code == 302
    with app.app_context():
        food = db.session.scalar(select(FoodItem).where(FoodItem.name == "Campus Toast"))
        assert food is not None
        food_id = food.id

    tomorrow = (campus_today() + timedelta(days=1)).isoformat()
    created_schedule = client.post(
        "/admin/schedules/new",
        data={
            "food_id": str(food_id),
            "date": tomorrow,
            "meal": "Lunch",
            "start_time": "12:00",
            "end_time": "15:00",
            "price": "",
            "stock": "4",
        },
    )
    assert created_schedule.status_code == 302
    with app.app_context():
        schedule = db.session.scalar(
            select(MenuSchedule).where(MenuSchedule.food_item_id == food_id)
        )
        assert schedule is not None
        assert schedule.quantity_available == 4
        assert schedule.scheduled_price is None


def test_manifest_and_private_cache_headers(client):
    manifest = client.get("/static/manifest.json")
    assert manifest.status_code == 200
    assert manifest.json["display"] == "standalone"
    assert client.get("/service-worker.js").headers["Service-Worker-Allowed"] == "/"
    login = client.get("/admin/login")
    assert "no-store" in login.headers["Cache-Control"]


def test_csrf_is_enabled_for_state_changes(tmp_path):
    from app import create_app
    from app.extensions import db

    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "csrf-test-key",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'csrf.sqlite'}",
            "WTF_CSRF_ENABLED": True,
            "RATELIMIT_ENABLED": False,
        }
    )
    with app.app_context():
        db.create_all()
    response = app.test_client().post("/admin/login", data={"username": "x", "password": "y"})
    assert response.status_code == 400
