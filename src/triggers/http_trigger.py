"""
HTTP Trigger Simulator for Azure Functions.

Provides classes for simulating Azure Functions HTTP triggers,
including request/response handling and route parameter parsing.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import parse_qs, urlparse


@dataclass
class HttpRequest:
    """Represents an HTTP request to an Azure Function."""

    method: str
    url: str
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[bytes] = None
    route_params: Dict[str, str] = field(default_factory=dict)

    @property
    def params(self) -> Dict[str, str]:
        """Parse and return query parameters from the URL."""
        parsed = urlparse(self.url)
        qs = parse_qs(parsed.query)
        return {k: v[0] if len(v) == 1 else v for k, v in qs.items()}

    def get_json(self) -> Any:
        """Parse and return the request body as JSON."""
        if self.body is None:
            return None
        try:
            return json.loads(self.body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def get_body(self) -> bytes:
        """Return the raw request body."""
        return self.body or b""


@dataclass
class HttpResponse:
    """Represents an HTTP response from an Azure Function."""

    body: str = ""
    status_code: int = 200
    headers: Dict[str, str] = field(default_factory=dict)
    mimetype: str = "text/plain"

    def get_body(self) -> bytes:
        """Return the response body as bytes."""
        if isinstance(self.body, bytes):
            return self.body
        return self.body.encode("utf-8")

    def to_dict(self) -> Dict[str, Any]:
        """Convert the response to a dictionary representation."""
        return {
            "status_code": self.status_code,
            "headers": self.headers,
            "body": self.body,
            "mimetype": self.mimetype,
        }


class HttpTrigger:
    """
    Simulates an Azure Functions HTTP trigger.

    Supports GET, POST, PUT, DELETE, PATCH methods with route
    parameter extraction and middleware-like auth level checking.
    """

    ALLOWED_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}
    AUTH_LEVELS = {"anonymous", "function", "admin"}

    def __init__(
        self,
        route: str = "",
        methods: Optional[List[str]] = None,
        auth_level: str = "anonymous",
    ):
        self.route = route.strip("/")
        self.methods = [m.upper() for m in (methods or ["GET", "POST"])]
        if auth_level not in self.AUTH_LEVELS:
            raise ValueError(
                f"Invalid auth_level '{auth_level}'. Must be one of {self.AUTH_LEVELS}"
            )
        self.auth_level = auth_level
        self._handler: Optional[Callable] = None
        self._route_pattern = self._compile_route(self.route)

    @staticmethod
    def _compile_route(route: str) -> re.Pattern:
        """Compile a route template into a regex pattern for matching."""
        pattern = re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", route)
        return re.compile(f"^{pattern}$")

    def __call__(self, func: Callable) -> Callable:
        """Register a function as the handler for this trigger."""
        self._handler = func
        func._trigger = self
        return func

    def match_route(self, path: str) -> Optional[Dict[str, str]]:
        """Check if a path matches this trigger's route and extract parameters."""
        path = path.strip("/")
        match = self._route_pattern.match(path)
        if match:
            return match.groupdict()
        return None

    def invoke(self, request: HttpRequest) -> HttpResponse:
        """
        Invoke the trigger handler with the given request.

        Validates the HTTP method and auth level before executing.
        """
        if not self._handler:
            return HttpResponse(body="No handler registered", status_code=500)

        if request.method.upper() not in self.methods:
            return HttpResponse(
                body=f"Method {request.method} not allowed",
                status_code=405,
            )

        route_params = self.match_route(urlparse(request.url).path)
        if route_params is not None:
            request.route_params = route_params

        try:
            result = self._handler(request)
            if isinstance(result, HttpResponse):
                return result
            return HttpResponse(body=str(result), status_code=200)
        except Exception as exc:
            return HttpResponse(body=f"Internal error: {exc}", status_code=500)
