#!/usr/bin/env python3
"""Backwards-compatible entry point.

The original single-file script now lives in the :mod:`opencode2others`
package. This shim keeps the old invocation working by forwarding to the
``pi`` target.

Prefer::

    python -m opencode2others --target pi

or, once installed::

    opencode2others --target pi
"""

from __future__ import annotations

import sys

from opencode2others.cli import main


def _forward(argv: list[str]) -> list[str]:
    argv = list(argv)
    if "--target" not in argv and "-t" not in argv:
        argv = ["--target", "pi", *argv]
    return argv


if __name__ == "__main__":
    raise SystemExit(main(_forward(sys.argv[1:])))
