# migration_add_date.py
from models import engine
from sqlalchemy import text


def add_date_column():
    """Add date_posted column to existing database"""
    with engine.connect() as conn:
        # Check if column exists
        result = conn.execute(text("PRAGMA table_info(jobs)"))
        columns = [row[1] for row in result]

        if 'date_posted' not in columns:
            conn.execute(text("ALTER TABLE jobs ADD COLUMN date_posted VARCHAR(100)"))
            conn.commit()
            print("Added date_posted column to jobs table")
        else:
            print("date_posted column already exists")


if __name__ == "__main__":
    add_date_column()