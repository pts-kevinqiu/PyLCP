import unittest

from mock import patch, call, sentinel

from lcp import mac


class GenerateExtTestCase(unittest.TestCase):
    def test_content_type_and_body_none_is_zero_length_ext(self):
        content_type = None
        body = None
        ext = mac.generate_ext(content_type, body)
        self.assertIsNotNone(ext)
        self.assertEqual(ext, "")

    def test_content_type_and_body_zero_length_is_zero_length_ext(self):
        content_type = ''
        body = ''
        ext = mac.generate_ext(content_type, body)
        self.assertIsNotNone(ext)
        self.assertEqual(ext, "")

    def test_content_type_non_none_and_body_none_is_zero_length_ext(self):
        content_type = "dave was here"
        body = None
        ext = mac.generate_ext(content_type, body)
        self.assertIsNotNone(ext)
        self.assertEqual(ext, "")

    def test_content_type_none_and_body_non_none_is_zero_length_ext(self):
        content_type = None
        body = "dave was here"
        ext = mac.generate_ext(content_type, body)
        self.assertIsNotNone(ext)
        self.assertEqual(ext, "")

    @patch('lcp.mac.hashlib.sha1')
    def test_content_type_and_body_non_none_returns_sha1_of_both(self, mock_sha1):
        content_type = "hello world!"
        body = "dave was here"
        ext = mac.generate_ext(content_type, body)
        self.assertEqual(ext, mock_sha1.return_value.hexdigest.return_value)
        self.assertEqual(mock_sha1.call_args_list, [call(content_type + body)])


class BuildNormalizedRequestStringTestCase(unittest.TestCase):
    def test_generate_concatenates_request_elements_as_per_rfc(self):
        # This is the example from the RFC:
        # http://tools.ietf.org/html/draft-ietf-oauth-v2-http-mac-02#section-3.2.1
        actual = mac.build_normalized_request_string(
            '264095',
            '7d8f3e4a',
            'POST',
            'example.com',
            80,
            '/request?b5=%3D%253D&a3=a&c%40=&a2=r%20b&c2&a3=2+q',
            'a,b,c')
        expected = '''264095
7d8f3e4a
POST
/request?b5=%3D%253D&a3=a&c%40=&a2=r%20b&c2&a3=2+q
example.com
80
a,b,c
'''
        self.assertEqual(expected, actual)


class GenerateNonceTestCase(unittest.TestCase):
    @patch('lcp.mac.base64.b64encode')
    @patch('lcp.mac.os.urandom')
    def test_returns_b64_encoded_random_string(self, mock_urandom, mock_b64encode):
        self.assertEqual(mock_b64encode.return_value, mac.generate_nonce())
        self.assertEqual(mock_b64encode.call_args_list, [
            call(mock_urandom.return_value)])
        self.assertEquals(mock_urandom.call_args_list, [call(8)])


class GenerateSignatureTestCase(unittest.TestCase):
    @patch('lcp.mac.base64.b64encode')
    @patch('lcp.mac.keyczar.keys.HmacKey')
    def test_returns_signature(self, mock_HmacKey, mock_b64encode):
        self.assertEquals(
            mac.generate_signature(sentinel.MAC_KEY, sentinel.NORMALIZED_REQUEST_STRING),
            mock_b64encode.return_value)
        self.assertEquals(mock_b64encode.call_args_list, [
            call(mock_HmacKey.return_value.Sign.return_value)])
        self.assertEquals(mock_HmacKey.call_args_list, [call(sentinel.MAC_KEY)])
        self.assertEquals(mock_HmacKey.return_value.Sign.call_args_list, [
            call(sentinel.NORMALIZED_REQUEST_STRING)])


