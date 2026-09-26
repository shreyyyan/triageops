"""Reproducer for INC-2026-1045.

Real-world case: humanize 4.3.0's metric() crashes on zero input.
Upstream issue: https://github.com/python-humanize/humanize/issues/57
(Fixed upstream in 4.4.0 via PR #47.)

The 4.3.0 package is vendored verbatim under triage/realworld/humanize/.
Its __init__.py needs installed package metadata, so this script loads the
vendored humanize.number module directly (it only depends on .i18n).

Run from the repo root:
    python triage/realworld/repro_metric_zero.py
"""
import importlib.util
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent / "humanize"


def load(mod_name, path):
    spec = importlib.util.spec_from_file_location(mod_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


# Stub package so the vendored module's relative imports resolve.
pkg = importlib.util.module_from_spec(
    importlib.util.spec_from_loader("humanize_vendored", loader=None, is_package=True)
)
pkg.__path__ = [str(PKG)]
sys.modules["humanize_vendored"] = pkg

load("humanize_vendored.i18n", PKG / "i18n.py")
number = load("humanize_vendored.number", PKG / "number.py")

print("vendored module:", number.__file__)
print(number.metric(0))
