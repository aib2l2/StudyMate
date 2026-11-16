"""HTTP routers grouped by domain."""

from fastapi import APIRouter


class Router(APIRouter):
    """APIRouter that omits optional fields the handler did not set.

    Response models document the API without changing the JSON the frontend
    already relies on (e.g. a quiz has no ``feedback`` key until submitted).
    """

    def add_api_route(self, path, endpoint, **kwargs):
        kwargs["response_model_exclude_unset"] = True
        return super().add_api_route(path, endpoint, **kwargs)
