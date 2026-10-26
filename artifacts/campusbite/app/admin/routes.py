import re
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from functools import wraps
from urllib.parse import urlsplit

from flask import (
    Blueprint,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from ..extensions import db, limiter
from ..models import Admin, Category, FoodItem, MenuSchedule, Review, utc_now
from ..public.routes import campus_today
from ..services.menu_service import DIETARY_TAGS, MEAL_TYPES
from ..services.stock_service import stock_label, update_schedule_stock

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
SPICE_LEVELS = ("none", "mild", "medium", "hot")


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not getattr(g, "current_admin", None):
            session.clear()
            flash("Please sign in to open the kitchen desk.", "error")
            return redirect(url_for("admin.login"))
        return view(*args, **kwargs)

    return wrapped


def _parse_integer(value: str, label: str, minimum: int = 0) -> int:
    value = value.strip()
    if not re.fullmatch(r"-?\d+", value):
        raise ValueError(f"{label} must be a whole number.")
    number = int(value)
    if number < minimum:
        raise ValueError(f"{label} cannot be less than {minimum}.")
    return number


def _parse_price(value: str, label: str, required: bool = True) -> Decimal | None:
    value = value.strip()
    if not value and not required:
        return None
    try:
        price = Decimal(value)
    except (InvalidOperation, ValueError):
        raise ValueError(f"{label} must be a valid amount in PKR.") from None
    if not price.is_finite() or price <= 0 or price > Decimal("999999.99"):
        raise ValueError(f"{label} must be greater than Rs. 0.")
    return price.quantize(Decimal("0.01"))


def _food_form_context(food=None, form_values=None, error=None):
    category_statement = select(Category).where(
        or_(Category.is_active.is_(True), Category.id == getattr(food, "category_id", -1))
    ).order_by(Category.sort_order, Category.name)
    return render_template(
        "admin/food_form.html",
        food=food,
        categories=list(db.session.scalars(category_statement).all()),
        dietary_tags=DIETARY_TAGS,
        spice_levels=SPICE_LEVELS,
        form_values=form_values or {},
        error=error,
    )


def _food_values(form, existing_food=None) -> dict:
    name = form.get("name", "").strip()
    if not name:
        raise ValueError("Dish name is required.")
    if len(name) > 120:
        raise ValueError("Dish name must be 120 characters or fewer.")

    try:
        category_id = _parse_integer(form.get("category_id", ""), "Category", 1)
    except ValueError:
        raise ValueError("Choose an existing category.") from None
    category = db.session.get(Category, category_id)
    if category is None or (
        not category.is_active
        and (existing_food is None or existing_food.category_id != category_id)
    ):
        raise ValueError("Choose an existing category.")

    price = _parse_price(form.get("price", ""), "Price")
    image_url = form.get("image_url", form.get("image_path", "")).strip()
    if image_url:
        parsed = urlsplit(image_url)
        safe_local = (
            image_url.startswith("/static/")
            and not image_url.startswith("//")
            and ".." not in parsed.path.split("/")
        )
        safe_remote = (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
        )
        if not (safe_local or safe_remote) or len(image_url) > 500:
            raise ValueError("Use a local /static/ image path or a valid HTTPS image URL.")

    spice_level = form.get("spice_level", "mild").strip()
    if spice_level not in SPICE_LEVELS:
        raise ValueError("Choose a supported spice level.")

    raw_tags = form.get("dietary_tags", "").strip()
    dietary_tags = []
    for item in raw_tags.split(","):
        tag = item.strip().lower()
        if not tag:
            continue
        if len(tag) > 32 or not re.fullmatch(r"[a-z0-9]+(?:[ -][a-z0-9]+)*", tag):
            raise ValueError("Dietary tags may contain letters, numbers, spaces, and hyphens.")
        if tag not in dietary_tags:
            dietary_tags.append(tag)
    is_vegan = form.get("is_vegan") or "vegan" in dietary_tags
    if is_vegan and "vegan" not in dietary_tags:
        dietary_tags.append("vegan")

    description = form.get("description", "").strip()
    ingredients = form.get("ingredients", "").strip()
    allergen_notes = form.get("allergens", form.get("allergen_notes", "")).strip()
    if len(description) > 2000 or len(ingredients) > 1000 or len(allergen_notes) > 500:
        raise ValueError("Description, ingredient, or allergen information is too long.")

    return {
        "name": name,
        "description": description,
        "category_id": category_id,
        "default_price": price,
        "image_path": image_url or None,
        "ingredients": ingredients,
        "allergen_notes": allergen_notes,
        "is_vegetarian": bool(form.get("is_vegetarian")) or is_vegan,
        "spice_level": spice_level,
        "dietary_tags": dietary_tags,
        "is_active": bool(form.get("is_active", "1")),
    }


def _category_values(form) -> dict:
    name = form.get("name", "").strip()
    if not name:
        raise ValueError("Category name is required.")
    if len(name) > 80:
        raise ValueError("Category name must be 80 characters or fewer.")
    try:
        sort_order = _parse_integer(form.get("sort_order", "0") or "0", "Display order", 0)
    except ValueError:
        sort_order = 0
    return {
        "name": name,
        "description": form.get("description", "").strip()[:240],
        "sort_order": sort_order,
        "is_active": bool(form.get("is_active", "1")),
    }


def _schedule_values(form, schedule=None) -> dict:
    try:
        food_id = _parse_integer(form.get("food_id", ""), "Food item", 1)
        menu_date = date.fromisoformat(form.get("date", ""))
        serving_start = time.fromisoformat(form.get("start_time", ""))
        serving_end = time.fromisoformat(form.get("end_time", ""))
        quantity = _parse_integer(
            form.get("stock", form.get("quantity_available", "")), "Stock quantity", 0
        )
    except (ValueError, TypeError):
        raise ValueError("Enter a valid food, date, time, and non-negative stock quantity.") from None

    meal_type = form.get("meal", form.get("meal_type", "")).strip()
    if meal_type not in MEAL_TYPES:
        raise ValueError("Choose Breakfast, Lunch, or Evening/Dinner.")
    if serving_end <= serving_start:
        raise ValueError("Serving end time must be later than the start time.")

    food = db.session.get(FoodItem, food_id)
    if food is None or (not food.is_active and (schedule is None or schedule.food_item_id != food_id)):
        raise ValueError("Choose an active food item.")
    scheduled_price = _parse_price(
        form.get("price", form.get("scheduled_price", "")),
        "Serving price",
        required=False,
    )
    duplicate = db.session.scalar(
        select(MenuSchedule.id).where(
            MenuSchedule.food_item_id == food_id,
            MenuSchedule.menu_date == menu_date,
            MenuSchedule.meal_type == meal_type,
            MenuSchedule.id != (schedule.id if schedule else -1),
        )
    )
    if duplicate is not None:
        raise ValueError("That dish is already scheduled for this date and meal.")
    return {
        "food_item_id": food_id,
        "menu_date": menu_date,
        "meal_type": meal_type,
        "serving_start": serving_start,
        "serving_end": serving_end,
        "scheduled_price": scheduled_price,
        "quantity_available": quantity,
    }


def _schedule_form(schedule=None, form_values=None, error=None):
    foods = list(
        db.session.scalars(
            select(FoodItem).where(FoodItem.is_active.is_(True)).order_by(FoodItem.name)
        ).all()
    )
    return render_template(
        "admin/schedule_form.html",
        schedule=schedule,
        foods=foods,
        meals=MEAL_TYPES,
        form_values=form_values or {},
        error=error,
    )


@admin_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per 15 minutes", methods=["POST"])
def login():
    if getattr(g, "current_admin", None):
        return redirect(url_for("admin.dashboard"))
    error = None
    form_values = {"username": ""}
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        form_values["username"] = username
        admin = db.session.scalar(select(Admin).where(func.lower(Admin.username) == username.lower()))
        if admin is not None and admin.is_active and admin.check_password(password):
            session.clear()
            session.permanent = True
            session["admin_id"] = admin.id
            return redirect(url_for("admin.dashboard"))
        error = "Invalid username or password."
    return render_template("admin/login.html", error=error, form_values=form_values)


@admin_bp.post("/logout")
@admin_required
def logout():
    session.clear()
    flash("You have signed out.", "success")
    return redirect(url_for("admin.login"))


@admin_bp.get("/dashboard")
@admin_required
def dashboard():
    today = campus_today()
    active_foods = db.session.scalar(
        select(func.count(FoodItem.id)).where(FoodItem.is_active.is_(True))
    ) or 0
    active_categories = db.session.scalar(
        select(func.count(Category.id)).where(Category.is_active.is_(True))
    ) or 0
    today_count = db.session.scalar(
        select(func.count(MenuSchedule.id))
        .join(MenuSchedule.food)
        .where(MenuSchedule.menu_date == today, FoodItem.is_active.is_(True))
    ) or 0
    schedules = list(
        db.session.scalars(
            select(MenuSchedule)
            .join(MenuSchedule.food)
            .where(
                MenuSchedule.menu_date == today,
                FoodItem.is_active.is_(True),
            )
            .options(joinedload(MenuSchedule.food).joinedload(FoodItem.category))
        ).unique().all()
    )
    threshold = current_threshold()
    low_stock = [item for item in schedules if 0 < item.quantity_available <= threshold]
    sold_out_count = sum(item.quantity_available == 0 for item in schedules)
    available_count = sum(item.quantity_available > threshold for item in schedules)
    visible_reviews = db.session.scalar(
        select(func.count(Review.id)).where(Review.is_hidden.is_(False))
    ) or 0
    hidden_reviews = db.session.scalar(
        select(func.count(Review.id)).where(Review.is_hidden.is_(True))
    ) or 0
    metrics = {
        "food_count": active_foods,
        "category_count": active_categories,
        "today_count": today_count,
        "available_count": available_count,
        "low_stock_count": len(low_stock),
        "sold_out_count": sold_out_count,
        "pending_reviews": hidden_reviews,
        "visible_reviews": visible_reviews,
    }
    return render_template("admin/dashboard.html", metrics=metrics, low_stock=low_stock)


def current_threshold() -> int:
    from flask import current_app

    return int(current_app.config.get("LOW_STOCK_THRESHOLD", 5))


@admin_bp.get("/foods")
@admin_required
def foods():
    statement = select(FoodItem).options(joinedload(FoodItem.category))
    query = request.args.get("q", "").strip()[:100]
    status = request.args.get("status", "")
    category_id = request.args.get("category", "")
    if query:
        statement = statement.where(FoodItem.name.ilike(f"%{query}%"))
    if status in ("active", "inactive"):
        statement = statement.where(FoodItem.is_active.is_(status == "active"))
    if category_id.isdigit() and int(category_id) > 0:
        statement = statement.where(FoodItem.category_id == int(category_id))
    statement = statement.order_by(FoodItem.name)
    food_rows = list(db.session.scalars(statement).unique().all())
    categories = list(db.session.scalars(select(Category).order_by(Category.name)).all())
    return render_template(
        "admin/foods.html",
        foods=food_rows,
        categories=categories,
        query=query,
        selected_status=status,
        selected_category=category_id,
    )


@admin_bp.route("/foods/new", methods=["GET", "POST"])
@admin_required
def food_new():
    if request.method == "POST":
        values = request.form.to_dict()
        try:
            food = FoodItem(**_food_values(request.form))
            db.session.add(food)
            db.session.commit()
        except ValueError as error:
            return _food_form_context(form_values=values, error=str(error)), 400
        except IntegrityError:
            db.session.rollback()
            return _food_form_context(form_values=values, error="A food item with that information already exists."), 400
        flash("Food item added. Schedule a serving to put it on the menu.", "success")
        return redirect(url_for("admin.foods"))
    return _food_form_context()


@admin_bp.route("/foods/<int:id>/edit", methods=["GET", "POST"])
@admin_required
def food_edit(id: int):
    food = db.session.get(FoodItem, id)
    if food is None:
        abort(404)
    if request.method == "POST":
        values = request.form.to_dict()
        try:
            for key, value in _food_values(request.form, food).items():
                setattr(food, key, value)
            food.updated_at = utc_now()
            db.session.commit()
        except ValueError as error:
            return _food_form_context(food, values, str(error)), 400
        except IntegrityError:
            db.session.rollback()
            return _food_form_context(food, values, "That food item could not be saved."), 400
        flash("Food details saved.", "success")
        return redirect(url_for("admin.foods"))
    return _food_form_context(food)


@admin_bp.post("/foods/<int:id>/toggle")
@admin_required
def food_toggle(id: int):
    food = db.session.get(FoodItem, id)
    if food is None:
        abort(404)
    food.is_active = not food.is_active
    db.session.commit()
    flash(f"{food.name} is now {'visible' if food.is_active else 'hidden'} on the menu.", "success")
    return redirect(url_for("admin.foods"))


@admin_bp.post("/foods/<int:id>/delete")
@admin_required
def food_delete(id: int):
    food = db.session.get(FoodItem, id)
    if food is None:
        abort(404)
    referenced = (
        db.session.scalar(
            select(MenuSchedule.id).where(MenuSchedule.food_item_id == id).limit(1)
        )
        or db.session.scalar(select(Review.id).where(Review.food_item_id == id).limit(1))
    )
    if referenced:
        flash("This dish has schedule or review history. Hide it instead of deleting it.", "error")
    else:
        db.session.delete(food)
        db.session.commit()
        flash("Food item deleted.", "success")
    return redirect(url_for("admin.foods"))


@admin_bp.get("/categories")
@admin_required
def categories():
    rows = list(
        db.session.scalars(
            select(Category).order_by(Category.sort_order, Category.name)
        ).all()
    )
    return render_template("admin/categories.html", categories=rows)


@admin_bp.route("/categories/new", methods=["GET", "POST"])
@admin_required
def category_new():
    if request.method == "POST":
        values = request.form.to_dict()
        try:
            data = _category_values(request.form)
            duplicate = db.session.scalar(
                select(Category.id).where(func.lower(Category.name) == data["name"].lower())
            )
            if duplicate:
                raise ValueError("A category with that name already exists.")
            db.session.add(Category(**data))
            db.session.commit()
        except ValueError as error:
            return render_template("admin/category_form.html", form_values=values, error=str(error)), 400
        flash("Category added.", "success")
        return redirect(url_for("admin.categories"))
    return render_template("admin/category_form.html", category=None, form_values={})


@admin_bp.route("/categories/<int:id>/edit", methods=["GET", "POST"])
@admin_required
def category_edit(id: int):
    category = db.session.get(Category, id)
    if category is None:
        abort(404)
    if request.method == "POST":
        values = request.form.to_dict()
        try:
            data = _category_values(request.form)
            duplicate = db.session.scalar(
                select(Category.id).where(
                    func.lower(Category.name) == data["name"].lower(),
                    Category.id != id,
                )
            )
            if duplicate:
                raise ValueError("A category with that name already exists.")
            for key, value in data.items():
                setattr(category, key, value)
            db.session.commit()
        except ValueError as error:
            return render_template("admin/category_form.html", category=category, form_values=values, error=str(error)), 400
        flash("Category saved.", "success")
        return redirect(url_for("admin.categories"))
    return render_template("admin/category_form.html", category=category, form_values={})


@admin_bp.post("/categories/<int:id>/toggle")
@admin_required
def category_toggle(id: int):
    category = db.session.get(Category, id)
    if category is None:
        abort(404)
    category.is_active = not category.is_active
    db.session.commit()
    flash(f"Category {category.name} is now {'active' if category.is_active else 'hidden'}.", "success")
    return redirect(url_for("admin.categories"))


@admin_bp.get("/schedules")
@admin_required
def schedules():
    today = campus_today()
    statement = (
        select(MenuSchedule)
        .join(MenuSchedule.food)
        .options(joinedload(MenuSchedule.food).joinedload(FoodItem.category))
        .where(MenuSchedule.menu_date >= today - timedelta(days=7))
        .order_by(MenuSchedule.menu_date, MenuSchedule.meal_type, FoodItem.name)
    )
    rows = list(db.session.scalars(statement).unique().all())
    return render_template("admin/schedules.html", schedules=rows, meals=MEAL_TYPES)


@admin_bp.route("/schedules/new", methods=["GET", "POST"])
@admin_required
def schedule_new():
    if request.method == "POST":
        values = request.form.to_dict()
        try:
            schedule = MenuSchedule(**_schedule_values(request.form))
            db.session.add(schedule)
            db.session.commit()
        except ValueError as error:
            return _schedule_form(form_values=values, error=str(error)), 400
        except IntegrityError:
            db.session.rollback()
            return _schedule_form(form_values=values, error="That serving already exists."), 400
        flash("Serving scheduled.", "success")
        return redirect(url_for("admin.schedules"))
    return _schedule_form()


@admin_bp.route("/schedules/<int:id>/edit", methods=["GET", "POST"])
@admin_required
def schedule_edit(id: int):
    schedule = db.session.get(MenuSchedule, id)
    if schedule is None:
        abort(404)
    if request.method == "POST":
        values = request.form.to_dict()
        try:
            for key, value in _schedule_values(request.form, schedule).items():
                setattr(schedule, key, value)
            schedule.updated_at = utc_now()
            db.session.commit()
        except ValueError as error:
            return _schedule_form(schedule, values, str(error)), 400
        except IntegrityError:
            db.session.rollback()
            return _schedule_form(schedule, values, "That serving already exists."), 400
        flash("Serving schedule updated.", "success")
        return redirect(url_for("admin.schedules"))
    return _schedule_form(schedule)


@admin_bp.post("/schedules/<int:id>/delete")
@admin_required
def schedule_delete(id: int):
    schedule = db.session.get(MenuSchedule, id)
    if schedule is None:
        abort(404)
    db.session.delete(schedule)
    db.session.commit()
    flash("Serving removed from the schedule.", "success")
    return redirect(url_for("admin.schedules"))


@admin_bp.get("/stock")
@admin_required
def stock():
    today = campus_today()
    statement = (
        select(MenuSchedule)
        .join(MenuSchedule.food)
        .options(joinedload(MenuSchedule.food).joinedload(FoodItem.category))
        .where(MenuSchedule.menu_date >= today)
        .order_by(MenuSchedule.menu_date, MenuSchedule.meal_type, FoodItem.name)
    )
    rows = list(db.session.scalars(statement).unique().all())
    return render_template(
        "admin/stock.html",
        schedules=rows,
        threshold=current_threshold(),
        stock_label=stock_label,
    )


@admin_bp.post("/stock/<int:id>")
@admin_required
def stock_update(id: int):
    schedule = db.session.get(MenuSchedule, id)
    if schedule is None:
        abort(404)
    try:
        quantity = _parse_integer(
            request.form.get("stock", request.form.get("quantity", "")),
            "Stock quantity",
            0,
        )
        update_schedule_stock(schedule, quantity)
    except ValueError as error:
        flash(str(error), "error")
        return redirect(url_for("admin.stock"))
    flash(f"Stock saved for {schedule.food.name}.", "success")
    return redirect(url_for("admin.stock"))


@admin_bp.get("/reviews")
@admin_required
def reviews():
    statement = (
        select(Review)
        .join(Review.food)
        .options(joinedload(Review.food).joinedload(FoodItem.category))
        .order_by(Review.created_at.desc())
    )
    query = request.args.get("q", "").strip()[:100]
    food_id = request.args.get("food_id", "")
    if query:
        statement = statement.where(
            or_(
                Review.review_text.ilike(f"%{query}%"),
                Review.reviewer_name.ilike(f"%{query}%"),
                FoodItem.name.ilike(f"%{query}%"),
            )
        )
    if food_id.isdigit() and int(food_id) > 0:
        statement = statement.where(Review.food_item_id == int(food_id))
    rows = list(db.session.scalars(statement).unique().all())
    foods = list(db.session.scalars(select(FoodItem).order_by(FoodItem.name)).all())
    return render_template("admin/reviews.html", reviews=rows, foods=foods, query=query, food_id=food_id)


@admin_bp.post("/reviews/<int:id>/moderate")
@admin_required
def review_moderate(id: int):
    review = db.session.get(Review, id)
    if review is None:
        abort(404)
    approved = request.form.get("is_approved") == "1"
    review.is_hidden = not approved
    db.session.commit()
    flash("Review published." if approved else "Review hidden from students.", "success")
    return redirect(url_for("admin.reviews"))


@admin_bp.post("/reviews/<int:id>/delete")
@admin_required
def review_delete(id: int):
    review = db.session.get(Review, id)
    if review is None:
        abort(404)
    db.session.delete(review)
    db.session.commit()
    flash("Review deleted.", "success")
    return redirect(url_for("admin.reviews"))
