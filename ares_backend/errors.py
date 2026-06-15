from __future__ import annotations


class BackendError(RuntimeError):
    code = "backend_error"
    status_code = 500


class UnauthorizedError(BackendError):
    code = "unauthorized"
    status_code = 401


class AuthProviderError(BackendError):
    code = "auth_provider_error"
    status_code = 400

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code


class RelinkRequiredError(BackendError):
    code = "relink_required"
    status_code = 409


class CapabilityError(BackendError):
    code = "capability_unavailable"
    status_code = 409


class RiotRequestError(BackendError):
    code = "riot_request_failed"
    status_code = 502

    def __init__(self, message: str, *, riot_status: int | None = None) -> None:
        super().__init__(message)
        self.riot_status = riot_status
