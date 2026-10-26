from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select

from ..extensions import db
from ..models import Category, FoodItem, MenuSchedule, Review

SAMPLE_CATEGORIES = (
    ("Desi Food", "Campus favourites made for a filling meal."),
    ("Fast Food", "Quick, freshly prepared café classics."),
    ("Bakery", "Small baked treats for a study break."),
    ("Snacks", "Easy bites between classes."),
    ("Beverages", "Hot and cold drinks from the café."),
    ("Desserts", "Something sweet after lunch."),
    ("Healthy Food", "Lighter options and fresh produce."),
)

SAMPLE_FOODS = (
    {
        "name": "Chicken Biryani",
        "category": "Desi Food",
        "price": "350.00",
        "description": "Fragrant basmati rice layered with spiced chicken.",
        "ingredients": "Basmati rice, chicken, onion, tomato, spices",
        "allergens": "",
        "vegetarian": False,
        "spice": "medium",
        "tags": [],
        "image": "https://images.unsplash.com/photo-1563379091339-03246963d96c?auto=format&fit=crop&w=900&q=82",
    },
    {
        "name": "Daal Chawal",
        "category": "Desi Food",
        "price": "180.00",
        "description": "Comforting lentils served with steamed rice.",
        "ingredients": "Lentils, rice, onion, tomato, spices",
        "allergens": "",
        "vegetarian": True,
        "spice": "mild",
        "tags": ["vegan"],
        "image": "https://images.unsplash.com/photo-1547592180-85f173990554?auto=format&fit=crop&w=900&q=82",
    },
    {
        "name": "Chicken Karahi",
        "category": "Desi Food",
        "price": "420.00",
        "description": "Chicken simmered with tomato, ginger and green chilli.",
        "ingredients": "Chicken, tomato, ginger, green chilli, spices",
        "allergens": "",
        "vegetarian": False,
        "spice": "hot",
        "tags": [],
        "image": "https://images.unsplash.com/photo-1603894584373-5ac82b2ae398?auto=format&fit=crop&w=900&q=82",
    },
    {
        "name": "Chicken Roll",
        "category": "Fast Food",
        "price": "220.00",
        "description": "Seasoned chicken and crisp salad wrapped in a warm paratha.",
        "ingredients": "Chicken, wheat paratha, lettuce, yogurt sauce",
        "allergens": "Contains wheat and dairy.",
        "vegetarian": False,
        "spice": "medium",
        "tags": [],
        "image": "https://images.unsplash.com/photo-1626700051175-6818013e1d4f?auto=format&fit=crop&w=900&q=82",
    },
    {
        "name": "Zinger Burger",
        "category": "Fast Food",
        "price": "380.00",
        "description": "Crispy chicken, lettuce and house sauce in a toasted bun.",
        "ingredients": "Chicken, wheat bun, lettuce, mayonnaise",
        "allergens": "Contains wheat and egg.",
        "vegetarian": False,
        "spice": "mild",
        "tags": [],
        "image": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?auto=format&fit=crop&w=900&q=82",
    },
    {
        "name": "French Fries",
        "category": "Snacks",
        "price": "160.00",
        "description": "Golden fries with a light seasoning.",
        "ingredients": "Potato, cooking oil, salt",
        "allergens": "",
        "vegetarian": True,
        "spice": "mild",
        "tags": ["vegan", "gluten-free"],
        "image": "https://images.unsplash.com/photo-1573080496219-bb080dd4f877?auto=format&fit=crop&w=900&q=82",
    },
    {
        "name": "Aloo Paratha",
        "category": "Desi Food",
        "price": "140.00",
        "description": "Flaky flatbread filled with spiced potato.",
        "ingredients": "Wheat flour, potato, coriander, spices",
        "allergens": "Contains wheat.",
        "vegetarian": True,
        "spice": "mild",
        "tags": [],
        "image": "https://images.unsplash.com/photo-1600628422019-97d1b0e8f33a?auto=format&fit=crop&w=900&q=82",
    },
    {
        "name": "Omelette",
        "category": "Desi Food",
        "price": "180.00",
        "description": "A fluffy two-egg omelette with herbs and a little chilli.",
        "ingredients": "Egg, onion, coriander, green chilli",
        "allergens": "Contains egg.",
        "vegetarian": False,
        "spice": "mild",
        "tags": [],
        "image": "https://images.unsplash.com/photo-1525351484163-7529414344d8?auto=format&fit=crop&w=900&q=82",
    },
    {
        "name": "Chicken Sandwich",
        "category": "Fast Food",
        "price": "260.00",
        "description": "Chicken, crunchy vegetables and a creamy café dressing.",
        "ingredients": "Chicken, wheat bread, lettuce, mayonnaise",
        "allergens": "Contains wheat and egg.",
        "vegetarian": False,
        "spice": "mild",
        "tags": [],
        "image": "https://images.unsplash.com/photo-1528735602780-2552fd46c7af?auto=format&fit=crop&w=900&q=82",
    },
    {
        "name": "Samosa",
        "category": "Snacks",
        "price": "60.00",
        "description": "Crisp pastry filled with spiced potato and peas.",
        "ingredients": "Wheat pastry, potato, peas, spices",
        "allergens": "Contains wheat.",
        "vegetarian": True,
        "spice": "medium",
        "tags": [],
        "image": "https://images.unsplash.com/photo-1601050690597-df0568f70950?auto=format&fit=crop&w=900&q=82",
    },
    {
        "name": "Pakora",
        "category": "Snacks",
        "price": "100.00",
        "description": "Vegetable fritters coated in a seasoned gram-flour batter.",
        "ingredients": "Potato, onion, chickpea flour, spices",
        "allergens": "",
        "vegetarian": True,
        "spice": "medium",
        "tags": ["vegan", "gluten-free"],
        "image": "https://images.unsplash.com/photo-1626777552726-4a6b54c97e46?auto=format&fit=crop&w=900&q=82",
    },
    {
        "name": "Chai",
        "category": "Beverages",
        "price": "80.00",
        "description": "Freshly brewed tea with a gentle milk finish.",
        "ingredients": "Tea, milk, water, sugar",
        "allergens": "Contains dairy.",
        "vegetarian": True,
        "spice": "mild",
        "tags": [],
        "image": "https://images.unsplash.com/photo-1571934811356-5cc061b6821f?auto=format&fit=crop&w=900&q=82",
    },
    {
        "name": "Fresh Juice",
        "category": "Beverages",
        "price": "180.00",
        "description": "Seasonal fruit juice, prepared fresh for the day.",
        "ingredients": "Seasonal fruit",
        "allergens": "",
        "vegetarian": True,
        "spice": "mild",
        "tags": ["vegan", "dairy-free", "egg-free", "gluten-free"],
        "image": "https://images.unsplash.com/photo-1600271886742-f049cd451bba?auto=format&fit=crop&w=900&q=82",
    },
    {
        "name": "Brownie",
        "category": "Desserts",
        "price": "150.00",
        "description": "A rich cocoa brownie with a soft, fudgy centre.",
        "ingredients": "Cocoa, wheat flour, egg, butter, sugar",
        "allergens": "Contains wheat, egg and dairy.",
        "vegetarian": True,
        "spice": "mild",
        "tags": [],
        "image": "https://images.unsplash.com/photo-1606313564200-e75d5e30476c?auto=format&fit=crop&w=900&q=82",
    },
    {
        "name": "Fruit Salad",
        "category": "Healthy Food",
        "price": "180.00",
        "description": "A colourful bowl of seasonal cut fruit.",
        "ingredients": "Seasonal fruit",
        "allergens": "",
        "vegetarian": True,
        "spice": "mild",
        "tags": ["vegan", "dairy-free", "egg-free", "gluten-free"],
        "image": "https://images.unsplash.com/photo-1490474418585-ba9bad8fd0ea?auto=format&fit=crop&w=900&q=82",
    },
)

