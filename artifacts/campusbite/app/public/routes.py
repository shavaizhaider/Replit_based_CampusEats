from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    make_response,
    render_template,
    request,
    send_from_directory,
)
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from ..extensions import db
from ..models import Category, FoodItem, MenuSchedule, Review
from ..services.menu_service import (
    MEAL_TYPES,
    available_dietary_tags,
    menu_schedules_for,
    schedules_between,
)
from ..services.stock_service import stock_label

public_bp = Blueprint("public", __name__)
CAMPUS_ZONE = ZoneInfo("Asia/Karachi")


def campus_today() -> date:
    return datetime.now(CAMPUS_ZONE).date()


def selected_date(value: str | None) -> tuple[date, str | None]:
    if not value:
        return campus_today(), None
    try:
        return date.fromisoformat(value), None
    except ValueError:
        return campus_today(), "Choose a valid calendar date."


def active_categories() -> list[Category]:
    return list(
        db.session.scalars(
            select(Category)
            .where(Category.is_active.is_(True))
            .order_by(Category.sort_order, Category.name)
        ).all()
    )


@public_bp.get("/")
def index():
    today = campus_today()
    featured = menu_schedules_for(today, "Lunch")
    if not featured:
        next_schedule = db.session.scalar(
            select(MenuSchedule.menu_date)
            .join(MenuSchedule.food)
            .where(
                MenuSchedule.menu_date >= today,
                FoodItem.is_active.is_(True),
            )
            .order_by(MenuSchedule.menu_date)
            .limit(1)
        )
        if next_schedule:
            featured = menu_schedules_for(next_schedule, "Lunch")
    return render_template(
        "index.html",
        featured=featured,
        meals=MEAL_TYPES,
        categories=active_categories(),
        today=today,
    )


@public_bp.get("/menu")
def menu():
    day, error = selected_date(request.args.get("date"))
    meal = request.args.get("meal", "Lunch")
    if meal not in MEAL_TYPES:
        meal = "Lunch"
        error = error or "Choose Breakfast, Lunch, or Evening/Dinner."

    raw_category = request.args.get("category", "").strip()
    category_id = None
    if raw_category:
        try:
            category_id = int(raw_category)
            if category_id < 1:
                raise ValueError
        except ValueError:
            error = error or "Choose a valid food category."

    raw_budget = request.args.get("budget", "").strip()
    budget = None
    if raw_budget:
        try:
            budget = Decimal(raw_budget)
            if not budget.is_finite() or budget <= 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            error = error or "Enter a valid budget greater than Rs. 0."
            budget = None

    vegetarian = request.args.get("vegetarian") == "1"
    non_vegetarian = request.args.get("non_vegetarian") == "1"
    if vegetarian and non_vegetarian:
        error = error or "Choose either vegetarian or non-vegetarian."
        vegetarian = False
        non_vegetarian = False

    spice_level = request.args.get("spice", "").strip()
    if spice_level not in ("", "mild", "medium", "hot"):
        spice_level = ""
        error = error or "Choose a supported spice level."
    dietary_tag = request.args.get("dietary", "").strip().lower()
    dietary_tags = available_dietary_tags()
    if dietary_tag not in dietary_tags:
        dietary_tag = ""
        if request.args.get("dietary"):
            error = error or "Choose a supported dietary preference."
    sort = request.args.get("sort", "price-asc")
    if sort not in ("price-asc", "price-desc"):
        sort = "price-asc"

    filters = {
        "q": request.args.get("q", "").strip()[:100],
        "category_id": category_id,
        "available_only": request.args.get("available") == "1",
        "vegetarian": vegetarian,
        "non_vegetarian": non_vegetarian,
        "spice_level": spice_level,
        "dietary_tag": dietary_tag,
        "budget": budget,
        "sort": sort,
    }
    schedules = menu_schedules_for(day, meal, filters)
    response = make_response(
        render_template(
            "menu.html",
            menu=schedules,
            schedules=schedules,
            selected_date=day,
            selected_meal=meal,
            selected_category=category_id,
            categories=active_categories(),
            meals=MEAL_TYPES,
            filters=filters,
            dietary_tags=dietary_tags,
            error=error,
            updated_at=datetime.now(CAMPUS_ZONE),
        )
    )
    response.headers.setdefault("Cache-Control", "public, max-age=0, must-revalidate")
    return response


