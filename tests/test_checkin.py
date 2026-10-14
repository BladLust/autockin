import contextlib
import io
import os
import unittest
from unittest.mock import Mock, patch

import requests

import checkin


class CheckinTests(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_safari_request_preparation(self):
        post, get = checkin.build_headers()
        with requests.Session() as session:
            session.headers.clear()
            prepared = session.prepare_request(requests.Request(
                'POST', checkin.CHECKIN_URL,
                headers={**post, 'Cookie': 'session=test'}, data=checkin.CHECKIN_BODY,
            ))
        self.assertIn('Macintosh', prepared.headers['User-Agent'])
        self.assertIn('Safari/', prepared.headers['User-Agent'])
        self.assertNotIn('Chrome/', prepared.headers['User-Agent'])
        self.assertFalse(any(k.lower().startswith('sec-ch-') for k in prepared.headers))
        self.assertEqual(prepared.headers['Accept-Encoding'], requests.utils.default_headers()['Accept-Encoding'])
        self.assertEqual(prepared.headers['Content-Length'], str(len(prepared.body)))
        self.assertEqual(prepared.headers['Referer'], checkin.BASE_URL + '/console/checkin')
        self.assertNotIn('Content-Type', get)
        self.assertNotIn('Origin', get)
        self.assertEqual(post['User-Agent'], get['User-Agent'])

    @patch.dict(os.environ, {'USER_AGENT': 'Captured Safari UA', 'ACCEPT_LANGUAGE': 'en-US,en;q=0.9'})
    def test_captured_profile_override(self):
        post, get = checkin.build_headers()
        for headers in (post, get):
            self.assertEqual(headers['User-Agent'], 'Captured Safari UA')
            self.assertEqual(headers['Accept-Language'], 'en-US,en;q=0.9')

    @patch.dict(os.environ, {'USER_AGENT': 'bad\r\nCookie: injected'})
    def test_multiline_override_rejected(self):
        with self.assertRaises(ValueError):
            checkin.build_headers()

    def test_redirect_not_followed(self):
        session = Mock()
        session.request.return_value.status_code = 302
        with self.assertRaisesRegex(RuntimeError, 'redirect'):
            checkin.request_json(session, 'POST', checkin.CHECKIN_URL, {'Cookie': 'secret'})
        self.assertFalse(session.request.call_args.kwargs['allow_redirects'])
        self.assertEqual(session.request.call_args.kwargs['timeout'], checkin.TIMEOUT)

    def test_success_and_status(self):
        session = Mock()
        response = session.request.return_value
        response.status_code = 200
        response.json.side_effect = [
            {'message': 'checkin repeats! please try tomorrow'},
            {'data': {'email': 'test@example.com', 'leftDays': '12.7'}},
        ]
        self.assertIn('checkin repeats!', checkin.checkin(session, 'session=test'))
        self.assertEqual(checkin.get_status(session, 'session=test'), 12)

    def test_invalid_json(self):
        session = Mock()
        session.request.return_value.status_code = 200
        session.request.return_value.json.side_effect = ValueError()
        with self.assertRaisesRegex(RuntimeError, 'invalid JSON'):
            checkin.request_json(session, 'GET', checkin.STATUS_URL, {})

    @patch('checkin.time.sleep')
    def test_read_timeout_then_success(self, sleep):
        session = Mock()
        response = Mock(status_code=200)
        response.json.return_value = {'message': 'checkin repeats!'}
        session.request.side_effect = [requests.ReadTimeout(), response]
        self.assertEqual(checkin.checkin(session, 'secret'), 'checkin repeats!')
        self.assertEqual(session.request.call_count, 2)
        sleep.assert_called_once_with(2)

    @patch('checkin.time.sleep')
    def test_timeout_exhaustion_is_bounded_and_private(self, sleep):
        session = Mock()
        session.request.side_effect = requests.ReadTimeout('secret cookie')
        with self.assertRaisesRegex(RuntimeError, 'POST .*3 attempt') as error:
            checkin.checkin(session, 'secret cookie')
        self.assertNotIn('secret cookie', str(error.exception))
        self.assertEqual(session.request.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    @patch('checkin.time.sleep')
    def test_transient_status_retries_but_auth_failure_does_not(self, sleep):
        session = Mock()
        unavailable = Mock(status_code=503)
        denied = Mock(status_code=401)
        denied.raise_for_status.side_effect = requests.HTTPError('401')
        session.request.side_effect = [unavailable, denied]
        with self.assertRaises(requests.HTTPError):
            checkin.get_status(session, 'secret')
        self.assertEqual(session.request.call_count, 2)
        unavailable.close.assert_called_once()
        sleep.assert_called_once_with(2)

    @patch('checkin.time.sleep')
    def test_arbitrary_post_not_retried(self, sleep):
        session = Mock()
        session.request.side_effect = requests.ReadTimeout()
        with self.assertRaises(RuntimeError):
            checkin.request_json(session, 'POST', checkin.BASE_URL, {})
        self.assertEqual(session.request.call_count, 1)
        sleep.assert_not_called()

    @patch.dict(os.environ, {'COOKIES': 'first&&second'}, clear=True)
    @patch('checkin.run_account', side_effect=[RuntimeError('failed'), None])
    def test_account_failure_does_not_skip_next_account(self, run):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(checkin.main(), 1)
        self.assertEqual(run.call_count, 2)


if __name__ == '__main__':
    unittest.main()
