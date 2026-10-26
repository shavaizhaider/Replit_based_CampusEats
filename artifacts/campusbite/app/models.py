from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import CheckConstraint, Index, UniqueConstraint
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Admin(db.Model):
    __tablename__ = "admins"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True, index=True)
    description = db.Column(db.String(240), nullable=False, default="")
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    foods = db.relationship("FoodItem", back_populates="category", lazy="selectin")

    @property
    def food_count(self) -> int:
        return len(self.foods)


class FoodItem(db.Model):
    __tablename__ = "food_items"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False, default="")
    category_id = db.Column(
        db.Integer,
        db.ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    default_price = db.Column(db.Numeric(10, 2), nullable=False)
    image_path = db.Column(db.String(500), nullable=True)
    ingredients = db.Column(db.Text, nullable=False, default="")
    allergen_notes = db.Column(db.String(500), nullable=False, default="")
    is_vegetarian = db.Column(db.Boolean, nullable=False, default=False)
    spice_level = db.Column(db.String(16), nullable=False, default="mild")
    dietary_tags = db.Column(db.JSON, nullable=False, default=list)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    category = db.relationship("Category", back_populates="foods")
    schedules = db.relationship("MenuSchedule", back_populates="food")
    reviews = db.relationship("Review", back_populates="food", lazy="selectin")

    @property
    def price(self) -> Decimal:
        return Decimal(self.default_price)

    @price.setter
    def price(self, value: Decimal) -> None:
        self.default_price = value

    @property
    def image_url(self) -> str | None:
        return self.image_path

    @image_url.setter
    def image_url(self, value: str | None) -> None:
        self.image_path = value

    @property
    def allergens(self) -> str:
        return self.allergen_notes

    @allergens.setter
    def allergens(self, value: str) -> None:
        self.allergen_notes = value

    @property
    def is_vegan(self) -> bool:
        return "vegan" in (self.dietary_tags or [])

    @is_vegan.setter
    def is_vegan(self, value: bool) -> None:
        tags = list(self.dietary_tags or [])
        if value and "vegan" not in tags:
            tags.append("vegan")
        if not value:
            tags = [tag for tag in tags if tag != "vegan"]
        self.dietary_tags = tags

    @property
    def avg_rating(self) -> float | None:
        visible = [review.rating for review in self.reviews if not review.is_hidden]
        return round(sum(visible) / len(visible), 1) if visible else None

    @property
    def review_count(self) -> int:
        return sum(1 for review in self.reviews if not review.is_hidden)


class MenuSchedule(db.Model):
    __tablename__ = "menu_schedules"
    __table_args__ = (
        UniqueConstraint(
            "food_item_id", "menu_date", "meal_type", name="uq_schedule_food_date_meal"
        ),
        CheckConstraint("quantity_available >= 0", name="ck_schedule_nonnegative_stock"),
        Index("ix_schedule_date_meal", "menu_date", "meal_type"),
    )

    id = db.Column(db.Integer, primary_key=True)
    food_item_id = db.Column(
        db.Integer,
        db.ForeignKey("food_items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    menu_date = db.Column(db.Date, nullable=False)
    meal_type = db.Column(db.String(24), nullable=False)
    serving_start = db.Column(db.Time, nullable=False)
    serving_end = db.Column(db.Time, nullable=False)
    scheduled_price = db.Column(db.Numeric(10, 2), nullable=True)
    quantity_available = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    food = db.relationship("FoodItem", back_populates="schedules")

    @property
    def price(self) -> Decimal:
        return self.effective_price

    @property
    def stock(self) -> int:
        return self.quantity_available

    @stock.setter
    def stock(self, value: int) -> None:
        self.quantity_available = value

    @property
    def meal(self) -> str:
        return self.meal_type

    @meal.setter
    def meal(self, value: str) -> None:
        self.meal_type = value

    @property
    def date(self):
        return self.menu_date

    @date.setter
    def date(self, value):
        self.menu_date = value

    @property
    def start_time(self):
        return self.serving_start

    @start_time.setter
    def start_time(self, value):
        self.serving_start = value

    @property
    def end_time(self):
        return self.serving_end

    @end_time.setter
    def end_time(self, value):
        self.serving_end = value

    @property
    def is_available(self) -> bool:
        return self.quantity_available > 0

    @is_available.setter
    def is_available(self, value: bool) -> None:
        if not value:
            self.quantity_available = 0

    @property
    def effective_price(self) -> Decimal:
        return Decimal(self.scheduled_price or self.food.default_price)

    @property
    def stock_status(self) -> str:
        threshold = 5
        try:
            from flask import current_app

            threshold = current_app.config.get("LOW_STOCK_THRESHOLD", threshold)
        except RuntimeError:
            pass
        if self.quantity_available <= 0:
            return "Sold Out"
        if self.quantity_available <= threshold:
            return "Low Stock"
        return "Available"

    @property
    def availability_label(self) -> str:
        if self.quantity_available <= 0:
            return "Sold Out"
        campus_zone = ZoneInfo("Asia/Karachi")
        now = datetime.now(campus_zone)
        if self.menu_date > now.date():
            return "Scheduled"
        if self.menu_date < now.date():
            return "Not serving now"
        local_time = now.time().replace(tzinfo=None)
        if self.serving_start <= local_time <= self.serving_end:
            return "Available now"
        return "Outside serving hours"


class Review(db.Model):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint(
            "food_item_id", "device_hash", name="uq_review_food_device"
        ),
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_review_rating_range"),
        Index("ix_reviews_food_hidden_created", "food_item_id", "is_hidden", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    food_item_id = db.Column(
        db.Integer,
        db.ForeignKey("food_items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    rating = db.Column(db.Integer, nullable=False)
    review_text = db.Column(db.String(300), nullable=True)
    reviewer_name = db.Column(db.String(80), nullable=True)
    device_hash = db.Column(db.String(64), nullable=False)
    is_hidden = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    food = db.relationship("FoodItem", back_populates="reviews")

    @property
    def comment(self) -> str | None:
        return self.review_text

    @property
    def student_name(self) -> str | None:
        return self.reviewer_name

    @property
    def is_approved(self) -> bool:
        return not self.is_hidden

    @property
    def is_visible(self) -> bool:
        return not self.is_hidden
