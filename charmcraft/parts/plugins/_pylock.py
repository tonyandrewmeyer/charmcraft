# Copyright 2026 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# For further info, check https://github.com/canonical/charmcraft
"""Charmcraft-specific pylock plugin.

Builds a charm's virtualenv from a PEP 751 ``pylock.toml`` file. Unlike the
``uv`` and ``poetry`` plugins, this does not require the lock file's producing
tool to be present in the build environment: a ``pylock.toml`` produced by uv,
pdm, pip-tools or ``pip lock`` is installed with pip itself.

pip's ``-r pylock.toml`` support is experimental and landed in pip 26.1
(https://github.com/pypa/pip/pull/13876), so the plugin bootstraps a new enough
pip into the venv before installing.
"""

import re
import shlex
from pathlib import Path
from typing import Literal

import pydantic
from craft_parts.plugins.base import BasePythonPlugin
from craft_parts.plugins.properties import PluginProperties
from overrides import override

from charmcraft import utils

# PEP 751: a lock file must be named ``pylock.toml`` or ``pylock.<name>.toml``.
# pip detects the pylock format from this filename, so anything else is parsed
# as a requirements.txt and fails.
_PYLOCK_FILENAME = re.compile(r"^pylock\.(.+\.)?toml$")

# pip version that first understands ``pip install -r pylock.toml``.
_MIN_PIP = "26.1"


class PylockPluginProperties(PluginProperties, frozen=True):
    """The part properties used by the pylock plugin."""

    plugin: Literal["pylock"] = "pylock"

    pylock_file: str = "pylock.toml"
    """The PEP 751 lock file to install from, relative to the source tree."""

    pylock_keep_bins: bool = False
    """Keep the virtual environment's 'bin' directory."""

    source: str  # pyright: ignore[reportGeneralTypeIssues]

    @pydantic.field_validator("pylock_file", mode="after")
    @classmethod
    def _validate_pylock_file(cls, pylock_file: str) -> str:
        if not _PYLOCK_FILENAME.match(Path(pylock_file).name):
            raise ValueError(
                f"{pylock_file!r} is not a valid PEP 751 lock file name: "
                "the file must be named 'pylock.toml' or 'pylock.<name>.toml'."
            )
        return pylock_file


class PylockPlugin(BasePythonPlugin):
    """Charmcraft plugin to build a charm from a PEP 751 pylock.toml file."""

    properties_class = PylockPluginProperties
    _options: PylockPluginProperties  # type: ignore[reportIncompatibleVariableOverride]

    @override
    def get_build_packages(self) -> set[str]:
        # python3-pip provides the bootstrap pip; it is upgraded to >=26.1
        # in the venv before the lock file is installed.
        return {*super().get_build_packages(), "python3-pip"}

    @override
    def get_build_environment(self) -> dict[str, str]:
        # NB: unlike the python/poetry/uv plugins this does *not* create the
        # venv with --without-pip (it needs pip>=26.1 inside the venv to read
        # pylock.toml) and does *not* set PIP_NO_BINARY: a pylock.toml pins
        # specific artifacts with hashes, so forcing source builds would make
        # the recorded wheel hashes fail to match.
        return super().get_build_environment()

    @override
    def _get_venv_directory(self) -> Path:
        return self._part_info.part_install_dir / "venv"

    @override
    def _get_pip(self) -> str:
        """Get the pip command to use, run from the venv's own interpreter."""
        return f'"{self._get_venv_directory()}/bin/python" -m pip'

    @override
    def _get_package_install_commands(self) -> list[str]:
        """Get the package installation commands.

        Charms are not installable Python packages, so this installs only the
        locked dependencies and then copies the charm source and charmlibs into
        the install directory.
        """
        pip = self._get_pip()
        pylock_file = shlex.quote(self._options.pylock_file)
        return [
            # pylock support is experimental and only exists in pip>=26.1, which
            # is newer than the pip shipped in any current build base.
            f"{pip} install --upgrade 'pip>={_MIN_PIP}'",
            f"{pip} install --requirement={pylock_file}",
            # Confirm the resulting environment is internally consistent.
            f"{pip} check",
            *utils.get_charm_copy_commands(
                self._part_info.part_build_dir, self._part_info.part_install_dir
            ),
        ]

    @override
    def _should_remove_symlinks(self) -> bool:
        return True

    @override
    def _get_rewrite_shebangs_commands(self) -> list[str]:
        """Charms don't need their shebangs rewritten."""
        return []

    @override
    def get_build_commands(self) -> list[str]:
        return [
            *super().get_build_commands(),
            *utils.get_venv_cleanup_commands(
                self._get_venv_directory(), keep_bins=self._options.pylock_keep_bins
            ),
        ]
