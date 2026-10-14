import unittest

import checkin


class HeaderConstructionTests(unittest.TestCase):
    def test_checkin_headers_use_truthful_runtime_user_agent(self):
        headers = checkin.build_checkin_headers("session=abc")
        self.assertEqual(headers["Cookie"], "session=abc")
        self.assertEqual(headers["Origin"], checkin.BASE_URL)
        self.assertEqual(headers["Referer"], checkin.CHECKIN_PAGE_URL)
        self.assertTrue(headers["User-Agent"].startswith("autockin/1.0 "))
        self.assertNotIn("Windows NT", headers["User-Agent"])
        self.assertNotIn("Macintosh", headers["User-Agent"])
        self.assertNotIn("Sec-Fetch-Site", headers)

    def test_status_headers_do_not_send_content_type(self):
        headers = checkin.build_status_headers("session=abc")
        self.assertNotIn("Content-Type", headers)
        self.assertEqual(headers["Cookie"], "session=abc")


if __name__ == "__main__":
    unittest.main()
