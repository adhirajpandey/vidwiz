from playwright.sync_api import Page, expect

def test_dashboard_loads(page: Page, live_server):
    page.goto("http://localhost:5000/dashboard")
    expect(page).to_have_title("Dashboard")

def test_video_page_loads(page: Page, live_server):
    video_id = "test_video_id"
    page.goto(f"http://localhost:5000/dashboard/{video_id}")
    expect(page).to_have_title("Notes") 