"""Fail when public-release files contain secrets, personal details, or excluded branding."""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_PARTS = {
    ".git",
    ".local",
    ".terraform",
    ".venv",
    "__pycache__",
    "artifacts",
    "data/generated",
    "dbt_packages",
    "logs",
    "output",
    "target",
}
TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".ps1",
    ".py",
    ".sql",
    ".tf",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}

excluded_brand = "".join(chr(code) for code in (119, 111, 111, 109))
forbidden_literals = {
    "nick" + "accturk": "personal account identifier",
    "na" + "pet": "local account identifier",
    "begin " + "private key": "private key material",
    "private" + "_key_id": "service-account key field",
    "private" + "_key": "service-account key field",
    excluded_brand: "excluded real-company reference",
    f"{excluded_brand}.com": "excluded real-company URL",
}
home_path = re.compile(r"(?i)(?:[a-z]:\\users\\|/" + "home" + r"/)[^/\\\s]+")
email = re.compile(r"(?i)\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b")
allowed_email_domains = {
    "example.com",
    "gserviceaccount.com",
    "rider360.example",
    "tracegate-r7m5o9ld.iam",
}


def _is_skipped(path: Path) -> bool:
    relative = path.relative_to(ROOT).as_posix()
    return any(relative == part or relative.startswith(f"{part}/") for part in SKIP_PARTS)


def _scan_text(label: str, text: str) -> list[str]:
    lowered = text.lower()
    failures = [
        f"{label}: {reason}" for literal, reason in forbidden_literals.items() if literal in lowered
    ]
    if home_path.search(text):
        failures.append(f"{label}: absolute personal home path")
    for match in email.finditer(text):
        domain = match.group(0).rsplit("@", 1)[1].lower()
        if not any(
            domain == allowed or domain.endswith(f".{allowed}") for allowed in allowed_email_domains
        ):
            failures.append(f"{label}: personal/unapproved email address")
    return failures


def _notebook_text(path: Path) -> str:
    notebook = json.loads(path.read_text(encoding="utf-8"))
    chunks: list[str] = []
    for cell in notebook.get("cells", []):
        chunks.extend(cell.get("source", []))
        for output in cell.get("outputs", []):
            chunks.extend(output.get("text", []))
            plain = output.get("data", {}).get("text/plain", [])
            chunks.extend(plain if isinstance(plain, list) else [plain])
    return "".join(chunks)


def _pptx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        return "".join(
            archive.read(name).decode("utf-8", errors="replace")
            for name in archive.namelist()
            if name.endswith(".xml") or name.endswith(".rels")
        )


def main() -> int:
    failures: list[str] = []
    scanned = 0
    for path in ROOT.rglob("*"):
        if not path.is_file() or _is_skipped(path):
            continue
        relative = path.relative_to(ROOT).as_posix()
        try:
            if path.suffix == ".ipynb":
                text = _notebook_text(path)
            elif path.suffix == ".pptx":
                text = _pptx_text(path)
            elif path.suffix.lower() in TEXT_SUFFIXES or path.name in {
                "LICENSE",
                ".dockerignore",
                ".env.example",
                ".gitignore",
            }:
                text = path.read_text(encoding="utf-8")
            else:
                continue
        except (OSError, UnicodeError, ValueError, zipfile.BadZipFile) as error:
            failures.append(f"{relative}: could not inspect public artifact ({error})")
            continue
        scanned += 1
        failures.extend(_scan_text(relative, text))

    if failures:
        print("Public-release audit failed:")
        for failure in sorted(set(failures)):
            print(f"- {failure}")
        return 1
    print(f"Public-release audit passed for {scanned} text-bearing files and artifacts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
