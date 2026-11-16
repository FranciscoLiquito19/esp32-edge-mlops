import json

import pytest
from fastapi.testclient import TestClient

from ingest_service.app import MAX_IMAGE_BYTES, create_app
from ingest_service.storage import GcsStorage, LocalStorage, from_spec

TOKEN = "test-token"
JPEG = b"\xff\xd8" + b"\x00" * 100 + b"\xff\xd9"

# The shape firmware/main/main.c builds for a collect-mode event.
FIRMWARE_META = (
    '{"v":1,"device":"esp32s3-a1b2c3","fw":"46e5119","session":"0f3a9c21","seq":4,"wake":"pir",'
    '"mode":"collect","ts":0,"dropped":0,"rssi":-58,"image":true,'
    '"frame":{"w":1024,"h":768,"bytes":104},'
    '"t_ms":{"cam_init":412,"grab":655,"wifi":1830,"awake":2260}}'
)
# And for an infer-mode event that keeps only the result.
FIRMWARE_META_INFER = (
    '{"v":1,"device":"esp32s3-a1b2c3","fw":"46e5119","session":"0f3a9c21","seq":5,"wake":"pir",'
    '"mode":"infer","ts":1794860000,"dropped":1,"rssi":-61,"image":false,'
    '"frame":{"w":1024,"h":768,"bytes":98211},'
    '"t_ms":{"cam_init":405,"grab":640,"wifi":1712,"awake":2390},'
    '"model":{"version":3,"label":"nothing","top":0,"q":[120,-121,-127],"decode_us":51200,"invoke_us":9400}}'
)

# Printed by the real firmware running in the emulator (tools/qemu_bench.sh), byte for byte.
EMULATOR_META = (
    '{"v":1,"device":"esp32s3-000000","fw":"1","session":"9519e175","seq":0,"wake":"pir","mode":"bench",'
    '"ts":0,"dropped":0,"rssi":0,"image":false,"frame":{"w":1024,"h":768,"bytes":98765},'
    '"t_ms":{"cam_init":0,"grab":0,"wifi":0,"awake":1740},'
    '"model":{"version":1,"label":"animal","top":2,"q":[-128,-128,127],"decode_us":48721,"invoke_us":13330}}'
)


@pytest.fixture
def root(tmp_path):
    return tmp_path / "store"


@pytest.fixture
def client(root):
    return TestClient(create_app(LocalStorage(root), TOKEN))


def post(client, meta=FIRMWARE_META, body=JPEG, token=TOKEN):
    headers = {"X-Event-Meta": meta if isinstance(meta, str) else json.dumps(meta)}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    if body:
        headers["Content-Type"] = "image/jpeg"
    return client.post("/v1/events", headers=headers, content=body)


def meta(**changes) -> dict:
    return {**json.loads(FIRMWARE_META), **changes}


def test_event_with_image_is_stored(client, root):
    response = post(client)

    assert response.status_code == 201
    reply = response.json()
    assert reply["id"] == "esp32s3-a1b2c3/0f3a9c21/000004"
    assert reply["stored_image"] is True
    assert reply["server_time"] > 1_700_000_000

    folder = root / "captures/esp32s3-a1b2c3/0f3a9c21"
    assert (folder / "000004.jpg").read_bytes() == JPEG
    record = json.loads((folder / "000004.json").read_text())
    assert record["wake"] == "pir"
    assert record["t_ms"]["wifi"] == 1830
    assert record["image_bytes"] == len(JPEG)
    assert len(record["image_sha256"]) == 64
    assert record["received_unix"] == reply["server_time"]


def test_result_only_event_is_stored_without_image(client, root):
    response = post(client, FIRMWARE_META_INFER, body=b"")

    assert response.status_code == 201
    assert response.json()["stored_image"] is False
    folder = root / "captures/esp32s3-a1b2c3/0f3a9c21"
    assert not (folder / "000005.jpg").exists()
    record = json.loads((folder / "000005.json").read_text())
    assert record["model"] == {
        "version": 3,
        "label": "nothing",
        "top": 0,
        "q": [120, -121, -127],
        "decode_us": 51200,
        "invoke_us": 9400,
    }