MEAL_WINDOWS = {
    "Breakfast": (time(7, 30), time(10, 30)),
    "Lunch": (time(12, 0), time(15, 0)),
    "Evening/Dinner": (time(16, 0), time(20, 0)),
}


def seed_sample_data() -> None:
    category_by_name: dict[str, Category] = {}
    for name, description in SAMPLE_CATEGORIES:
        category = db.session.scalar(select(Category).where(Category.name == name))
        if category is None:
            category = Category(name=name, description=description, is_active=True)
            db.session.add(category)
            db.session.flush()
        category_by_name[name] = category

    food_by_name: dict[str, FoodItem] = {}
    for row in SAMPLE_FOODS:
        food = db.session.scalar(select(FoodItem).where(FoodItem.name == row["name"]))
        if food is None:
            food = FoodItem(
                name=row["name"],
                description=row["description"],
                category=category_by_name[row["category"]],
                default_price=Decimal(row["price"]),
                image_path=row["image"],
                ingredients=row["ingredients"],
                allergen_notes=row["allergens"],
                is_vegetarian=row["vegetarian"],
                spice_level=row["spice"],
                dietary_tags=row["tags"],
                is_active=True,
            )
            db.session.add(food)
            db.session.flush()
        food_by_name[row["name"]] = food

    today = datetime.now(ZoneInfo("Asia/Karachi")).date()
    schedule_plan = (
        ("Breakfast", ("Aloo Paratha", "Omelette", "Chai", "Samosa", "Fresh Juice")),
        ("Lunch", ("Chicken Biryani", "Daal Chawal", "Chicken Karahi", "Chicken Roll", "Zinger Burger", "Fruit Salad")),
        ("Evening/Dinner", ("Chicken Roll", "French Fries", "Samosa", "Pakora", "Chai", "Brownie")),
    )
    for day_offset in range(7):
        menu_date = today + timedelta(days=day_offset)
        for meal_type, names in schedule_plan:
            start, end = MEAL_WINDOWS[meal_type]
            for position, name in enumerate(names):
                food = food_by_name[name]
                exists = db.session.scalar(
                    select(MenuSchedule.id).where(
                        MenuSchedule.food_item_id == food.id,
                        MenuSchedule.menu_date == menu_date,
                        MenuSchedule.meal_type == meal_type,
                    )
                )
                if exists:
                    continue
                quantities = (0, 3, 12, 8, 16, 5)
                quantity = quantities[(position + day_offset) % len(quantities)]
                db.session.add(
                    MenuSchedule(
                        food_item_id=food.id,
                        menu_date=menu_date,
                        meal_type=meal_type,
                        serving_start=start,
                        serving_end=end,
                        scheduled_price=None,
                        quantity_available=quantity,
                    )
                )

    for food_name, rating, text, device in (
        ("Chicken Biryani", 5, "The rice was fragrant and the portion was generous.", "demo-device-biryani"),
        ("Daal Chawal", 4, "A comforting lunch between classes.", "demo-device-daal"),
        ("Zinger Burger", 4, "Crispy and filling.", "demo-device-zinger"),
    ):
        food = food_by_name[food_name]
        existing = db.session.scalar(
            select(Review.id).where(
                Review.food_item_id == food.id, Review.device_hash == device
            )
        )
        if existing is None:
            db.session.add(
                Review(
                    food_item_id=food.id,
                    rating=rating,
                    review_text=text,
                    reviewer_name="Campus student",
                    device_hash=device,
                    is_hidden=False,
                    created_at=datetime.now(timezone.utc),
                )
            )
    db.session.commit()
