from datetime import time
from decimal import Decimal
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from app.extensions import db
from app.models import Admin, Category, FoodItem, MenuSchedule
from app.public.routes import campus_today


@pytest.fixture
def app(tmp_path):
    database_path = tmp_path / "campusbite-test.sqlite"
    application = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-only-key",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path}",
            "WTF_CSRF_ENABLED": False,
            "RATELIMIT_ENABLED": False,
            "SESSION_COOKIE_SECURE": False,
        }
    )
    with application.app_context():
        db.create_all()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def sample_records(app):
    with app.app_context():
        category = Category(name="Desi Food", description="Campus dishes")
        db.session.add(category)
        db.session.flush()
        vegetarian = FoodItem(
            name="Daal Chawal",
            description="Lentils with rice",
            category_id=category.id,
            default_price=Decimal("180.00"),
            ingredients="Lentils, rice",
            is_vegetarian=True,
            spice_level="mild",
            dietary_tags=["vegan"],
        )
        chicken = FoodItem(
            name="Chicken Biryani",
            description="Rice and chicken",
            category_id=category.id,
            default_price=Decimal("350.00"),
            ingredients="Rice, chicken",
            is_vegetarian=False,
            spice_level="medium",
            dietary_tags=[],
        )
        db.session.add_all([vegetarian, chicken])
        db.session.flush()
        today = campus_today()
        daal_schedule = MenuSchedule(
            food_item_id=vegetarian.id,
            menu_date=today,
            meal_type="Lunch",
            serving_start=time(0, 0),
            serving_end=time(23, 59),
            quantity_available=5,
        )
        chicken_schedule = MenuSchedule(
            food_item_id=chicken.id,
            menu_date=today,
            meal_type="Lunch",
            serving_start=time(0, 0),
            serving_end=time(23, 59),
            quantity_available=0,
        )
        db.session.add_all([daal_schedule, chicken_schedule])
        admin = Admin(username="campus-admin")
        admin.set_password("correct-horse-battery")
        db.session.add(admin)
        db.session.commit()
        return {
            "category_id": category.id,
            "vegetarian_id": vegetarian.id,
            "chicken_id": chicken.id,
            "daal_schedule_id": daal_schedule.id,
            "chicken_schedule_id": chicken_schedule.id,
            "today": today.isoformat(),
        }
