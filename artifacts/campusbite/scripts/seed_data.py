from pathlib import Path
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from app import create_app
from app.extensions import db
from app.services.seed_service import seed_sample_data

app = create_app()

with app.app_context():
    db.create_all()
    seed_sample_data()
    print("Sample café data is ready. Existing administrator credentials were not changed.")
