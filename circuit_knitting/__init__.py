# This code is a Qiskit project.

# (C) Copyright IBM 2022.

# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Main Circuit Knitting Toolbox public functionality."""

from __future__ import annotations
from importlib.metadata import version, PackageNotFoundError


try:
    __version__ = version("circuit-knitting-toolbox")
except PackageNotFoundError:  # pragma: no cover
    # Package is not installed
    pass

__all__: list[str] = []