class VerifySignatureTestCase(unittest.TestCase):
    @patch('lcp.mac.keyczar.util.Base64WSDecode')
    @patch('lcp.mac.keyczar.keys.HmacKey')
    def test_valid_signature_calls_HmacKey_verify(self, mock_HmacKey, mock_Base64WSDecode):
        mac.verify_signature(
            sentinel.SIGNATURE, sentinel.SHARED_SECRET,
            sentinel.NORMALIZED_REQUEST_STRING)
        self.assertEquals(mock_HmacKey.call_args_list, [
            call(sentinel.SHARED_SECRET)])
        self.assertEquals(mock_Base64WSDecode.call_args_list, [
            call(sentinel.SIGNATURE)])
        self.assertEquals(mock_HmacKey.return_value.Verify.call_args_list, [
            call(sentinel.NORMALIZED_REQUEST_STRING, mock_Base64WSDecode.return_value)])

    @patch('lcp.mac.keyczar.util.Base64WSDecode')
    @patch('lcp.mac.keyczar.keys.HmacKey')
    def test_invalid_signature_raises(self, mock_HmacKey, mock_Base64WSDecode):
        mock_HmacKey.return_value.Verify.return_value = False
        with self.assertRaises(mac.InvalidSignature):
            mac.verify_signature(
                sentinel.SIGNATURE, sentinel.SHARED_SECRET,
                sentinel.NORMALIZED_REQUEST_STRING)


class GenerateAuthorizationHeaderValueTestCase(unittest.TestCase):
    def setUp(self):
        self.mock_time = patch('lcp.mac.time.time').start()
        self.mock_generate_nonce = patch('lcp.mac.generate_nonce').start()
        self.mock_generate_ext = patch('lcp.mac.generate_ext').start()
        self.mock_build_normalized_request_string = patch(
            'lcp.mac.build_normalized_request_string').start()
        self.mock_generate_signature = patch('lcp.mac.generate_signature').start()

        self.mock_time.return_value = 42
        self.mock_generate_nonce.return_value = 'NONCE'
        self.mock_generate_ext.return_value = 'EXT'
        self.mock_generate_signature.return_value = 'SIGNATURE'

    def tearDown(self):
        patch.stopall()

    def test_returns_authorization_header_as_per_rfc(self):
        # http://tools.ietf.org/html/draft-ietf-oauth-v2-http-mac-02#section-3.1
        retval = mac.generate_authorization_header_value(
            'METHOD', 'http://HOST:8008/PATH', 'KEY_ID', 'SECRET', 'CONTENT_TYPE',
            'BODY')
        self.assertEquals(
            retval, 'MAC id="KEY_ID", ts="42", nonce="NONCE", ext="EXT", mac="SIGNATURE"')

    def test_calls_all_dependencies(self):
        mac.generate_authorization_header_value(
            'METHOD', 'http://HOST:8008/PATH', 'KEY_ID', 'SECRET', 'CONTENT_TYPE',
            'BODY')
        self.assertEquals(self.mock_time.call_args_list, [call()])
        self.assertEquals(self.mock_generate_nonce.call_args_list, [call()])
        self.assertEquals(self.mock_generate_ext.call_args_list, [
            call('CONTENT_TYPE', 'BODY')])
        self.assertEquals(self.mock_generate_signature.call_args_list, [
            call('SECRET', self.mock_build_normalized_request_string.return_value)])


