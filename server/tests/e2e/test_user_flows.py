from playwright.sync_api import Page, expect

def test_search_on_dashboard(page: Page, live_server):
    # Mock the search API endpoint
    page.route("**/search?query=Test", 
        lambda route: route.fulfill(
            status=200,
            json=[{"video_id": "vid1", "video_title": "Test Video Title"}]
        )
    )

    page.goto("http://localhost:5000/dashboard")

    # Perform a search
    page.get_by_placeholder("Search Videos...").fill("Test")
    page.get_by_role("button", name="Search").click()

    # Check that the video is displayed
    video_link = page.get_by_text("Test Video Title")
    expect(video_link).to_be_visible()
    expect(video_link).to_have_attribute("href", "https://www.youtube.com/watch?v=vid1")

    # Check that the "Notes" button links to the correct page
    notes_button = page.get_by_role("link", name="Notes")
    expect(notes_button).to_have_attribute("href", "/dashboard/vid1")

def test_note_management_on_video_page(page: Page, live_server):
    video_id = "test_vid_123"

    # Mock the initial notes load
    page.route(f"**/video-notes/{video_id}",
        lambda route: route.fulfill(
            status=200,
            json=[{
                "id": 1, 
                "video_id": video_id, 
                "video_title": "My Test Video", 
                "note_timestamp": "00:01:15", 
                "note": "This is the original note text.", 
                "ai_note": None
            }]
        )
    )

    # Mock the note update (PATCH) endpoint
    page.route("**/notes/1",
        lambda route: route.fulfill(
            status=200,
            json={
                "id": 1,
                "video_id": video_id,
                "note_timestamp": "00:01:15",
                "note": "This is the updated note text.",
                "ai_note": None
            }
        ),
        times=1 # Only mock this once for the PATCH request
    )

    # Mock the note deletion (DELETE) endpoint
    page.route("**/notes/1",
        lambda route: route.fulfill(
            status=200,
            json={"message": "Note deleted successfully"}
        )
    )

    page.goto(f"http://localhost:5000/dashboard/{video_id}")
    
    # --- Verify initial note is displayed ---
    original_note = page.get_by_text("This is the original note text.")
    expect(original_note).to_be_visible()

    # --- Test Editing a Note ---
    # Click the edit button (targeting by title attribute of the icon)
    page.locator('[title="Edit note"]').click()
    
    # The note element is replaced by a textarea
    textarea = page.locator('textarea')
    expect(textarea).to_be_visible()
    textarea.fill("This is the updated note text.")
    
    # Click save
    page.get_by_role("button", name="Save").click()

    # Verify the note text has been updated
    updated_note = page.get_by_text("This is the updated note text.")
    expect(updated_note).to_be_visible()

    # --- Test Deleting a Note ---
    # Click the delete button
    page.locator('[title="Delete note"]').click()
    
    # Confirm the deletion in the modal
    expect(page.locator("#deleteModal")).to_be_visible()
    page.get_by_role("button", name="Delete").click()
    
    # Verify the note is no longer visible
    expect(page.get_by_text("This is the updated note text.")).not_to_be_visible()
    expect(page.locator("#deleteModal")).not_to_be_visible() 