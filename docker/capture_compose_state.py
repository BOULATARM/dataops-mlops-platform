"""Capture horodatée de Compose, y compris les échecs (sans masquer leur code)."""

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def capture(compose_file, output):
    command = ["docker", "compose", "-f", compose_file, "ps", "--all", "--format", "json"]
    started = datetime.now(UTC).isoformat()
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        code, stdout, stderr = result.returncode, result.stdout, result.stderr
    except (OSError, subprocess.TimeoutExpired) as exc:
        code, stdout, stderr = 1, "", str(exc)
    evidence = {
        "timestamp_utc": started,
        "command": command,
        "returncode": code,
        "stdout": stdout,
        "stderr": stderr,
    }
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    return code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compose-file", default="docker/docker-compose.yml")
    parser.add_argument("--output", default="docs/evidence/compose-state.json")
    args = parser.parse_args()
    raise SystemExit(capture(args.compose_file, args.output))