class VerifyTimeStampTestCase(unittest.TestCase):
    def setUp(self):
        self.mock_time = patch('lcp.mac.time.time', return_value=0).start()
        self.mock_logger = patch('lcp.mac.logger').start()

    def tearDown(self):
        patch.stopall()

    def test_accepts_recent_timestamp_without_logging(self):
        mac.verify_timestamp(-1)
        self.assertEquals(self.mock_logger.warning.call_args_list, [])
        self.assertEquals(self.mock_logger.info.call_args_list, [])

    def test_accepts_timestamp_as_string(self):
        mac.verify_timestamp("-1")

    def test_accepts_and_logs_timestamp_a_little_in_the_future(self):
        mac.verify_timestamp(mac.TIMESTAMP_MAX_SECONDS)
        self.assertEquals(self.mock_logger.info.call_args_list, [
            call("Accepting timestamp %ss in the future.", mac.TIMESTAMP_MAX_SECONDS)])

    def test_rejects_and_logs_timestamp_to_far_in_the_future(self):
        with self.assertRaises(mac.InvalidTimeStamp):
            mac.verify_timestamp(mac.TIMESTAMP_MAX_SECONDS + 1)
        self.assertEquals(self.mock_logger.warning.call_args_list, [
            call("Rejecting timestamp %ss in the future.", mac.TIMESTAMP_MAX_SECONDS + 1)])

    def test_rejects_and_logs_timestamp_too_old(self):
        with self.assertRaises(mac.InvalidTimeStamp):
            mac.verify_timestamp(-mac.TIMESTAMP_MAX_SECONDS - 1)
        self.assertEquals(self.mock_logger.warning.call_args_list, [
            call("Rejecting timestamp %ss in the past.", mac.TIMESTAMP_MAX_SECONDS + 1)])


class AuthHeaderValueTestCase(unittest.TestCase):
    def _create_ahv_str(
            self, mac_key_identifier='FAKE_ID', ts='42', nonce='FAKE_NONCE',
            ext='FAKE_EXT', mac='FAKE_MAC'):
        fmt = 'MAC id="%s", ts="%s", nonce="%s", ext="%s", mac="%s"'
        return fmt % (mac_key_identifier, ts, nonce, ext, mac)

    def test_string_representation_include_all_parameters_as_per_rfc(self):
        actual = '%s' % mac.AuthHeaderValue('FAKE_ID', '42', 'FAKE_NONCE', 'FAKE_EXT', 'FAKE_MAC')
        self.assertEquals(self._create_ahv_str(), actual)

    def test_parse_extracts_all_parameters(self):
        actual = mac.AuthHeaderValue.parse(self._create_ahv_str())
        self.assertEquals(actual.mac_key_identifier, 'FAKE_ID')
        self.assertEquals(actual.ts, '42')
        self.assertEquals(actual.nonce, 'FAKE_NONCE')
        self.assertEquals(actual.ext, 'FAKE_EXT')
        self.assertEquals(actual.mac, 'FAKE_MAC')

    @patch('lcp.mac.logger')
    def test_parse_logs_valid_format(self, mock_logger):
        mac.AuthHeaderValue.parse(self._create_ahv_str())
        self.assertEquals(mock_logger.info.call_args_list, [
            call("Valid format for authorization header %r", self._create_ahv_str())])

    @patch('lcp.mac.logger')
    def assert_parse_logs_and_raises(self, header_value, mock_logger):
        with self.assertRaises(mac.InvalidAuthHeader):
            mac.AuthHeaderValue.parse(header_value)
        self.assertEquals(mock_logger.warning.call_args_list, [
            call("Invalid format for authorization header %r", header_value)])

    def test_parse_with_empty_mac_key_identifier_logs_and_raises(self):
        self.assert_parse_logs_and_raises(self._create_ahv_str(mac_key_identifier=""))

    def test_parse_with_empty_timestamp_logs_and_raises(self):
        self.assert_parse_logs_and_raises(self._create_ahv_str(ts=""))

    def test_parse_with_empty_nonce_logs_and_raises(self):
        self.assert_parse_logs_and_raises(self._create_ahv_str(nonce=""))

    def test_parse_with_empty_mac_logs_and_raises(self):
        self.assert_parse_logs_and_raises(self._create_ahv_str(mac=""))

    def test_parse_with_invalid_header_logs_and_raises(self):
        self.assert_parse_logs_and_raises("foo")

    def test_parse_with_empty_header_logs_and_raises(self):
        self.assert_parse_logs_and_raises("")

    def test_parse_with_none_header_logs_and_raises(self):
        self.assert_parse_logs_and_raises(None)
