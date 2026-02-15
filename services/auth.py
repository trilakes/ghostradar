import uuid
from flask import request, make_response

COOKIE_NAME = "ghostradar_device_id"
COOKIE_MAX_AGE = 365 * 24 * 60 * 60  # 1 year


def get_device_id() -> str:
    """Get or create device_id from cookie."""
    device_id = request.cookies.get(COOKIE_NAME)
    if not device_id:
        device_id = str(uuid.uuid4())
    return device_id


def set_device_cookie(response, device_id: str):
    """Set the device_id cookie on the response."""
    response.set_cookie(
        COOKIE_NAME,
        device_id,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="Lax",
        secure=False,  # set True in production with HTTPS
    )
    return response
