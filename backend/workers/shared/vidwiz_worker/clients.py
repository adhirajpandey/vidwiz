from typing import Any

import requests

from vidwiz_worker.config import WorkerSettings


class InternalApiClient:
    def __init__(
        self, settings: WorkerSettings, logger: Any, *, session: Any = requests
    ):
        self._settings = settings
        self._logger = logger
        self._session = session

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._settings.internal_api_admin_token}",
        }

    def get_video(self, video_id: str) -> dict[str, Any] | None:
        return self._request_json("get", f"/v2/internal/videos/{video_id}", video_id)

    def update_note(self, note_id: int, text: str) -> bool:
        return self._request_success(
            "patch",
            f"/v2/internal/notes/{note_id}",
            {"text": text, "generated_by_ai": True},
            "note_id",
            note_id,
        )

    def update_summary(self, video_id: str, summary: str) -> bool:
        return self._request_success(
            "post",
            f"/v2/internal/videos/{video_id}/summary",
            {"summary": summary},
            "video_id",
            video_id,
        )

    def _request_json(
        self, method: str, path: str, video_id: str
    ) -> dict[str, Any] | None:
        try:
            response = getattr(self._session, method)(
                f"{self._settings.internal_api_base_url}{path}",
                headers=self._headers,
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
    ) -> bool:
        try:
            response = getattr(self._session, method)(
                f"{self._settings.internal_api_base_url}{path}",
                json=payload,
                headers=self._headers,
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
        self, settings: WorkerSettings, logger: Any, *, session: Any = requests
    ):
        self._settings = settings
        self._logger = logger
        self._session = session

    def complete(self, prompt: str) -> str | None:
        try:
            response = self._session.post(
                self._settings.openrouter_endpoint,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._settings.openrouter_api_key}",
                },
                json={
                    "model": self._settings.openrouter_model,
                    "messages": [{"role": "user", "content": prompt}],
                },
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
                return None
            choices = data.get("choices", [])
            message = choices[0].get("message") if choices else None
            return message.get("content") if message else None
        except Exception as error:
            self._logger.error(
                "OpenRouter API request failed",
                extra={
                    "error_type": type(error).__name__,
                    "status_code": getattr(
                        getattr(error, "response", None), "status_code", None
                    ),
                },
            )
            return None
