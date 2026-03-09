"""Tests for the HTTP Trigger module."""

import json
import unittest

from src.triggers.http_trigger import HttpRequest, HttpResponse, HttpTrigger


class TestHttpRequest(unittest.TestCase):
    """Tests for the HttpRequest class."""

    def test_params_parsing(self):
        req = HttpRequest(method="GET", url="/api/test?name=azure&version=4")
        self.assertEqual(req.params["name"], "azure")
        self.assertEqual(req.params["version"], "4")

    def test_get_json(self):
        body = json.dumps({"key": "value"}).encode("utf-8")
        req = HttpRequest(method="POST", url="/api/test", body=body)
        data = req.get_json()
        self.assertEqual(data["key"], "value")

    def test_get_json_none_body(self):
        req = HttpRequest(method="GET", url="/api/test")
        self.assertIsNone(req.get_json())

    def test_get_body_default(self):
        req = HttpRequest(method="GET", url="/api/test")
        self.assertEqual(req.get_body(), b"")


class TestHttpResponse(unittest.TestCase):
    """Tests for the HttpResponse class."""

    def test_default_values(self):
        resp = HttpResponse()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.body, "")

    def test_get_body(self):
        resp = HttpResponse(body="Hello World")
        self.assertEqual(resp.get_body(), b"Hello World")

    def test_to_dict(self):
        resp = HttpResponse(body="test", status_code=201)
        d = resp.to_dict()
        self.assertEqual(d["status_code"], 201)
        self.assertEqual(d["body"], "test")


class TestHttpTrigger(unittest.TestCase):
    """Tests for the HttpTrigger class."""

    def test_basic_get(self):
        trigger = HttpTrigger(route="api/hello", methods=["GET"])

        @trigger
        def hello(req: HttpRequest) -> HttpResponse:
            name = req.params.get("name", "World")
            return HttpResponse(body=f"Hello, {name}!", status_code=200)

        req = HttpRequest(method="GET", url="api/hello?name=Azure")
        resp = trigger.invoke(req)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.body, "Hello, Azure!")

    def test_post_with_json(self):
        trigger = HttpTrigger(route="api/data", methods=["POST"])

        @trigger
        def create_data(req: HttpRequest) -> HttpResponse:
            data = req.get_json()
            return HttpResponse(
                body=json.dumps({"received": data}),
                status_code=201,
            )

        body = json.dumps({"item": "test"}).encode("utf-8")
        req = HttpRequest(method="POST", url="api/data", body=body)
        resp = trigger.invoke(req)
        self.assertEqual(resp.status_code, 201)

    def test_method_not_allowed(self):
        trigger = HttpTrigger(route="api/readonly", methods=["GET"])

        @trigger
        def read_only(req: HttpRequest) -> HttpResponse:
            return HttpResponse(body="OK")

        req = HttpRequest(method="DELETE", url="api/readonly")
        resp = trigger.invoke(req)
        self.assertEqual(resp.status_code, 405)

    def test_route_parameters(self):
        trigger = HttpTrigger(route="api/users/{user_id}", methods=["GET"])

        @trigger
        def get_user(req: HttpRequest) -> HttpResponse:
            user_id = req.route_params.get("user_id")
            return HttpResponse(body=f"User: {user_id}")

        req = HttpRequest(method="GET", url="api/users/42")
        resp = trigger.invoke(req)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("42", resp.body)

    def test_invalid_auth_level(self):
        with self.assertRaises(ValueError):
            HttpTrigger(route="api/test", auth_level="invalid")

    def test_handler_exception(self):
        trigger = HttpTrigger(route="api/error", methods=["GET"])

        @trigger
        def failing_handler(req: HttpRequest) -> HttpResponse:
            raise RuntimeError("Something broke")

        req = HttpRequest(method="GET", url="api/error")
        resp = trigger.invoke(req)
        self.assertEqual(resp.status_code, 500)
        self.assertIn("Something broke", resp.body)

    def test_no_handler(self):
        trigger = HttpTrigger(route="api/empty")
        req = HttpRequest(method="GET", url="api/empty")
        resp = trigger.invoke(req)
        self.assertEqual(resp.status_code, 500)


if __name__ == "__main__":
    unittest.main()
