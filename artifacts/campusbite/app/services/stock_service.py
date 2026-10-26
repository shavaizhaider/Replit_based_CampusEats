from datetime import datetime, timezone

from ..extensions import db
from ..models import MenuSchedule


def stock_label(quantity: int, threshold: int = 5) -> str:
    if quantity <= 0:
        return "Sold Out"
    if quantity <= threshold:
        return "Low Stock"
    return "Available"


def update_schedule_stock(schedule: MenuSchedule, quantity: int) -> None:
    if quantity < 0:
        raise ValueError("Stock quantity cannot be negative.")
    schedule.quantity_available = quantity
    schedule.updated_at = datetime.now(timezone.utc)
    db.session.commit()
