# Device → ingest protocol

One HTTP request per event. The device has no other way of talking to the
outside world.

## Request

```
POST /v1/events
Authorization: Bearer <device token>
X-Event-Meta: <single-line JSON, see below>
Content-Type: image/jpeg          (only when a body is sent)

<JPEG bytes, or empty>
```

Metadata travels in a header and the image is the raw body, so the device
sends the camera buffer as it is: no multipart encoding, no copy.

### Metadata

| Field | Type | Meaning |
|---|---|---|
| `v` | int | Schema version, `1` |
| `device` | string | `esp32s3-` + last three bytes of the MAC |
| `fw` | string | Firmware version |
| `session` | 8 hex chars | Random per power cycle |
| `seq` | int | Event number within the session |
| `wake` | `pir` / `timer` / `power_on` | Why the device woke |
| `mode` | `collect` / `infer` / `bench` | Operating mode |
| `ts` | int | Device clock (Unix time), `0` until the server has set it |
| `dropped` | int | Events lost (upload failed) since the last success |
| `rssi` | int | Wi-Fi signal, dBm |
| `image` | bool | Whether the body carries the JPEG |
| `frame` | `{w, h, bytes}` | The captured frame |
| `t_ms` | `{cam_init, grab, wifi, awake}` | Time spent in each stage, ms |
| `model` | `{version, label, top, q, decode_us, invoke_us}` | Infer mode: result and timings. `q` holds the raw int8 outputs |

`device`, `session` and `seq` identify an event and form its storage path.
Unknown fields are stored as received, so firmware can add data without a
server change.

Example, printed by the firmware running in the emulator:

```json
{"v":1,"device":"esp32s3-000000","fw":"1","session":"9519e175","seq":0,"wake":"pir","mode":"bench","ts":0,"dropped":0,"rssi":0,"image":false,"frame":{"w":1024,"h":768,"bytes":98765},"t_ms":{"cam_init":0,"grab":0,"wifi":0,"awake":1740},"model":{"version":1,"label":"animal","top":2,"q":[-128,-128,127],"decode_us":48721,"invoke_us":13330}}
```

## Response

| Status | Meaning |
|---|---|
| `201` | Stored |
| `200` | Already stored (a retry); nothing is overwritten |
| `400` | Missing or malformed metadata, or body is not a complete JPEG / does not match `image` |
| `401` | Wrong or missing token |
| `413` | Image over 2 MB or metadata over 4 KB |
| `422` | Metadata fails validation |

```json
{"id": "esp32s3-a1b2c3/0f3a9c21/000004", "stored_image": true, "server_time": 1794860258}
```

The device sets its clock from `server_time`, so it needs no NTP round trip.

## Storage layout

```
captures/<device>/<session>/<seq>.jpg     the image, when one was sent
captures/<device>/<session>/<seq>.json    metadata + received_at, image_sha256
```

The `.json` file is written last: if it exists, the event is complete.

## Security notes

- The token is a shared secret sent in clear over `http://`. That is acceptable
  on a home network for development; anything reachable from outside must use
  `https://` (the firmware verifies the server against its certificate bundle).
- Path components are validated against a strict alphabet before use.
