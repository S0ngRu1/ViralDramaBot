import unittest

from src.publishing.weixin.account_manager import AccountManager
from src.publishing.weixin.schemas import AccountStatus


class _FakeStates:
    def __init__(self, displayed=True):
        self.is_displayed = displayed


class _FakeElement:
    def __init__(self, text="", displayed=True):
        self.text = text
        self.states = _FakeStates(displayed)
        self.clicked = False

    def click(self):
        self.clicked = True


class _FakePage:
    def __init__(self, elements=None, url="https://channels.weixin.qq.com/login.html", js_error=None):
        self.elements = elements or {}
        self.url = url
        self.js_error = js_error
        self.requested_selectors = []

    def ele(self, selector, timeout=None):
        self.requested_selectors.append(selector)
        return self.elements.get(selector)

    def run_js(self, script):
        if self.js_error:
            raise self.js_error
        return 2

    def cookies(self):
        return []


class WeixinLoginCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.manager = AccountManager.__new__(AccountManager)

    def test_switches_quick_login_to_qrcode(self):
        switch = _FakeElement("使用其他头像、昵称或账号")
        page = _FakePage({"text:使用其他头像、昵称或账号": switch})

        switched = self.manager._switch_to_qrcode_login(page)

        self.assertTrue(switched)
        self.assertTrue(switch.clicked)

    def test_qrcode_page_does_not_require_switch(self):
        page = _FakePage()

        switched = self.manager._switch_to_qrcode_login(page)

        self.assertFalse(switched)

    def test_hidden_error_element_does_not_close_login(self):
        hidden_error = _FakeElement("登录失败", displayed=False)
        page = _FakePage({"css:.login-error": hidden_error})

        result = self.manager._detect_login_error(page)

        self.assertIsNone(result)
        self.assertNotIn("tag:body", page.requested_selectors)
        self.assertFalse(any("class*=" in item for item in page.requested_selectors))

    def test_visible_explicit_error_is_reported(self):
        visible_error = _FakeElement("二维码已过期，请刷新", displayed=True)
        page = _FakePage({"css:.qrcode-expired": visible_error})

        result = self.manager._detect_login_error(page)

        self.assertEqual("二维码已过期，请刷新", result)

    def test_platform_route_is_login_success_without_old_dom(self):
        page = _FakePage(url="https://channels.weixin.qq.com/platform/post/list")

        result = self.manager._check_login_status(page)

        self.assertTrue(result["success"])
        self.assertIsNone(result["error"])

    def test_login_page_with_unavailable_js_is_not_treated_as_closed(self):
        page = _FakePage(js_error=RuntimeError("javascript context temporarily unavailable"))

        result = self.manager._check_login_status(page)

        self.assertFalse(result["success"])
        self.assertIsNone(result["error"])

    def test_refresh_all_skips_account_currently_logging_in(self):
        class _FakeDAO:
            def __init__(self):
                self.auto_login_called = False

            def get_all_accounts(self):
                return [{
                    "id": 1,
                    "name": "test",
                    "status": AccountStatus.EXPIRED.value,
                }]

            def has_active_task(self, account_id):
                return False

            def get_account(self, account_id):
                return {
                    "id": account_id,
                    "name": "test",
                    "status": AccountStatus.LOGGING_IN.value,
                }

        manager = AccountManager.__new__(AccountManager)
        manager.dao = _FakeDAO()

        stats = manager.refresh_all_accounts()

        self.assertEqual(0, stats["checked"])
        self.assertEqual(1, stats["skipped"])


if __name__ == "__main__":
    unittest.main()
