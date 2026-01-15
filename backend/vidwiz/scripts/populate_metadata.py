import csv
import json
import os
import sys

# Add backend directory to sys.path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from vidwiz.app import create_app
from vidwiz.shared.models import db, Video

def populate_metadata():
    app = create_app()
    with app.app_context():
        # csv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../vidwiz-video-details.csv"))
        # csv_path = "/app/vidwiz-video-details.csv"
        csv_path = "vidwiz-video-details.csv"
        print(f"Reading CSV from {csv_path}")
        
        if not os.path.exists(csv_path):
            print("CSV file not found!")
            return

        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            updated_count = 0
            for row in reader:
                video_id = row.get('videoid', '').strip()
                raw_details = row.get('raw_details')
                
                # Debug first row
                if updated_count == 0:
                    print(f"DEBUG: Row keys: {list(row.keys())}")
                    print(f"DEBUG: video_id from CSV: '{video_id}'")

                if video_id and raw_details:
                    try:
                        metadata = json.loads(raw_details)
                        video = Video.query.filter_by(video_id=video_id).first()
                        if updated_count == 0:
                             print(f"DEBUG: Video found in DB: {video}")
                        if video:
                            video.video_metadata = metadata
                            updated_count += 1
                            print(f"Updated metadata for video {video_id}")
                        else:
                            print(f"Video {video_id} not found in DB. Creating...")
                            title = metadata.get("title", "Unknown Title")
                            new_video = Video(video_id=video_id, title=title, video_metadata=metadata)
                            db.session.add(new_video)
                            updated_count += 1
                    except json.JSONDecodeError:
                        print(f"Failed to parse JSON for video {video_id}")
                    except Exception as e:
                        print(f"Error updating video {video_id}: {e}")

            try:
                db.session.commit()
                print(f"Successfully updated {updated_count} videos.")
            except Exception as e:
                db.session.rollback()
                print(f"Failed to commit changes: {e}")

if __name__ == "__main__":
    populate_metadata()
