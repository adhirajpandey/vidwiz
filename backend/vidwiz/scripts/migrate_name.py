
import sys
import os

# Add parent directory to path so we can import app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from vidwiz.app import create_app
from vidwiz.shared.models import db
from sqlalchemy import text

def migrate():
    print("Starting database migration for User Name...")
    app = create_app()
    
    with app.app_context():
        try:
            with db.engine.connect() as conn:
                print("Adding name column...")
                try:
                    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS name TEXT;"))
                    print("name column added (or already existed).")
                except Exception as e:
                    print(f"Note: Could not add name (might already exist or not supported): {e}")

                conn.commit()
                print("Migration steps completed.")
                
        except Exception as e:
            print(f"Migration failed: {e}")
            sys.exit(1)

if __name__ == "__main__":
    migrate()
