from django.contrib.staticfiles import finders
from django.test import TestCase


class FrontendShellTests(TestCase):
    def test_root_serves_the_app_shell(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="root"')
        self.assertContains(response, "js/main.js")

    def test_static_assets_exist(self):
        for path in (
            "css/app.css",
            "js/main.js",
            "js/api.js",
            "js/shell.js",
            "js/dom.js",
            "js/icons.js",
        ):
            self.assertIsNotNone(finders.find(path), path)
