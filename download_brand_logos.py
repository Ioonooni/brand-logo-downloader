from __future__ import annotations

import os
import re
import time
from pathlib import Path
from urllib.parse import quote

import requests


OUTPUT_DIR = Path("mobile-brand-logos")
LOGO_SIZE = 512
TIMEOUT = 30
MAX_RETRIES = 3

BRANDS = [
    "Poco", "iQOO", "OnePlus", "Sony", "Nokia", "ZTE", "Tecno",
    "Black Shark", "HTC", "BlackBerry", "Nubia", "LG", "Lenovo",
    "i-mobile", "Sharp", "Lenovo", "Microsoft", "Amazon", "Garmin",
    "OnePlus", "Fitbit", "Amazfit", "Fossil", "Suunto", "COROS",
    "Polar", "Haylou", "imoo", "CMF", "Mobvoi", "Dell", "HP",
    "Lenovo", "Acer", "MSI", "Microsoft", "Razer", "LG", "Sony",
    "VAIO", "Toshiba", "Dynabook", "Fujitsu", "Chuwi", "NEC",
    "Compaq", "Gigabyte", "Alienware", "Sony", "Nintendo",
    "Microsoft", "Logitech", "Razer", "JBL", "Other",
]

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def unique_brands(names: list[str]) -> list[str]:
    """ลบชื่อซ้ำ โดยรักษาลำดับเดิมไว้"""
    result = []
    seen = set()

    for name in names:
        key = name.strip().casefold()

        if key and key not in seen:
            seen.add(key)
            result.append(name.strip())

    return result


def slugify(name: str) -> str:
    """แปลงชื่อแบรนด์เป็นชื่อไฟล์ภาษาอังกฤษตัวพิมพ์เล็ก"""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower())
    return slug.strip("-")


BRAND_DOMAINS = {
    "Chuwi": "chuwi.com",
}


def build_url(brand: str, token: str) -> str:
    """สร้าง URL สำหรับดาวน์โหลด PNG จาก Logo.dev"""

    domain = BRAND_DOMAINS.get(brand)

    if domain:
        identifier = domain
        endpoint = "https://img.logo.dev"
    else:
        identifier = quote(brand, safe="")
        endpoint = "https://img.logo.dev/name"

    return (
        f"{endpoint}/{identifier}"
        f"?token={token}"
        f"&format=png"
        f"&size={LOGO_SIZE}"
        f"&fallback=404"
    )


def download_logo(
    session: requests.Session,
    brand: str,
    token: str,
) -> tuple[bool, str]:
    filename = f"logo-{slugify(brand)}.png"
    output_path = OUTPUT_DIR / filename

    if output_path.exists() and output_path.stat().st_size > 0:
        return True, f"มีไฟล์แล้ว: {filename}"

    url = build_url(brand, token)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(url, timeout=TIMEOUT)

            if response.status_code == 404:
                return False, "ไม่พบโลโก้"

            if response.status_code == 429 or response.status_code >= 500:
                if attempt < MAX_RETRIES:
                    time.sleep(attempt * 2)
                    continue

            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "").lower()

            if "image/png" not in content_type:
                return False, f"ไฟล์ที่ได้รับไม่ใช่ PNG: {content_type}"

            if not response.content.startswith(PNG_SIGNATURE):
                return False, "ข้อมูลไฟล์ไม่มี PNG signature"

            temporary_path = output_path.with_suffix(".png.part")
            temporary_path.write_bytes(response.content)
            temporary_path.replace(output_path)

            size_kb = output_path.stat().st_size / 1024
            return True, f"{filename} ({size_kb:.1f} KB)"

        except requests.Timeout:
            error = "หมดเวลารอการตอบกลับ"

        except requests.ConnectionError:
            error = "เชื่อมต่ออินเทอร์เน็ตไม่ได้"

        except requests.RequestException as exc:
            error = f"Request error: {exc}"

        except OSError as exc:
            return False, f"บันทึกไฟล์ไม่ได้: {exc}"

        if attempt < MAX_RETRIES:
            time.sleep(attempt * 2)
        else:
            return False, error

    return False, "เกิดข้อผิดพลาดไม่ทราบสาเหตุ"


def main() -> None:
    token = os.getenv("LOGO_DEV_TOKEN", "").strip()

    if not token:
        raise SystemExit(
            "\nERROR: ยังไม่ได้ตั้งค่า LOGO_DEV_TOKEN\n"
            "เราจะตั้งค่าในขั้นตอนถัดไป\n"
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    brands = [
        brand
        for brand in unique_brands(BRANDS)
        if brand.casefold() != "other"
    ]

    success = []
    failed = []

    print(f"กำลังดาวน์โหลด {len(brands)} แบรนด์")
    print(f"ปลายทาง: {OUTPUT_DIR.resolve()}\n")

    with requests.Session() as session:
        session.headers.update({
            "Accept": "image/png",
            "User-Agent": "brand-logo-downloader/1.0",
        })

        for index, brand in enumerate(brands, start=1):
            ok, message = download_logo(session, brand, token)

            if ok:
                success.append(brand)
                status = "OK"
            else:
                failed.append((brand, message))
                status = "ERROR"

            print(f"[{index:02d}/{len(brands):02d}] {status} {brand}: {message}")
            time.sleep(0.3)

    print("\n===== สรุปผล =====")
    print(f"สำเร็จ: {len(success)}")
    print(f"ไม่สำเร็จ: {len(failed)}")

    if failed:
        print("\nรายการที่ไม่สำเร็จ:")

        for brand, reason in failed:
            print(f"- {brand}: {reason}")


if __name__ == "__main__":
    main()
