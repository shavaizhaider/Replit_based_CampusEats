import hashlib
import re
import secrets
from decimal import Decimal

from flask import Blueprint, current_app, make_response, redirect, render_template, request, url_for, flash
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload

from ..extensions import db, limiter
from ..models import FoodItem, MenuSchedule, Review
from ..public.routes import campus_today

reviews_bp = Blueprint("reviews", __name__)
DEVICE_COOKIE = "campusbite_device"


def _render_review_error(food_id: int, message: str, values: dict):
    food = db.session.scalar(
        select(FoodItem)
        .where(FoodItem.id == food_id, FoodItem.is_active.is_(True))
        .options(joinedload(FoodItem.category), selectinload(FoodItem.reviews))
    )
    if food is None:
        return render_template("errors/404.html"), 404
    schedules = list(
        db.session.scalars(
            select(MenuSchedule)
            .where(MenuSchedule.food_item_id == food_id, MenuSchedule.menu_date >= campus_today())
            .order_by(MenuSchedule.menu_date, MenuSchedule.serving_start)
            .limit(14)
        ).all()
    )
    reviews = list(
        db.session.scalars(
            select(Review)
            .where(Review.food_item_id == food_id, Review.is_hidden.is_(False))
            .order_by(Review.created_at.desc())
            .limit(10)
        ).all()
    )
    return (
        render_template(
            "food_detail.html",
            food=food,
            schedules=schedules,
            reviews=reviews,
            avg_rating=food.avg_rating,
            review_count=food.review_count,
            error=message,
            form_values=values,
        ),
        400,
    )


@reviews_bp.post("/food/<int:id>/reviews")
@limiter.limit("5 per hour")
def submit_review(id: int):
    rating_text = request.form.get("rating", "").strip()
    raw_review_text = request.form.get("comment", request.form.get("review_text", ""))
    review_text = raw_review_text.strip()
    reviewer_name = request.form.get(
        "student_name", request.form.get("reviewer_name", "")
    ).strip()
    values = {
        "rating": rating_text,
        "comment": review_text,
        "student_name": reviewer_name,
    }

    if not re.fullmatch(r"[1-5]", rating_text):
        return _render_review_error(
            id, "Choose a rating from one to five stars.", values
        )
    if raw_review_text and not review_text:
        return _render_review_error(
            id, "A written review cannot contain only spaces.", values
        )
    if len(review_text) > 300:
        return _render_review_error(
            id, "Keep your review to 300 characters or fewer.", values
        )
    if len(reviewer_name) > 80:
        return _render_review_error(id, "Name must be 80 characters or fewer.", values)

    food = db.session.scalar(
        select(FoodItem).where(FoodItem.id == id, FoodItem.is_active.is_(True))
    )
    if food is None:
        return render_template("errors/404.html"), 404

    device_token = request.cookies.get(DEVICE_COOKIE) or secrets.token_urlsafe(32)
    device_hash = hashlib.sha256(device_token.encode("utf-8")).hexdigest()
    existing = db.session.scalar(
        select(Review.id).where(
            Review.food_item_id == id, Review.device_hash == device_hash
        )
    )
    if existing:
        return _render_review_error(
            id,
            "This browser has already rated this item. Device limits are not identity verification.",
            values,
        )

    review = Review(
        food_item_id=id,
        rating=int(rating_text),
        review_text=review_text or None,
        reviewer_name=reviewer_name or None,
        device_hash=device_hash,
    )
    db.session.add(review)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _render_review_error(
            id,
            "This browser has already rated this item. Device limits are not identity verification.",
            values,
        )

    flash("Thank you! Your rating has been submitted.", "success")
    response = make_response(redirect(url_for("public.food_detail", id=id) + "#reviews"))
    if not request.cookies.get(DEVICE_COOKIE):
        response.set_cookie(
            DEVICE_COOKIE,
            device_token,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            secure=current_app.config["SESSION_COOKIE_SECURE"],
            samesite="Lax",
        )
    return response
