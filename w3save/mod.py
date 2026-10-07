"""Generate a temporary mod from the user's own verified Next-Gen script.

Only original additions are distributed. No complete game script is embedded.
"""
from hashlib import sha256
from importlib.resources import files

SUPPORTED_SCRIPT_SHA256 = "2aa887f7767db04e26978d91d62799181305ed421cde0e293e33d73d9f8403ff"
MOD_ROOT = "modCheckpointRemasterTo404/content/scripts"


def _snippet(name: str) -> str:
    return files("w3save").joinpath("snippets", name).read_text(encoding="utf-8")


def generate_mod(source_script: bytes) -> dict[str, bytes]:
    """Return relative paths and bytes; never read/write the user's game directory.

    Refuse altered, unknown or already patched input. The exact fingerprint pins
    insertion positions to the observed 4.04 script, with additional anchor checks.
    """
    if sha256(source_script).hexdigest() != SUPPORTED_SCRIPT_SHA256:
        raise ValueError("Game script SHA-256 is not the supported unmodified Next-Gen 4.04 file")
    if not source_script.startswith(b"\xff\xfe"):
        raise ValueError("Expected the verified UTF-16LE game script encoding")
    try:
        source = source_script[2:].decode("utf-16-le")
    except UnicodeError as exc:
        raise ValueError("Invalid UTF-16LE game script encoding") from exc
    if "MigrateInspectedRemasterCheckpoint" in source:
        raise ValueError("Migration is already present; duplicate insertion refused")
    lines = source.splitlines(keepends=True)
    if (
        len(lines) <= 4525
        or lines[75] != "\t\tif(!super.Init(ownr,cStats, isFromLoad, diff))\r\n"
        or lines[76] != "\t\t\treturn false;\r\n"
        or lines[4525] != "}\r\n"
        or "\n" in source.replace("\r\n", "")
    ):
        raise ValueError("Supported game script structure/anchors do not match")
    hook = _snippet("migration_hook.ws").replace("\n", "\r\n")
    method = _snippet("migration_method.ws").replace("\n", "\r\n") + "\r\n"
    generated = "".join(lines[:77]) + hook + "".join(lines[77:4525]) + method + "".join(lines[4525:])
    return {
        f"{MOD_ROOT}/game/gameplay/ability/PlayerAbilityManager.ws": b"\xff\xfe" + generated.encode("utf-16-le"),
        f"{MOD_ROOT}/checkpointDiagnostics.ws": _snippet("checkpointDiagnostics.ws").encode("utf-8"),
    }
