"""Search and open files or folders in user-accessible locations."""

from __future__ import annotations

import os
import re
from pathlib import Path

from yuwontlaykit.tools.base import RiskLevel, ToolResult, failed, skipped
from yuwontlaykit.tools.runner import run_argv
from yuwontlaykit.tools.windows import powershell_json, run_powershell, windows_tools_available

READ = RiskLevel.READ_ONLY
LOW = RiskLevel.LOW_RISK_MODIFICATION

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff"}
SKIP_DIR_NAMES = {
    ".git",
    ".svn",
    "node_modules",
    "__pycache__",
    "AppData",
    "Library",
    ".cache",
    ".local",
    ".Trash",
}
KNOWN_FOLDER_NAMES = {
    "Downloads": "Downloads",
    "Documents": "Documents",
    "Desktop": "Desktop",
    "Pictures": "Pictures",
    "Videos": "Videos",
    "Home": "",
}


def search_user_files(
    query: str = "",
    kind: str = "file",
    limit: int = 8,
) -> ToolResult:
    needle = (query or "").strip()
    if not needle:
        return skipped(
            "search_user_files",
            READ,
            "I need a name to search for.",
        )
    roots = user_search_roots()
    if not roots:
        return failed("search_user_files", READ, "I could not find your user folders.")

    matches: list[dict[str, str]] = []
    scanned = 0
    tokens = [part for part in re.split(r"[\s_\-]+", needle.lower()) if part]
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [
                name
                for name in dirnames
                if name not in SKIP_DIR_NAMES and not name.startswith(".")
            ]
            rel = Path(dirpath)
            if kind in {"folder", "any"}:
                for name in dirnames:
                    scanned += 1
                    path = rel / name
                    score = _name_score(name, needle, tokens)
                    if score:
                        matches.append(
                            {
                                "name": name,
                                "path": str(path),
                                "kind": "folder",
                                "score": str(score),
                            }
                        )
            if kind in {"file", "image", "any"}:
                for name in filenames:
                    scanned += 1
                    path = rel / name
                    if kind == "image" and path.suffix.lower() not in IMAGE_EXTS:
                        continue
                    score = _name_score(name, needle, tokens)
                    if score:
                        matches.append(
                            {
                                "name": name,
                                "path": str(path),
                                "kind": "file",
                                "score": str(score),
                            }
                        )
            if scanned > 8000 or len(matches) >= 40:
                break
        if scanned > 8000 or len(matches) >= 40:
            break

    matches.sort(key=lambda row: (-int(row["score"]), row["name"].lower()))
    top = matches[: max(1, min(limit, 12))]
    return ToolResult(
        name="search_user_files",
        risk=READ,
        executed=True,
        available=True,
        success=True,
        data=top,
        summary=f"{len(top)} match(es) for '{needle}'.",
        extras={"query": needle, "kind": kind, "count": len(top), "matches": top},
    )


def open_path(path: str = "") -> ToolResult:
    target = Path(path).expanduser()
    if not _is_allowed_path(target):
        return skipped(
            "open_path",
            LOW,
            "I can only open files inside your usual folders.",
        )
    if not target.exists():
        return failed("open_path", LOW, "That file or folder is no longer there.")
    if windows_tools_available():
        return _open_windows_path(target)
    return _open_posix_path(target)


def resolve_known_folder(name: str = "") -> ToolResult:
    key = (name or "").strip()
    folder_name = KNOWN_FOLDER_NAMES.get(key, key)
    roots = _profile_roots()
    if not roots:
        return failed("resolve_known_folder", READ, "I could not find your user folder.")
    home = roots[0]
    target = home if folder_name in {"", "Home"} else home / folder_name
    if not target.is_dir():
        return failed(
            "resolve_known_folder",
            READ,
            f"I could not find your {key or 'home'} folder.",
        )
    return ToolResult(
        name="resolve_known_folder",
        risk=READ,
        executed=True,
        available=True,
        success=True,
        data={"path": str(target), "name": target.name or str(target)},
        summary=str(target),
        extras={"path": str(target), "name": target.name or "Home"},
    )


