from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from app import create_app
from config import Config


class FireMetricsStandaloneTests(unittest.TestCase):
    def setUp(self):
        self._tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp_db.close()
        self._old_db_path = os.environ.get("FIRE_METRICS_DB_PATH")
        os.environ["FIRE_METRICS_DB_PATH"] = self._tmp_db.name

        class TestConfig(Config):
            TESTING = True
            WTF_CSRF_ENABLED = False
            SECRET_KEY = "test-secret"
            ADMIN_USERNAME = "test-admin"
            ADMIN_PASSWORD_HASH = ""
            UPLOAD_FOLDER = "/tmp/fire_test_uploads"

        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

    def tearDown(self):
        if self._old_db_path is None:
            os.environ.pop("FIRE_METRICS_DB_PATH", None)
        else:
            os.environ["FIRE_METRICS_DB_PATH"] = self._old_db_path

        try:
            Path(self._tmp_db.name).unlink(missing_ok=True)
        except Exception:
            pass

    def _login(self):
        with self.client.session_transaction() as session:
            session["_user_id"] = self.app.config.get("ADMIN_USERNAME")
            session["_fresh"] = True

    def test_standalone_route_requires_auth(self):
        response = self.client.get("/fire-metrics/", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers.get("Location", ""))

    def test_authenticated_standalone_renders_fire_metrics(self):
        self._login()
        response = self.client.get("/fire-metrics/")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("FIRE Metrics", html)

    def test_standalone_hides_platform_navigation(self):
        self._login()
        response = self.client.get("/fire-metrics/")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertNotIn("Analytics Platform", html)
        self.assertNotIn("Weekly Property Summary", html)
        self.assertNotIn('class="fire-metrics-back"', html)

    def test_tools_route_still_renders_normal_navigation(self):
        self._login()
        response = self.client.get("/tools/fire-metrics/")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Analytics Platform", html)
        self.assertIn("Weekly Property Summary", html)
        self.assertIn('class="fire-metrics-back"', html)


if __name__ == "__main__":
    unittest.main()
