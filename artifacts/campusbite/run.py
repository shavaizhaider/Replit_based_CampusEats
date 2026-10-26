import os

from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.extensions import db
from app.services.seed_service import seed_sample_data

app = create_app()

if os.environ.get("FLASK_ENV") == "production" and os.environ.get("CAMPUSBITE_INIT_DB") == "1":
    with app.app_context():
        db.create_all()


def initialize_development_data() -> None:
    """Make the preview useful on first run without seeding production data."""
    if os.environ.get("FLASK_ENV") == "production":
        return
    with app.app_context():
        db.create_all()
        if os.environ.get("CAMPUSBITE_DEMO_DATA", "1") == "1":
            seed_sample_data()


if __name__ == "__main__":
    initialize_development_data()
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "26046")),
        debug=False,
    )
