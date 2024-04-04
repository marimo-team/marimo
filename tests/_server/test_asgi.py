import os
import tempfile
import unittest

from starlette.testclient import TestClient

from marimo._server.asgi import ASGIAppBuilder, create_asgi_app

contents = """
import marimo

__generated_with = "0.0.1"
app = marimo.App()


@app.cell
def __():
    import marimo as mo
    print("Hello from placeholder")
    return mo,


if __name__ == "__main__":
    app.run()
"""


class TestASGIAppBuilder(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for the tests
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app1 = os.path.join(self.temp_dir.name, "app1.py")
        self.app2 = os.path.join(self.temp_dir.name, "app2.py")
        with open(self.app1, "w") as f:
            f.write(contents.replace("placeholder", "app1"))
        with open(self.app2, "w") as f:
            f.write(contents.replace("placeholder", "app2"))

    def tearDown(self):
        # Clean up the temporary directory
        self.temp_dir.cleanup()

    def test_create_asgi_app(self):
        builder = create_asgi_app(quiet=True, include_code=True)
        assert isinstance(builder, ASGIAppBuilder)

        builder = create_asgi_app(quiet=True, include_code=True)
        assert isinstance(builder, ASGIAppBuilder)

        builder = builder.with_app(path="/test", root=self.app1)
        app = builder.build()
        assert callable(app)

    def test_app_base(self):
        builder = create_asgi_app(quiet=True, include_code=True)
        builder = builder.with_app(path="/", root=self.app1)
        app = builder.build()
        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200
        assert "app1.py" in response.text

    def test_app_redirect(self):
        builder = create_asgi_app(quiet=True, include_code=True)
        builder = builder.with_app(path="/test", root=self.app1)
        app = builder.build()
        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200, response.text
        assert "app1.py" in response.text

    def test_multiple_apps(self):
        builder = create_asgi_app(quiet=True, include_code=True)
        builder = builder.with_app(path="/app1", root=self.app1)
        builder = builder.with_app(path="/app2", root=self.app2)
        app = builder.build()
        client = TestClient(app)
        response = client.get("/app1")
        assert response.status_code == 200, response.text
        assert "app1.py" in response.text
        response = client.get("/app2")
        assert response.status_code == 200, response.text
        assert "app2.py" in response.text
        response = client.get("/")
        assert response.status_code == 404, response.text
        response = client.get("/app3")
        assert response.status_code == 404, response.text

    def test_root_doesnt_conflict_when_root_is_last(self):
        builder = create_asgi_app(quiet=True, include_code=True)
        builder = builder.with_app(path="/app1", root=self.app1)
        builder = builder.with_app(path="/", root=self.app2)
        app = builder.build()
        client = TestClient(app)
        response = client.get("/app1")
        assert response.status_code == 200, response.text
        assert "app1.py" in response.text
        response = client.get("/")
        assert response.status_code == 200, response.text
        assert "app2.py" in response.text

    def test_root_doesnt_conflict_when_root_is_first(self):
        builder = create_asgi_app(quiet=True, include_code=True)
        builder = builder.with_app(path="/", root=self.app2)
        builder = builder.with_app(path="/app1", root=self.app1)
        app = builder.build()
        client = TestClient(app)
        response = client.get("/app1")
        assert response.status_code == 200, response.text
        assert "app1.py" in response.text
        response = client.get("/")
        assert response.status_code == 200, response.text
        assert "app2.py" in response.text

    def test_can_include_code(self):
        builder = create_asgi_app(quiet=True, include_code=True)
        builder = builder.with_app(path="/app1", root=self.app1)
        app = builder.build()
        client = TestClient(app)
        response = client.get("/app1")
        assert response.status_code == 200, response.text
        assert "app1.py" in response.text

    def test_can_hit_health(self):
        builder = create_asgi_app(quiet=True, include_code=True)
        builder = builder.with_app(path="/app1", root=self.app1)
        app = builder.build()
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 404, response.text
        response = client.get("/app1/health")
        assert response.status_code == 200, response.text
