"""Put the repo root on sys.path so tests run without installing the package."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def run_module(globs):
    """Run every test_* function in a module's globals; print PASS/FAIL."""
    tests = sorted(n for n, v in globs.items() if n.startswith("test_") and callable(v))
    failed = 0
    for name in tests:
        try:
            globs[name]()
            print(f"  PASS {name}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  FAIL {name}: {e!r}")
    print(f"{'-'*40}\n{len(tests) - failed}/{len(tests)} passed in {globs.get('__name__')}")
    return failed
