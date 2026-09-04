import hashlib
import tempfile
import unittest
from pathlib import Path

from ridescope.platforms import (
    IGPSportClient,
    OnelapClient,
    PlatformError,
    RemoteActivity,
    is_fit_file,
    save_downloaded_activity,
)


FIT_BYTES = b"\x0e\x10\x00\x00\x00\x00\x00\x00.FIT\x00\x00track"


class FakeResponse:
    def __init__(self, status_code=200, payload=None, content=b""):
        self.status_code = status_code
        self._payload = payload
        self.content = content

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if not self.responses:
            raise AssertionError("没有准备对应的模拟响应")
        return self.responses.pop(0)


class PlatformTests(unittest.TestCase):
    def test_igpsport_login_list_and_download(self):
        session = FakeSession(
            [
                FakeResponse(payload={"code": 0, "data": {"access_token": "igp-token"}}),
                FakeResponse(payload={"code": 0, "data": {"rows": [{"rideId": 7, "startTime": "2026.09.01 08:00:00", "distance": 25000}], "totalPage": 1}}),
                FakeResponse(payload={"code": 0, "data": "https://files.example/7.fit"}),
                FakeResponse(content=FIT_BYTES),
            ]
        )
        client = IGPSportClient(session=session)
        token = client.login("rider", "secret")
        activities = client.list_activities(token, 10)
        data = client.download_activity(token, activities[0])
        self.assertEqual(token, "igp-token")
        self.assertEqual(activities[0].activity_id, "7")
        self.assertEqual(activities[0].distance_km, 25.0)
        self.assertEqual(data, FIT_BYTES)
        self.assertEqual(session.calls[0][2]["json"]["appId"], "igpsport-web")
        self.assertEqual(session.calls[1][2]["headers"]["Authorization"], "Bearer igp-token")

    def test_onelap_login_list_and_download(self):
        session = FakeSession(
            [
                FakeResponse(payload={"code": 200, "data": [{"token": "one-token"}]}),
                FakeResponse(payload={"code": 200, "data": {"list": [{"id": "abc", "name": "晨骑", "start_riding_time": "2026-09-01 06:30:00", "distance_km": 32.5}], "pagination": {"has_more": False}}}),
                FakeResponse(payload={"code": 200, "data": {"ridingRecord": {"durl": "https://files.example/abc.fit", "fitUrl": "rides/abc.fit"}}}),
                FakeResponse(content=FIT_BYTES),
            ]
        )
        client = OnelapClient(session=session)
        token = client.login("13800000000", "secret")
        activities = client.list_activities(token, 5)
        data = client.download_activity(token, activities[0])
        expected_md5 = hashlib.md5(b"secret", usedforsecurity=False).hexdigest()
        self.assertEqual(session.calls[0][2]["json"]["password"], expected_md5)
        self.assertEqual(session.calls[1][2]["headers"]["Authorization"], "one-token")
        self.assertEqual(activities[0].title, "晨骑")
        self.assertEqual(data, FIT_BYTES)

    def test_invalid_fit_and_safe_storage(self):
        self.assertTrue(is_fit_file(FIT_BYTES))
        self.assertFalse(is_fit_file(b"not-fit"))
        activity = RemoteActivity("Onelap", "a/b", "ride", "2026-09-01 08:00:00")
        with tempfile.TemporaryDirectory() as temporary:
            path = save_downloaded_activity(Path(temporary), activity, FIT_BYTES)
            self.assertTrue(path.exists())
            self.assertNotIn("a/b", path.name)
            self.assertEqual(path.read_bytes(), FIT_BYTES)

    def test_onelap_falls_back_to_fit_content(self):
        session = FakeSession(
            [
                FakeResponse(payload={"code": 200, "data": {"ridingRecord": {"durl": "https://files.example/missing.fit", "fitUrl": "rides/new.fit"}}}),
                FakeResponse(status_code=404),
                FakeResponse(content=FIT_BYTES),
            ]
        )
        client = OnelapClient(session=session)
        activity = RemoteActivity("Onelap", "new-id", "新记录")
        self.assertEqual(client.download_activity("token", activity), FIT_BYTES)
        self.assertIn("fit_content", session.calls[-1][1])

    def test_igpsport_can_fetch_more_than_one_hundred(self):
        responses = []
        for page in range(1, 7):
            rows = [{"rideId": f"{page}-{index}", "startTime": "2026.09.01"} for index in range(20)]
            responses.append(FakeResponse(payload={"code": 0, "data": {"rows": rows, "totalPage": 6}}))
        session = FakeSession(responses)
        activities = IGPSportClient(session=session).list_activities("token", 105)
        self.assertEqual(len(activities), 105)
        self.assertEqual(len(session.calls), 6)

    def test_readable_login_error(self):
        client = IGPSportClient(session=FakeSession([FakeResponse(payload={"code": 1, "message": "bad credentials"})]))
        with self.assertRaisesRegex(PlatformError, "登录失败"):
            client.login("bad", "bad")


if __name__ == "__main__":
    unittest.main()
