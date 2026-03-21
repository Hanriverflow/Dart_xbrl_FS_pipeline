from __future__ import annotations

import zipfile
from pathlib import Path

from dart_xbrl_pipeline.opendart import OpenDartClient


def _write_corp_code_zip(path: Path, corp_name: str = "테스트기업", corp_code: str = "00000000") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    xml_body = f"""<?xml version="1.0" encoding="utf-8"?>
<result>
  <list>
    <corp_name>{corp_name}</corp_name>
    <corp_code>{corp_code}</corp_code>
  </list>
</result>
"""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("CORPCODE.xml", xml_body)


def test_find_corp_code_by_name_reuses_fresh_cache(tmp_path: Path, monkeypatch) -> None:
    client = OpenDartClient(api_key="test-key")
    cache_dir = tmp_path / "corp-cache"
    download_calls: list[int] = []

    def fake_download(output_dir: Path) -> Path:
        download_calls.append(1)
        zip_path = output_dir / "corpCode.zip"
        _write_corp_code_zip(zip_path)
        return zip_path

    monkeypatch.setattr(client, "download_corp_codes", fake_download)

    first = client.find_corp_code_by_name("테스트기업", cache_dir)
    second = client.find_corp_code_by_name("테스트기업", cache_dir)

    assert first == "00000000"
    assert second == "00000000"
    assert len(download_calls) == 1
