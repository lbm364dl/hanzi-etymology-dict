#!/usr/bin/env python3
"""Download Japanese kanji data sources required by build_kanji.py."""

import urllib.request
import urllib.error
import gzip
import shutil
from pathlib import Path

SOURCES_DIR = Path("sources")


def download_file(url, dest, desc=""):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        print(f"  Already have {dest.name}, skipping")
        return True
    print(f"  Downloading {desc or dest.name}...")
    try:
        urllib.request.urlretrieve(url, str(dest))
        size = dest.stat().st_size
        print(f"    OK ({size / 1024:.0f} KB) -> {dest}")
        return True
    except urllib.error.URLError as e:
        print(f"    FAILED: {e}")
        if dest.exists():
            dest.unlink()
        return False


def download_decompress(url, dest_gz, dest, desc=""):
    dest = Path(dest)
    dest_gz = Path(dest_gz)
    if dest.exists():
        print(f"  Already have {dest.name}, skipping")
        return True
    if download_file(url, dest_gz, desc):
        print(f"  Decompressing {dest_gz.name}...")
        with gzip.open(str(dest_gz), "rb") as f_in:
            with open(str(dest), "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        dest_gz.unlink()
        print(f"    OK -> {dest}")
        return True
    return False


def main():
    print("Downloading Japanese kanji sources...\n")

    # 1. davidluzgouveia/kanji-data (MIT)
    # ~2,000 kanji with JLPT levels, WaniKani levels, readings, meanings
    print("[1/3] davidluzgouveia/kanji-data (MIT):")
    download_file(
        "https://raw.githubusercontent.com/davidluzgouveia/kanji-data/master/kanji.json",
        SOURCES_DIR / "kanji-data" / "kanji.json",
        "kanji.json",
    )

    # 2. KANJIDIC2 XML (CC BY-SA 4.0) -- 13,108 kanji, definitive Japanese reference
    print("\n[2/3] KANJIDIC2 XML (EDRDG, CC BY-SA 4.0):")
    download_decompress(
        "https://www.edrdg.org/kanjidic/kanjidic2.xml.gz",
        SOURCES_DIR / "kanjidic2" / "kanjidic2.xml.gz",
        SOURCES_DIR / "kanjidic2" / "kanjidic2.xml",
        "kanjidic2.xml.gz",
    )

    # 3. scriptin/kanji-frequency (CC BY 4.0)
    # Frequency from Aozora Bunko (literary) and Wikipedia (encyclopedic)
    # Note: repo uses CSV format (not JSON)
    print("\n[3/3] scriptin/kanji-frequency (CC BY 4.0):")
    freq_dir = SOURCES_DIR / "kanji-frequency"
    base_url = "https://raw.githubusercontent.com/scriptin/kanji-frequency/master/data"
    for fname in [
        "aozora_characters.csv",
        "wikipedia_characters.csv",
        "news_characters.csv",
    ]:
        download_file(f"{base_url}/{fname}", freq_dir / fname, fname)

    print("\nDone! Now run: python build_kanji.py")


if __name__ == "__main__":
    main()