def test_metadata_printed_by_the_firmware_is_accepted(client, root):
    assert post(client, EMULATOR_META, body=b"").status_code == 201
    record = json.loads((root / "captures/esp32s3-000000/9519e175/000000.json").read_text())
    assert record["model"]["label"] == "animal"


def test_retry_of_the_same_event_is_not_stored_twice(client, root):
    assert post(client).status_code == 201
    first = (root / "captures/esp32s3-a1b2c3/0f3a9c21/000004.json").read_text()

    again = post(client, body=b"\xff\xd8different\xff\xd9")
    assert again.status_code == 200
    assert again.json()["duplicate"] is True
    assert (root / "captures/esp32s3-a1b2c3/0f3a9c21/000004.json").read_text() == first
    assert (root / "captures/esp32s3-a1b2c3/0f3a9c21/000004.jpg").read_bytes() == JPEG


@pytest.mark.parametrize("token", [None, "wrong", ""])
def test_bad_token_is_refused(client, root, token):
    assert post(client, token=token).status_code == 401
    assert not (root / "captures").exists()


def test_missing_metadata_is_refused(client):
    response = client.post("/v1/events", headers={"Authorization": f"Bearer {TOKEN}"}, content=JPEG)
    assert response.status_code == 400


def test_metadata_that_is_not_json_is_refused(client):
    assert post(client, "{not json").status_code == 400


@pytest.mark.parametrize(
    "changes",
    [
        {"v": 2},
        {"device": "../../etc"},
        {"device": "UPPER"},
        {"session": "xyz"},
        {"session": "../.."},
        {"seq": -1},
        {"wake": "magic"},
        {"mode": "other"},
    ],
)
def test_invalid_metadata_is_refused(client, root, changes):
    response = post(client, meta(**changes))
    assert response.status_code == 422
    assert not (root / "captures").exists()


def test_body_that_is_not_a_jpeg_is_refused(client):
    assert post(client, body=b"<html>hello</html>").status_code == 400


def test_truncated_jpeg_is_refused(client):
    assert post(client, body=JPEG[:-2]).status_code == 400


def test_image_flag_must_match_the_body(client):
    assert post(client, meta(image=False), body=JPEG).status_code == 400
    assert post(client, meta(image=True), body=b"").status_code == 400


def test_oversized_image_is_refused(client):
    big = b"\xff\xd8" + b"\x00" * MAX_IMAGE_BYTES + b"\xff\xd9"
    assert post(client, body=big).status_code == 413


def test_unknown_metadata_fields_are_kept(client, root):
    assert post(client, meta(battery_mv=3712)).status_code == 201
    record = json.loads((root / "captures/esp32s3-a1b2c3/0f3a9c21/000004.json").read_text())
    assert record["battery_mv"] == 3712


def test_healthz(client):
    assert client.get("/healthz").json()["ok"] is True


def test_app_needs_a_token(root):
    with pytest.raises(ValueError):
        create_app(LocalStorage(root), "")


def test_local_storage_refuses_to_leave_its_root(root):
    with pytest.raises(ValueError):
        LocalStorage(root).put("../outside.txt", b"x", "text/plain")


def test_storage_spec():
    with pytest.raises(ValueError):
        from_spec("ftp:somewhere")


class FakeBlob:
    def __init__(self, store, name):
        self.store, self.name = store, name

    def exists(self):
        return self.name in self.store

    def upload_from_string(self, data, content_type=None):
        self.store[self.name] = (data, content_type)


class FakeBucket:
    name = "my-bucket"

    def __init__(self):
        self.store = {}

    def blob(self, name):
        return FakeBlob(self.store, name)


def test_gcs_backend_stores_under_the_prefix():
    bucket = FakeBucket()
    client = TestClient(create_app(GcsStorage(bucket, prefix="edge/"), TOKEN))

    assert post(client).status_code == 201
    assert bucket.store["edge/captures/esp32s3-a1b2c3/0f3a9c21/000004.jpg"] == (JPEG, "image/jpeg")
    assert "edge/captures/esp32s3-a1b2c3/0f3a9c21/000004.json" in bucket.store
    assert post(client).json()["duplicate"] is True
