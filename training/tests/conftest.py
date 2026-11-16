import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
FIRMWARE = REPO / "firmware"


@pytest.fixture(scope="session")
def host_check(tmp_path_factory) -> Path:
    """The firmware's portable C code, compiled for this machine."""
    gcc = shutil.which("gcc") or shutil.which("cc")
    if gcc is None:
        pytest.skip("no C compiler available")
    exe = tmp_path_factory.mktemp("host") / "host_check"
    subprocess.run(
        [
            gcc,
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-O1",
            "-I",
            str(FIRMWARE / "components/model_store/include"),
            "-I",
            str(FIRMWARE / "components/inference/include"),
            str(FIRMWARE / "test_host/host_check.c"),
            str(FIRMWARE / "components/model_store/model_manifest.c"),
            str(FIRMWARE / "components/inference/preprocess.c"),
            "-lm",
            "-o",
            str(exe),
        ],
        check=True,
    )
    return exe
