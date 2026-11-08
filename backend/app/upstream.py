"""HTTP calls to the mock services, with their errors mapped to one exception."""
from typing import Any

import httpx
from fastapi import HTTPException

from .institutions import Institution


class UpstreamError(Exception):
    def __init__(self, institution_id: str, status: int, detail: Any, retry_after: str | None = None):
        super().__init__(f"{institution_id}: {status} {detail}")
        self.institution_id = institution_id
        self.status = status
        self.detail = detail
        self.retry_after = retry_after


async def call(client: httpx.AsyncClient, institution: Institution, method: str, path: str,
               token: str | None = None, **kwargs: Any) -> Any:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        response = await client.request(method, institution.base_url.rstrip("/") + path, headers=headers, **kwargs)
    except httpx.HTTPError as error:
        raise UpstreamError(institution.id, 502, f"{institution.name} is unavailable ({type(error).__name__})") from error
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise UpstreamError(institution.id, response.status_code, detail, response.headers.get("Retry-After"))
    return response.json() if response.content else None


def as_http(error: UpstreamError) -> HTTPException:
    """Pass the service's status and FastAPI-style detail through, tagged with the institution."""
    headers = {"Retry-After": error.retry_after} if error.retry_after else None
    status = error.status if error.status in {401, 404, 409, 422, 429} else 502
    return HTTPException(status, {"institution_id": error.institution_id, "detail": error.detail}, headers=headers)
