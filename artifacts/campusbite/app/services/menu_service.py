from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from ..extensions import db
from ..models import FoodItem, MenuSchedule

MEAL_TYPES = ("Breakfast", "Lunch", "Evening/Dinner")
DIETARY_TAGS = ("dairy-free", "egg-free", "gluten-free", "vegan")


def menu_schedules_for(
    menu_date: date, meal_type: str, filters: dict | None = None
) -> list[MenuSchedule]:
    filters = filters or {}
    statement = (
        select(MenuSchedule)
        .join(MenuSchedule.food)
        .where(
            MenuSchedule.menu_date == menu_date,
            MenuSchedule.meal_type == meal_type,
            FoodItem.is_active.is_(True),
        )
        .options(
            joinedload(MenuSchedule.food).joinedload(FoodItem.category),
            joinedload(MenuSchedule.food).selectinload(FoodItem.reviews),
        )
    )
    schedules = list(db.session.scalars(statement).unique().all())
    query = str(filters.get("q", "")).strip().casefold()
    category_id = filters.get("category_id")
    vegetarian = filters.get("vegetarian")
    non_vegetarian = filters.get("non_vegetarian")
    available_only = filters.get("available_only")
    spice_level = filters.get("spice_level")
    dietary_tag = filters.get("dietary_tag")
    budget = filters.get("budget")

    def matches(schedule: MenuSchedule) -> bool:
        food = schedule.food
        if query and query not in food.name.casefold() and query not in food.description.casefold():
            return False
        if category_id and food.category_id != category_id:
            return False
        if vegetarian and not food.is_vegetarian:
            return False
        if non_vegetarian and food.is_vegetarian:
            return False
        if (available_only or budget is not None) and schedule.availability_label != "Available now":
            return False
        if spice_level and food.spice_level != spice_level:
            return False
        if dietary_tag and dietary_tag not in (food.dietary_tags or []):
            return False
        if budget is not None and schedule.effective_price > Decimal(budget):
            return False
        return True

    schedules = [schedule for schedule in schedules if matches(schedule)]
    sort_by = filters.get("sort", "price-asc")
    schedules.sort(
        key=lambda schedule: (
            schedule.effective_price,
            schedule.food.name.casefold(),
        ),
        reverse=sort_by == "price-desc",
    )
    return schedules


def schedules_between(start: date, end: date) -> list[MenuSchedule]:
    statement = (
        select(MenuSchedule)
        .join(MenuSchedule.food)
        .where(
            MenuSchedule.menu_date >= start,
            MenuSchedule.menu_date <= end,
            FoodItem.is_active.is_(True),
        )
        .options(
            joinedload(MenuSchedule.food).joinedload(FoodItem.category),
            joinedload(MenuSchedule.food).selectinload(FoodItem.reviews),
        )
        .order_by(MenuSchedule.menu_date, MenuSchedule.meal_type, FoodItem.name)
    )
    return list(db.session.scalars(statement).unique().all())


def available_dietary_tags() -> tuple[str, ...]:
    tags = set(DIETARY_TAGS)
    statement = select(FoodItem.dietary_tags).where(FoodItem.is_active.is_(True))
    for values in db.session.scalars(statement).all():
        tags.update(tag for tag in (values or []) if isinstance(tag, str))
    return tuple(sorted(tags))
