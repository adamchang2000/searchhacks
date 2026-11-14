"""Check that every type in lib/types has identical Python and TypeScript definitions.

For each <type>/ directory: import the Python module, load the TS module with tsx, and
compare every exported const object (members and values) with the Python enum or dict of the
same name. Exits non-zero on any mismatch.

Run from the repo root:  python3 lib/types/check_sync.py
"""

from __future__ import annotations

import enum
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TSX = HERE.parent.parent / "node_modules" / ".bin" / "tsx"


def load_py(path: Path) -> dict[str, dict[str, object]]:
    spec = importlib.util.spec_from_file_location(path.parent.parent.name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out: dict[str, dict[str, object]] = {}
    for name in getattr(mod, "__all__", []):
        obj = getattr(mod, name)
        if isinstance(obj, type) and issubclass(obj, enum.Enum):
            out[name] = {m.name: m.value for m in obj}
        elif isinstance(obj, dict):
            # Dicts keyed by enum members compare by member value, as TS keys them.
            out[name] = {str(k.value if isinstance(k, enum.Enum) else k): v for k, v in obj.items()}
    return out


def load_ts(path: Path) -> dict[str, dict[str, object]]:
    script = (
        f"import({json.dumps(path.as_uri())}).then((m) => {{"
        "const out = {};"
        "for (const [k, v] of Object.entries(m)) if (v && typeof v === 'object' && !Array.isArray(v)) out[k] = v;"
        "console.log(JSON.stringify(out));"
        "});"
    )
    res = subprocess.run([str(TSX), "--eval", script], capture_output=True, text=True, check=True)
    return {name: {str(k): v for k, v in obj.items()} for name, obj in json.loads(res.stdout).items()}


def main() -> int:
    failed = False
    for type_dir in sorted(p for p in HERE.iterdir() if (p / "python").is_dir()):
        py = load_py(type_dir / "python" / "__init__.py")
        ts = load_ts(type_dir / "typescript" / "index.ts")
        problems: list[str] = []
        for name in sorted(set(py) ^ set(ts)):
            problems.append(f"{name}: only in {'python' if name in py else 'typescript'}")
        for name in sorted(set(py) & set(ts)):
            a, b = py[name], ts[name]
            for key in sorted(set(a) | set(b)):
                if a.get(key, "<missing>") != b.get(key, "<missing>"):
                    problems.append(f"{name}.{key}: python={a.get(key, '<missing>')!r} ts={b.get(key, '<missing>')!r}")
        counts = ", ".join(f"{n}={len(py[n])}" for n in sorted(set(py) & set(ts)))
        if problems:
            failed = True
            print(f"FAIL {type_dir.name} ({counts})")
            for p in problems:
                print(f"  {p}")
        else:
            print(f"ok   {type_dir.name} ({counts})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
