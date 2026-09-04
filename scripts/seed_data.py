import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.core.db import SessionLocal, init_db, set_rls_context
from app.services.seed import seed_demo_data

def main():
    if "--reset" in sys.argv:
        if settings.DATABASE_URL.startswith("sqlite"):
            db_path = settings.DATABASE_URL.replace("sqlite:///", "")
            if os.path.exists(db_path):
                os.remove(db_path)
                print(f"Removed SQLite database file: {db_path}")
        else:
            print("Note: Reset flag only deletes local SQLite database. For PostgreSQL, drop tables or schema.")

    print("Initializing schema...")
    init_db()
    db = SessionLocal()
    try:
        set_rls_context(db, None, "state_admin")
        print("Seeding demo data for NE-EMIS network...")
        seed_demo_data(db)
        print("Seeding completed successfully!")
    finally:
        db.close()

if __name__ == "__main__":
    main()