@public_bp.get("/weekly-menu")
def weekly_menu():
    selected, error = selected_date(request.args.get("date"))
    week_start = selected - timedelta(days=selected.weekday())
    week_end = week_start + timedelta(days=6)
    schedules = schedules_between(week_start, week_end)
    grouped: dict[date, dict[str, list[MenuSchedule]]] = defaultdict(
        lambda: {meal: [] for meal in MEAL_TYPES}
    )
    for schedule in schedules:
        grouped[schedule.menu_date][schedule.meal_type].append(schedule)
    days = [
        {"date": week_start + timedelta(days=offset), "meals": grouped[week_start + timedelta(days=offset)]}
        for offset in range(7)
    ]
    return render_template(
        "weekly_menu.html",
        days=days,
        meals=MEAL_TYPES,
        selected_date=selected,
        week_start=week_start,
        week_end=week_end,
        previous_week=week_start - timedelta(days=7),
        next_week=week_start + timedelta(days=7),
        today=campus_today(),
        error=error,
    )


@public_bp.get("/food/<int:id>")
def food_detail(id: int):
    statement = (
        select(FoodItem)
        .where(FoodItem.id == id, FoodItem.is_active.is_(True))
        .options(
            joinedload(FoodItem.category),
            selectinload(FoodItem.reviews),
            selectinload(FoodItem.schedules),
        )
    )
    food = db.session.scalar(statement)
    if food is None:
        abort(404)
    today = campus_today()
    schedules = list(
        db.session.scalars(
            select(MenuSchedule)
            .where(MenuSchedule.food_item_id == id, MenuSchedule.menu_date >= today)
            .order_by(MenuSchedule.menu_date, MenuSchedule.serving_start)
            .limit(14)
        ).all()
    )
    reviews = list(
        db.session.scalars(
            select(Review)
            .where(Review.food_item_id == id, Review.is_hidden.is_(False))
            .order_by(Review.created_at.desc())
            .limit(10)
        ).all()
    )
    return render_template(
        "food_detail.html",
        food=food,
        schedules=schedules,
        reviews=reviews,
        avg_rating=food.avg_rating,
        review_count=food.review_count,
        meals=MEAL_TYPES,
        form_values={},
    )


@public_bp.get("/api/menu/availability")
def availability():
    day, error = selected_date(request.args.get("date"))
    meal = request.args.get("meal", "")
    if error or meal not in MEAL_TYPES:
        return jsonify(error="Provide a valid date and meal."), 400

    schedules = menu_schedules_for(day, meal)
    payload = {
        "date": day.isoformat(),
        "meal": meal,
        "updated_at": datetime.now(CAMPUS_ZONE).isoformat(),
        "items": [
            {
                "schedule_id": schedule.id,
                "food_id": schedule.food.id,
                "quantity": schedule.quantity_available,
                "stock_status": stock_label(
                    schedule.quantity_available,
                    current_app.config["LOW_STOCK_THRESHOLD"],
                ),
                "availability": schedule.availability_label,
                "updated_at": (
                    schedule.updated_at.isoformat() if schedule.updated_at else None
                ),
            }
            for schedule in schedules
        ],
    }
    response = jsonify(payload)
    response.headers["Cache-Control"] = "no-store"
    return response


@public_bp.get("/offline")
def offline():
    return render_template("offline.html")


@public_bp.get("/service-worker.js")
def service_worker():
    response = make_response(
        send_from_directory(current_app.static_folder, "service-worker.js")
    )
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache"
    return response


@public_bp.get("/healthz")
def health_check():
    return jsonify(status="ok")
