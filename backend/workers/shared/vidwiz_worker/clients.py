from typing import Any
import re

import requests

from vidwiz_worker.config import WorkerSettings


class InternalApiClient:
    def __init__(
        self, settings: WorkerSettings, logger: Any, *, session: Any = requests
    ):
        self._settings = settings
        self._logger = logger
        self._session = session

    def _headers(self, correlation_id: str | None = None) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._settings.internal_api_admin_token}",
        }
        if (
            correlation_id
            and len(correlation_id) <= 128
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]*", correlation_id)
        ):
            headers["X-Correlation-ID"] = correlation_id
        return headers

    def get_video(
        self, video_id: str, correlation_id: str | None = None
    ) -> dict[str, Any] | None:
        return self._request_json(
            "get", f"/v2/internal/videos/{video_id}", video_id, correlation_id
        )

    def save_moment_ai(
        self,
        moment_id: int,
        ai_text: str | None,
        ai_model: str | None = None,
        correlation_id: str | None = None,
    ) -> bool:
        """Store the AI line and its model, or null to mark the generation failed."""
        return self._request_success(
            "put",
            f"/v2/internal/moments/{moment_id}/ai",
            {"ai_text": ai_text, "ai_model": ai_model},
            "moment_id",
            moment_id,
            correlation_id,
        )

    def fail_overview(self, video_id: str, correlation_id: str | None = None) -> bool:
        """Mark the video's queued overview failed."""
        return self._request_success(
            "post",
            f"/v2/internal/videos/{video_id}/overview/failed",
            {},
            "video_id",
            video_id,
            correlation_id,
        )

    def update_summary(
        self,
        video_id: str,
        summary: str,
        suggested_questions: list[str],
        key_points: list[dict[str, Any]],
        overview_model: str,
        correlation_id: str | None = None,
    ) -> bool:
        return self._request_success(
            "post",
            f"/v2/internal/videos/{video_id}/summary",
            {
                "summary": summary,
                "miscellaneous_data": {
                    "suggested_questions": suggested_questions,
                    "key_points": key_points,
                    "overview_model": overview_model,
                },
            },
            "video_id",
            video_id,
            correlation_id,
        )

    def report_attempt_failure(
        self,
        workflow: str,
        reason: str,
        attempt: int,
        final: bool,
        correlation_id: str | None = None,
    ) -> bool:
        """Tell the API why an attempt failed, for its metrics."""
        try:
            response = self._session.post(
                f"{self._settings.internal_api_base_url}"
                f"/v2/internal/workflows/{workflow}/attempt-failures",
                json={"reason": reason, "attempt": attempt, "final": final},
                headers=self._headers(correlation_id),
                timeout=self._settings.request_timeout,
            )
            if response.status_code == 204:
                return True
            self._logger.warning(
                "Attempt report was rejected",
                extra={"workflow": workflow, "status": response.status_code},
            )
            return False
        except Exception as error:
            self._logger.warning(
                "Could not report failed attempt",
                extra={"workflow": workflow, "error": str(error)},
            )
            return False

    def _request_json(
        self, method: str, path: str, video_id: str, correlation_id: str | None = None
    ) -> dict[str, Any] | None:
        try:
            response = getattr(self._session, method)(
                f"{self._settings.internal_api_base_url}{path}",
                headers=self._headers(correlation_id),
                timeout=self._settings.request_timeout,
            )
            if response.status_code == 200:
                return response.json()
            self._logger.error(
                "Failed to get video metadata",
                extra={"video_id": video_id, "status": response.status_code},
            )
        except Exception as error:
            self._logger.error(
                "Error fetching video metadata",
                extra={"video_id": video_id, "error": str(error)},
            )
        return None

    def _request_success(
        self,
        method: str,
        path: str,
        payload: dict[str, Any],
        identifier_name: str,
        identifier: int | str,
        correlation_id: str | None = None,
    ) -> bool:
        try:
            response = getattr(self._session, method)(
                f"{self._settings.internal_api_base_url}{path}",
                json=payload,
                headers=self._headers(correlation_id),
                timeout=self._settings.request_timeout,
            )
            if response.status_code == 200:
                return True
            self._logger.error(
                "Failed to update VidWiz resource",
                extra={identifier_name: identifier, "status": response.status_code},
            )
        except Exception as error:
            self._logger.error(
                "Error updating VidWiz resource",
                extra={identifier_name: identifier, "error": str(error)},
            )
        return False


class OpenRouterClient:
    def __init__(
        self,
        settings: WorkerSettings,
        logger: Any,
        *,
        model: str,
        session: Any = requests,
    ):
        self._settings = settings
        self._logger = logger
        self._model = model
        self._session = session
        # Why the latest complete() call returned None, for attempt metrics.
        self.last_failure_kind: str | None = None

    def complete(
        self,
        prompt: str,
        *,
        response_format: dict[str, Any] | None = None,
        require_parameters: bool = False,
    ) -> str | None:
        request_payload: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
        }
        if response_format is not None:
            request_payload["response_format"] = response_format
        if require_parameters:
            request_payload["provider"] = {"require_parameters": True}

        self.last_failure_kind = None
        try:
            response = self._session.post(
                self._settings.openrouter_endpoint,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._settings.openrouter_api_key}",
                },
                json=request_payload,
                timeout=self._settings.request_timeout,
            )
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                provider_error = data["error"]
                error_code = (
                    provider_error.get("code")
                    if isinstance(provider_error, dict)
                    else None
                )
                self._logger.error(
                    "OpenRouter API returned an error",
                    extra=(
                        {"error_code": str(error_code)[:100]}
                        if error_code is not None
                        else {}
                    ),
                )
                self.last_failure_kind = provider_failure_kind(
                    error_code, provider_error
                )
                return None
            choices = data.get("choices", [])
            message = choices[0].get("message") if choices else None
            return message.get("content") if message else None
        except Exception as error:
            status_code = getattr(getattr(error, "response", None), "status_code", None)
            self._logger.error(
                "OpenRouter API request failed",
                extra={
                    "error_type": type(error).__name__,
                    "status_code": status_code,
                },
            )
            self.last_failure_kind = (
                "timeout"
                if isinstance(error, requests.Timeout)
                else provider_failure_kind(status_code, _error_body(error))
            )
            return None


def _error_body(error: Exception) -> Any:
    """The provider's error object, or None. Used for classification only."""
    try:
        return error.response.json().get("error")
    except Exception:
        return None


QUOTA_TERMS = ("limit", "credit", "budget", "quota", "afford")


def provider_failure_kind(status_code: Any, provider_error: Any = None) -> str:
    """402 means no credit and 429 is rate limiting. A 403 is a quota failure
    only when the provider says a limit or credit caused it; moderation and
    permission 403s are provider errors."""
    try:
        code = int(status_code)
    except (TypeError, ValueError):
        return "provider_error"
    if code == 402:
        return "provider_quota"
    if code == 403:
        detail = ""
        if isinstance(provider_error, dict):
            detail = f"{provider_error.get('message', '')} {provider_error.get('metadata', '')}"
        detail = detail.lower()
        return (
            "provider_quota"
            if any(term in detail for term in QUOTA_TERMS)
            else "provider_error"
        )
    if code == 429:
        return "provider_rate_limit"
    return "provider_error"
