
import pytest
from vidwiz.app import create_app

def test_google_auth_route_exists():
    """Test that the Google Auth route is registered."""
    app = create_app()
    
    # Check if the route is in the url_map
    routes = [str(p) for p in app.url_map.iter_rules()]
    assert any("/api/user/google/login" in r for r in routes), "Google login route not found"

def test_google_config_loaded():
    """Test that Google config variables are loaded (even if None)."""
    app = create_app()
    assert "GOOGLE_CLIENT_ID" in app.config
    # It might be None since we haven't set the env var yet, but the key should exist
