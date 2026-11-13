from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


@pytest.mark.skipif(shutil.which("bash") is None, reason="butuh bash")
def test_install_sh_syntax_is_valid() -> None:
    assert subprocess.run(["bash", "-n", str(SCRIPTS / "install.sh")]).returncode == 0


@pytest.mark.parametrize("name", ["install.sh", "install.ps1"])
def test_installers_never_run_sudo_and_never_overwrite_user_config(name: str) -> None:
    text = (SCRIPTS / name).read_text(encoding="utf-8")
    # sudo hanya boleh muncul sebagai petunjuk yang dicetak, bukan perintah yang dijalankan
    for line in text.splitlines():
        if re.search(r"\bsudo\b", line):
            assert line.lstrip().startswith(("echo", "warn", "#", "Write-Host", "Warn")), line
    assert "config.yaml" in text and "tidak diubah" in text  # config pengguna dipertahankan


def test_both_installers_create_launcher_with_api_enabled() -> None:
    sh = (SCRIPTS / "install.sh").read_text(encoding="utf-8")
    ps = (SCRIPTS / "install.ps1").read_text(encoding="utf-8")
    for text, launcher in ((sh, "run.sh"), (ps, "run.cmd")):
        assert launcher in text
        assert "enabled: true" in text  # ui.api untuk Isla Desk
        assert "island:" in text  # status suara & kartu izin tampil di pulau Isla
        assert "--listen" in text
