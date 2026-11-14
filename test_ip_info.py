"""
Unit tests for ip_info.py (run with: python -m unittest -v)
Network calls are mocked, so the tests run without internet access.
"""
import json
import os
import tempfile
import unittest
from unittest import mock

import ip_info

IPAPI_SAMPLE = {
    "ip": "8.8.8.8", "version": "IPv4", "city": "Mountain View", "region": "California",
    "country_name": "United States", "country_code": "US", "postal": "94043",
    "latitude": 37.42, "longitude": -122.08, "timezone": "America/Los_Angeles",
    "utc_offset": "-0800", "asn": "AS15169", "org": "GOOGLE",
}
IP_API_SAMPLE = {
    "status": "success", "query": "1.1.1.1", "country": "Australia", "countryCode": "AU",
    "regionName": "Queensland", "city": "South Brisbane", "zip": "4101", "lat": -27.47,
    "lon": 153.02, "timezone": "Australia/Brisbane", "isp": "Cloudflare, Inc",
    "as": "AS13335 Cloudflare, Inc.",
}


class TestApiLayer(unittest.TestCase):
    def test_public_ipv4(self):
        with mock.patch.object(ip_info, "fetch_json", return_value={"ip": "203.0.113.5"}):
            self.assertEqual(ip_info.get_public_ipv4(), "203.0.113.5")

    def test_public_ipv6_rejects_ipv4_answer(self):
        with mock.patch.object(ip_info, "fetch_json", return_value={"ip": "203.0.113.5"}):
            self.assertIsNone(ip_info.get_public_ipv6())

    def test_public_ipv6(self):
        with mock.patch.object(ip_info, "fetch_json", return_value={"ip": "2001:db8::1"}):
            self.assertEqual(ip_info.get_public_ipv6(), "2001:db8::1")

    def test_details_primary(self):
        with mock.patch.object(ip_info, "fetch_json", return_value=IPAPI_SAMPLE):
            d = ip_info.get_ip_details("8.8.8.8")
        self.assertEqual(d["asn"], "AS15169")
        self.assertEqual(d["source"], "ipapi.co")

    def test_details_fallback_when_rate_limited(self):
        responses = [{"error": True, "reason": "RateLimited"}, IP_API_SAMPLE]
        with mock.patch.object(ip_info, "fetch_json", side_effect=responses):
            d = ip_info.get_ip_details("1.1.1.1")
        self.assertEqual(d["source"], "ip-api.com")
        self.assertEqual(d["asn"], "AS13335")
        self.assertEqual(d["version"], "IPv4")

    def test_details_both_fail(self):
        with mock.patch.object(ip_info, "fetch_json", return_value=None):
            self.assertIsNone(ip_info.get_ip_details("1.1.1.1"))


class TestOffline(unittest.TestCase):
    def test_analyze_private_ipv4(self):
        d = ip_info.analyze_ip("192.168.1.10")
        self.assertEqual(d["class"], "C")
        self.assertTrue(d["type"].startswith("Private"))
        self.assertEqual(d["binary"], "11000000.10101000.00000001.00001010")

    def test_analyze_ipv6(self):
        d = ip_info.analyze_ip("2001:4860:4860::8888")
        self.assertEqual(d["version"], "IPv6")
        self.assertEqual(d["exploded"], "2001:4860:4860:0000:0000:0000:0000:8888")

    def test_analyze_invalid(self):
        with self.assertRaises(ValueError):
            ip_info.analyze_ip("999.1.1.1")

    def test_subnet(self):
        d = ip_info.subnet_info("192.168.1.77/26")
        self.assertEqual(d["network"], "192.168.1.64")
        self.assertEqual(d["broadcast"], "192.168.1.127")
        self.assertEqual(d["usable_hosts"], 62)
        self.assertEqual(d["subnet_mask"], "255.255.255.192")

    def test_large_subnet(self):
        d = ip_info.subnet_info("10.0.0.0/8")
        self.assertEqual(d["last_usable"], "10.255.255.254")


class TestOutput(unittest.TestCase):
    def test_save_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = ip_info.save_json({"ip": "8.8.8.8"}, os.path.join(tmp, "r.json"))
            with open(path) as f:
                self.assertEqual(json.load(f)["result"]["ip"], "8.8.8.8")

    def test_cli_json(self):
        with mock.patch.object(ip_info, "fetch_json", return_value=IPAPI_SAMPLE), \
             mock.patch("builtins.print") as p:
            self.assertEqual(ip_info.main(["--lookup", "8.8.8.8", "--json"]), 0)
        self.assertIn("AS15169", p.call_args[0][0])

    def test_cli_invalid_ip(self):
        with mock.patch("builtins.print"):
            self.assertEqual(ip_info.main(["--lookup", "not-an-ip"]), 1)


if __name__ == "__main__":
    unittest.main()
