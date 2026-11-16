import pytest

from edgeml import bench_compare

LOG = """\
\x1b[0;32mI (635) inference: Interpreter ready, arena 40 of 160 KB used\x1b[0m
BENCH {"image":"g0","bytes":93422,"top":0,"q":[125,-125,-127],"decode_us":71336,"invoke_us":15367,"gray_crc":"11bc9f3a"}
GRAY g0 0 000102
GRAY g0 3 0a0b
BENCH_DONE {"ok":true,"model_version":1,"arena_used":41164,"runs":1}
"""


def test_parse_log():
    parsed = bench_compare.parse_log(LOG)
    assert parsed["results"]["g0"]["q"] == [125, -125, -127]
    assert parsed["gray"]["g0"] == bytes([0, 1, 2, 10, 11])
    assert parsed["summary"]["arena_used"] == 41164


def test_gap_in_dump_is_an_error():
    with pytest.raises(ValueError, match="gap"):
        bench_compare.parse_log("GRAY g0 0 0001\nGRAY g0 5 02\n")


def test_unfinished_run_is_an_error(tmp_path):
    with pytest.raises(SystemExit, match="did not finish"):
        bench_compare.compare('BENCH {"image":"g0"}\n', b"", tmp_path)
