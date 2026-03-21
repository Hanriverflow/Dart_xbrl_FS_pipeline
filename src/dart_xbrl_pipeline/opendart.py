from __future__ import annotations

import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

import httpx
from tenacity import retry, stop_after_attempt, wait_fixed

from .models import Filing

BASE_URL = "https://opendart.fss.or.kr/api"


class OpenDartClient:
    def __init__(self, api_key: str | None = None, timeout: int = 30):
        self.api_key = api_key or os.getenv("OPENDART_API_KEY")
        if not self.api_key:
            raise ValueError("OPENDART_API_KEY가 필요합니다. .env 파일 또는 환경변수에 설정하세요.")
        self.client = httpx.Client(timeout=timeout)

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    def download_corp_codes(self, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        zip_path = output_dir / "corpCode.zip"
        response = self.client.get(
            f"{BASE_URL}/corpCode.xml",
            params={"crtfc_key": self.api_key},
        )
        response.raise_for_status()
        zip_path.write_bytes(response.content)
        return zip_path

    @staticmethod
    def _is_cache_fresh(path: Path) -> bool:
        if not path.exists():
            return False
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).date()
        return modified == datetime.now(timezone.utc).date()

    def _get_corp_codes_zip(self, cache_dir: Path) -> Path:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cached_zip = cache_dir / "corpCode.zip"
        if self._is_cache_fresh(cached_zip):
            return cached_zip
        return self.download_corp_codes(cache_dir)

    def find_corp_code_by_name(self, corp_name: str, cache_dir: Path) -> str:
        zip_path = self._get_corp_codes_zip(cache_dir)
        with zipfile.ZipFile(zip_path, "r") as zf:
            xml_name = next(name for name in zf.namelist() if name.lower().endswith(".xml"))
            xml_bytes = zf.read(xml_name)
        root = ET.fromstring(xml_bytes)
        normalized_target = corp_name.replace(" ", "")
        for item in root.findall("list"):
            name = (item.findtext("corp_name") or "").strip()
            code = (item.findtext("corp_code") or "").strip()
            if name.replace(" ", "") == normalized_target and code:
                return code
        raise ValueError(f"회사명으로 corp_code를 찾지 못했습니다: {corp_name}")

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    def search_filings(
        self,
        corp_code: str | None = None,
        bgn_de: str | None = None,
        end_de: str | None = None,
        pblntf_ty: str = "A",
        pblntf_detail_ty: str = "A001",
        page_count: int = 100,
    ) -> list[Filing]:
        response = self.client.get(
            f"{BASE_URL}/list.json",
            params={
                "crtfc_key": self.api_key,
                "corp_code": corp_code,
                "bgn_de": bgn_de,
                "end_de": end_de,
                "pblntf_ty": pblntf_ty,
                "pblntf_detail_ty": pblntf_detail_ty,
                "page_count": page_count,
                "sort": "date",
                "sort_mth": "desc",
                "last_reprt_at": "Y",
            },
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "000":
            raise RuntimeError(f"공시검색 실패: {payload.get('message')}")
        return [
            Filing(
                corp_name=item.get("corp_name", ""),
                corp_code=item.get("corp_code"),
                stock_code=item.get("stock_code"),
                report_name=item.get("report_nm", ""),
                rcept_no=item.get("rcept_no", ""),
                rcept_dt=item.get("rcept_dt", ""),
                corp_cls=item.get("corp_cls"),
                flr_nm=item.get("flr_nm"),
            )
            for item in payload.get("list", [])
        ]

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    def download_xbrl_zip(self, rcept_no: str, reprt_code: str, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        zip_path = output_dir / f"{rcept_no}_{reprt_code}.zip"
        response = self.client.get(
            f"{BASE_URL}/fnlttXbrl.xml",
            params={
                "crtfc_key": self.api_key,
                "rcept_no": rcept_no,
                "reprt_code": reprt_code,
            },
        )
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "application/xml" in content_type or response.text.startswith("<?xml"):
            raise RuntimeError(f"XBRL 다운로드 실패: {response.text[:300]}")
        zip_path.write_bytes(response.content)
        return zip_path

    def extract_zip(self, zip_path: Path, output_dir: Path) -> Path:
        target = output_dir / zip_path.stem
        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(target)
        return target
