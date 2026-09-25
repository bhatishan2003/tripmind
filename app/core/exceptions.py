"""Shared API exceptions."""

from fastapi import HTTPException, status

Unauthorized = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)

Forbidden = HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

NotFound = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


def not_found(detail: str = "Not found") -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