def user_search_roots() -> list[Path]:
    roots: list[Path] = []
    for home in _profile_roots():
        roots.append(home)
        for name in ("Desktop", "Documents", "Downloads", "Pictures", "Videos"):
            candidate = home / name
            if candidate.is_dir():
                roots.append(candidate)
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root.resolve()) if root.exists() else str(root)
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def _profile_roots() -> list[Path]:
    roots: list[Path] = []
    home = Path.home()
    if home.is_dir():
        roots.append(home)
    windows_home = _windows_home()
    if windows_home and windows_home.is_dir() and windows_home not in roots:
        roots.insert(0, windows_home)
    return roots


def _windows_home() -> Path | None:
    if not windows_tools_available():
        return None
    code, out, _ = run_powershell("Write-Output $env:USERPROFILE", timeout=8)
    raw = (out or "").strip().splitlines()
    text = raw[-1].strip() if raw else ""
    if not text:
        return None
    win = Path(text)
    if win.is_dir():
        return win
    converted = _to_wsl_path(text)
    if converted and converted.is_dir():
        return converted
    return None


def _to_wsl_path(windows_path: str) -> Path | None:
    match = re.match(r"^([A-Za-z]):\\(.*)$", windows_path)
    if not match:
        return None
    drive = match.group(1).lower()
    rest = match.group(2).replace("\\", "/")
    return Path(f"/mnt/{drive}/{rest}")


def _is_allowed_path(path: Path) -> bool:
    try:
        resolved = path.expanduser().resolve()
    except OSError:
        return False
    for root in user_search_roots():
        try:
            resolved.relative_to(root.resolve())
            return True
        except (OSError, ValueError):
            continue
    return False


def _name_score(name: str, query: str, tokens: list[str]) -> int:
    lowered = name.lower()
    stem = Path(name).stem.lower()
    q = query.lower()
    if lowered == q or stem == q:
        return 100
    if q in lowered or q in stem:
        return 80
    if tokens and all(token in lowered for token in tokens):
        return 60
    if tokens and any(token in lowered for token in tokens if len(token) > 2):
        return 30
    return 0


def _open_windows_path(path: Path) -> ToolResult:
    raw = str(path)
    if raw.startswith("/mnt/") and len(raw) > 6 and raw[6] == "/":
        drive = raw[5]
        rest = raw[7:].replace("/", "\\")
        raw = f"{drive.upper()}:\\{rest}"
    literal = raw.replace("'", "''")
    result = powershell_json(
        "open_path",
        f"""
$ErrorActionPreference = 'Stop'
$path = '{literal}'
if (-not (Test-Path -LiteralPath $path)) {{
  [pscustomobject]@{{ Opened = $false; Path = $path; Error = 'missing' }} | ConvertTo-Json -Compress
  exit
}}
try {{
  Start-Process -FilePath $path | Out-Null
  [pscustomobject]@{{ Opened = $true; Path = $path; Error = $null }} | ConvertTo-Json -Compress
}} catch {{
  [pscustomobject]@{{ Opened = $false; Path = $path; Error = $_.Exception.Message }} | ConvertTo-Json -Compress
}}
""",
        timeout=15.0,
        risk=LOW,
    )
    data = result.data if isinstance(result.data, dict) else {}
    opened = bool(data.get("Opened"))
    result.extras["opened"] = opened
    result.extras["path"] = str(path)
    result.success = opened
    result.summary = "Opened." if opened else (str(data.get("Error") or "Could not open it."))
    return result


def _open_posix_path(path: Path) -> ToolResult:
    opener = "xdg-open"
    code, _, err = run_argv([opener, str(path)], timeout=10)
    if code == 127:
        code, _, err = run_argv(["open", str(path)], timeout=10)
    opened = code == 0
    return ToolResult(
        name="open_path",
        risk=LOW,
        executed=True,
        available=True,
        success=opened,
        data={"Opened": opened, "Path": str(path)},
        summary="Opened." if opened else (err or "Could not open it."),
        extras={"opened": opened, "path": str(path)},
    )
