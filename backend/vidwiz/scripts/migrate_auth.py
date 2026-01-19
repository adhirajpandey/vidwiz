
import sys
import os

# Add parent directory to path so we can import app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from vidwiz.app import create_app
from vidwiz.shared.models import db
from sqlalchemy import text

def migrate():
    print("Starting database migration for Google Auth...")
    app = create_app()
    
    with app.app_context():
        try:
            # Check if columns exist
            with db.engine.connect() as conn:
                # We'll try to add columns one by one. If they exist, it might fail or we can use IF NOT EXISTS if supported (Postgres does)
                # Since we are likely on Postgres, we use proper syntax.
                
                print("Adding google_id column...")
                try:
                    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id TEXT UNIQUE;"))
                    print("google_id column added (or already existed).")
                except Exception as e:
                    print(f"Note: Could not add google_id (might already exist or not supported): {e}")

                print("Adding email column...")
                try:
                    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS email TEXT UNIQUE;"))
                    print("email column added (or already existed).")
                except Exception as e:
                    print(f"Note: Could not add email: {e}")

                print("Adding profile_image_url column...")
                try:
                    conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_image_url TEXT;"))
                    print("profile_image_url column added (or already existed).")
                except Exception as e:
                    print(f"Note: Could not add profile_image_url: {e}")

                print("Altering password_hash to be nullable...")
                try:
                    # Postgres syntax
                    conn.execute(text("ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL;"))
                    print("password_hash is now nullable.")
                except Exception as e:
                     print(f"Note: Could not alter password_hash: {e}")
                
                conn.commit()
                print("Migration steps completed.")
                
        except Exception as e:
            print(f"Migration failed: {e}")
            sys.exit(1)

if __name__ == "__main__":
    migrate()
