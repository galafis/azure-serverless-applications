"""
Function App Orchestrator for Azure Functions Simulator.

Manages registration, routing, and execution of multiple Azure Functions
across different trigger types in a unified application context.
"""

import json
import logging
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

from ..triggers.blob_trigger import BlobTrigger, BlobProperties
from ..triggers.http_trigger import HttpRequest, HttpResponse, HttpTrigger
from ..triggers.queue_trigger import QueueMessage, QueueTrigger
from ..triggers.timer_trigger import TimerSchedule, TimerTrigger

logger = logging.getLogger(__name__)


class FunctionApp:
    """
    Azure Functions application orchestrator.

    Manages multiple functions with different trigger types and provides
    a unified interface for registration, invocation, and local testing.
    """

    def __init__(self, name: str = "FunctionApp"):
        self.name = name
        self._functions: Dict[str, Dict[str, Any]] = {}
        self._http_routes: Dict[str, HttpTrigger] = {}
        self._timer_triggers: Dict[str, TimerTrigger] = {}
        self._queue_triggers: Dict[str, QueueTrigger] = {}
        self._blob_triggers: Dict[str, BlobTrigger] = {}
        self._invocation_log: List[Dict] = []
        self._started_at: Optional[datetime] = None

    def register_function(
        self,
        name: str,
        handler: Callable,
        trigger: Any,
    ) -> None:
        """
        Register a function with its trigger.

        Args:
            name: Unique name for the function.
            handler: The function handler callable.
            trigger: The trigger instance (HttpTrigger, TimerTrigger, etc.).
        """
        if name in self._functions:
            raise ValueError(f"Function '{name}' is already registered")

        trigger(handler)

        func_info = {
            "name": name,
            "handler": handler,
            "trigger": trigger,
            "trigger_type": type(trigger).__name__,
            "registered_at": datetime.utcnow().isoformat(),
        }
        self._functions[name] = func_info

        if isinstance(trigger, HttpTrigger):
            self._http_routes[trigger.route] = trigger
        elif isinstance(trigger, TimerTrigger):
            self._timer_triggers[name] = trigger
        elif isinstance(trigger, QueueTrigger):
            self._queue_triggers[name] = trigger
        elif isinstance(trigger, BlobTrigger):
            self._blob_triggers[name] = trigger

        logger.info(f"Registered function '{name}' with {type(trigger).__name__}")

    def http(
        self,
        route: str = "",
        methods: Optional[List[str]] = None,
        auth_level: str = "anonymous",
    ) -> Callable:
        """Decorator for registering HTTP-triggered functions."""
        trigger = HttpTrigger(route=route, methods=methods, auth_level=auth_level)

        def decorator(func: Callable) -> Callable:
            self.register_function(func.__name__, func, trigger)
            return func

        return decorator

    def timer(
        self,
        schedule: str,
        name: str = "timer",
        run_on_startup: bool = False,
    ) -> Callable:
        """Decorator for registering timer-triggered functions."""
        trigger = TimerTrigger(schedule=schedule, name=name, run_on_startup=run_on_startup)

        def decorator(func: Callable) -> Callable:
            self.register_function(func.__name__, func, trigger)
            return func

        return decorator

    def queue(
        self,
        queue_name: str,
        connection: str = "AzureWebJobsStorage",
        batch_size: int = 1,
    ) -> Callable:
        """Decorator for registering queue-triggered functions."""
        trigger = QueueTrigger(
            queue_name=queue_name, connection=connection, batch_size=batch_size
        )

        def decorator(func: Callable) -> Callable:
            self.register_function(func.__name__, func, trigger)
            return func

        return decorator

    def blob(
        self,
        path: str,
        connection: str = "AzureWebJobsStorage",
    ) -> Callable:
        """Decorator for registering blob-triggered functions."""
        trigger = BlobTrigger(path=path, connection=connection)

        def decorator(func: Callable) -> Callable:
            self.register_function(func.__name__, func, trigger)
            return func

        return decorator

    def handle_http_request(self, request: HttpRequest) -> HttpResponse:
        """Route and handle an HTTP request to the matching function."""
        path = urlparse(request.url).path.strip("/")

        for route, trigger in self._http_routes.items():
            match = trigger.match_route(path)
            if match is not None:
                request.route_params = match
                result = trigger.invoke(request)
                self._log_invocation("http", trigger._handler.__name__, result.status_code)
                return result

        return HttpResponse(body="Function not found", status_code=404)

    def invoke_timer(self, function_name: str) -> Dict:
        """Manually invoke a timer-triggered function."""
        if function_name not in self._timer_triggers:
            return {"status": "error", "message": f"Timer function '{function_name}' not found"}

        result = self._timer_triggers[function_name].invoke()
        self._log_invocation("timer", function_name, result.get("status", "unknown"))
        return result

    def send_queue_message(self, function_name: str, body: Any) -> Dict:
        """Send a message to a queue-triggered function."""
        if function_name not in self._queue_triggers:
            return {"status": "error", "message": f"Queue function '{function_name}' not found"}

        trigger = self._queue_triggers[function_name]
        trigger.send_message(body)
        result = trigger.invoke()
        self._log_invocation("queue", function_name, result.get("status", "unknown"))
        return result

    def upload_blob(
        self,
        function_name: str,
        blob_name: str,
        content: bytes,
        content_type: str = "application/octet-stream",
    ) -> Dict:
        """Upload a blob and trigger the associated function."""
        if function_name not in self._blob_triggers:
            return {"status": "error", "message": f"Blob function '{function_name}' not found"}

        trigger = self._blob_triggers[function_name]
        result = trigger.upload_and_trigger(blob_name, content, content_type)
        self._log_invocation("blob", function_name, result.get("status", "unknown"))
        return result

    def _log_invocation(self, trigger_type: str, function_name: str, status: Any) -> None:
        """Log a function invocation."""
        self._invocation_log.append({
            "trigger_type": trigger_type,
            "function_name": function_name,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
        })

    def list_functions(self) -> List[Dict[str, str]]:
        """List all registered functions and their trigger types."""
        return [
            {
                "name": info["name"],
                "trigger_type": info["trigger_type"],
                "registered_at": info["registered_at"],
            }
            for info in self._functions.values()
        ]

    def get_invocation_log(self) -> List[Dict]:
        """Return the invocation history."""
        return list(self._invocation_log)

    def start_local_server(self, host: str = "0.0.0.0", port: int = 7071) -> None:
        """
        Start a local HTTP server for testing HTTP-triggered functions.

        Mimics the Azure Functions local development experience.
        """
        app = self

        class FunctionHandler(BaseHTTPRequestHandler):
            def _handle_request(self, method: str):
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length) if content_length > 0 else None

                headers = {k: v for k, v in self.headers.items()}

                req = HttpRequest(
                    method=method,
                    url=self.path,
                    headers=headers,
                    body=body,
                )

                resp = app.handle_http_request(req)

                self.send_response(resp.status_code)
                for key, value in resp.headers.items():
                    self.send_header(key, value)
                self.send_header("Content-Type", resp.mimetype)
                self.end_headers()
                self.wfile.write(resp.get_body())

            def do_GET(self):
                self._handle_request("GET")

            def do_POST(self):
                self._handle_request("POST")

            def do_PUT(self):
                self._handle_request("PUT")

            def do_DELETE(self):
                self._handle_request("DELETE")

            def log_message(self, format, *args):
                logger.info(f"[HTTP] {self.address_string()} - {format % args}")

        self._started_at = datetime.utcnow()
        server = HTTPServer((host, port), FunctionHandler)
        logger.info(f"Function App '{self.name}' running at http://{host}:{port}")
        logger.info(f"Registered functions: {[f['name'] for f in self.list_functions()]}")

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            server.server_close()
            logger.info("Function App stopped")
