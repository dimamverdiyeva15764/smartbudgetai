import logging

from django.http import JsonResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def _first_message(data):
    """Return the first human readable message inside a DRF error payload."""
    if isinstance(data, str):
        return data
    if isinstance(data, list) and data:
        return _first_message(data[0])
    if isinstance(data, dict):
        if 'detail' in data:
            return _first_message(data['detail'])
        for value in data.values():
            message = _first_message(value)
            if message:
                return message
    return None


def custom_exception_handler(exc, context):
    """Standard JSON error structure for every API error.

    {"success": false, "message": "...", "errors": {...}}
    Unexpected exceptions are logged and returned as JSON 500 instead of
    Django's HTML error page.
    """
    response = exception_handler(exc, context)
    if response is not None:
        errors = response.data
        response.data = {
            "success": False,
            "message": _first_message(errors) or "Sorğu uğursuz oldu.",
            "errors": errors,
        }
        return response

    logger.exception("Unhandled API error", exc_info=exc)
    return Response(
        {
            "success": False,
            "message": "Serverdə gözlənilməz xəta baş verdi. Zəhmət olmasa bir az sonra yenidən cəhd edin.",
            "code": "SERVER_ERROR",
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def json_server_error(request, *args, **kwargs):
    """handler500: JSON instead of HTML for errors raised outside DRF views."""
    return JsonResponse(
        {
            "success": False,
            "message": "Serverdə gözlənilməz xəta baş verdi.",
            "code": "SERVER_ERROR",
        },
        status=500,
    )


def json_not_found(request, exception=None, *args, **kwargs):
    return JsonResponse(
        {"success": False, "message": "API ünvanı tapılmadı.", "code": "NOT_FOUND"},
        status=404,
    )
