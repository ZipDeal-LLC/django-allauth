import asyncio
import inspect

from asgiref.sync import iscoroutinefunction, sync_to_async, async_to_sync
from django.conf import settings
from django.utils.decorators import sync_and_async_middleware

from allauth.core import context
from allauth.core.exceptions import ImmediateHttpResponse
import environ

env = environ.Env()
ZIPDEAL_ENV = env.str("ZIPDEAL_ENV", "")

@sync_and_async_middleware
def AccountMiddleware(get_response):
    is_async = iscoroutinefunction(get_response)
    #  AttributeError: 'coroutine' object has no attribute 'headers'
    #  RuntimeWarning: coroutine '_asgi_middleware_mixin_factory.<locals>.SentryASGIMixin.__acall__' was never awaited
    # needs inspect to determine the response
    if is_async or ZIPDEAL_ENV != "devs":

        async def middleware(request):
            with context.request_context(request):
                try:
                    response = await get_response(request)
                    if _should_check_dangling_login(request, response):
                        await _acheck_dangling_login(request)
                    return response
                except ImmediateHttpResponse as e:
                    return e.response
    else:

        def middleware(request):
            with context.request_context(request):
                try:
                    response = get_response(request)
                    if _should_check_dangling_login(request, response):
                        _check_dangling_login(request)
                    return response
                except ImmediateHttpResponse as e:
                    return e.response

    return middleware


async def await_response(response):
    return await response


def _should_check_dangling_login(request, response):
    content_type = response.headers.get("content-type")
    if content_type:
        content_type = content_type.partition(";")[0]
    if content_type and content_type != "text/html":
        return False
    if request.path.startswith(settings.STATIC_URL) or request.path in [
        "/favicon.ico",
        "/robots.txt",
        "/humans.txt",
    ]:
        return False
    if response.status_code // 100 != 2:
        return False
    return True


def _check_dangling_login(request):
    if not getattr(request, "_account_login_accessed", False):
        if "account_login" in request.session:
            request.session.pop("account_login")


async def _acheck_dangling_login(request):
    await sync_to_async(_check_dangling_login)(request)
