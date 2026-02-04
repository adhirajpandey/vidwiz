from src.exceptions import RateLimitError


def test_rate_limit_error_preserves_dict_details():
    error = RateLimitError("Daily limit reached", details={"reset_in_seconds": 10})
    response = error.to_response()
    assert response.error.details == {"reset_in_seconds": 10}
