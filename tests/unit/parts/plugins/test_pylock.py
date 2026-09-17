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
"""Unit tests for the Charmcraft-specific pylock plugin."""

import pathlib
import typing

import craft_parts
import pytest
import pytest_check

from charmcraft.parts import plugins


def test_get_build_packages(pylock_plugin: plugins.PylockPlugin):
    assert "python3-pip" in pylock_plugin.get_build_packages()


def test_get_build_environment_keeps_pip_and_binaries(
    pylock_plugin: plugins.PylockPlugin,
):
    env = pylock_plugin.get_build_environment()

    # The venv must keep pip (no --without-pip) so it can read pylock.toml,
    # and PIP_NO_BINARY must not be set or recorded wheel hashes would fail.
    pytest_check.not_equal(env.get("PARTS_PYTHON_VENV_ARGS"), "--without-pip")
    pytest_check.is_not_in("PIP_NO_BINARY", env)


def test_get_venv_directory(
    pylock_plugin: plugins.PylockPlugin, install_path: pathlib.Path
):
    assert pylock_plugin._get_venv_directory() == install_path / "venv"


@pytest.mark.parametrize("source_subdir", [None, "subdir"])
def test_get_package_install_commands(
    tmp_path: pathlib.Path,
    install_path: pathlib.Path,
    source_subdir: str | None,
):
    project_dirs = craft_parts.ProjectDirs(work_dir=tmp_path)
    spec: dict[str, typing.Any] = {
        "plugin": "pylock",
        "source": str(tmp_path),
    }
    if source_subdir:
        spec["source-subdir"] = source_subdir
    plugin_properties = plugins.PylockPluginProperties.unmarshal(spec)
    part_spec = craft_parts.plugins.extract_part_properties(spec, plugin_name="pylock")
    part = craft_parts.Part(
        "foo", part_spec, project_dirs=project_dirs, plugin_properties=plugin_properties
    )
    project_info = craft_parts.ProjectInfo(
        application_name="test",
        project_dirs=project_dirs,
        cache_dir=tmp_path,
    )
    part_info = craft_parts.PartInfo(project_info=project_info, part=part)
    plugin = typing.cast(
        plugins.PylockPlugin,
        craft_parts.plugins.get_plugin(
            part=part, part_info=part_info, properties=plugin_properties
        ),
    )
    plugin._get_pip = lambda: "/python -m pip"  # ty: ignore[invalid-assignment]

    build_path = part_info.part_build_dir
    build_subdir = part_info.part_build_subdir
    if source_subdir:
        assert build_subdir != build_path
    else:
        assert build_subdir == build_path

    copy_src_cmd = (
        f"cp --archive --recursive --reflink=auto {build_subdir}/src {install_path}"
    )
    copy_lib_cmd = (
        f"cp --archive --recursive --reflink=auto {build_subdir}/lib {install_path}"
    )

    default_commands = plugin._get_package_install_commands()

    # pip is bootstrapped to a version that understands pylock.toml, then the
    # lock file is installed and the environment is checked.
    pytest_check.is_in("/python -m pip install --upgrade 'pip>=26.1'", default_commands)
    pytest_check.is_in(
        "/python -m pip install --requirement=pylock.toml", default_commands
    )
    pytest_check.is_in("/python -m pip check", default_commands)
    pytest_check.is_not_in(copy_src_cmd, default_commands)
    pytest_check.is_not_in(copy_lib_cmd, default_commands)

    if source_subdir:
        # Creating src/lib in parent build_path should not trigger copy
        (build_path / "src").mkdir(parents=True)
        (build_path / "lib" / "charm").mkdir(parents=True)
        wrong_copy_src_cmd = (
            f"cp --archive --recursive --reflink=auto {build_path}/src {install_path}"
        )
        wrong_copy_lib_cmd = (
            f"cp --archive --recursive --reflink=auto {build_path}/lib {install_path}"
        )
        commands_with_parent_dirs = plugin._get_package_install_commands()
        pytest_check.is_not_in(wrong_copy_src_cmd, commands_with_parent_dirs)
        pytest_check.is_not_in(wrong_copy_lib_cmd, commands_with_parent_dirs)
        pytest_check.is_not_in(copy_src_cmd, commands_with_parent_dirs)
        pytest_check.is_not_in(copy_lib_cmd, commands_with_parent_dirs)

    (build_subdir / "src").mkdir(parents=True)

    pytest_check.equal(
        plugin._get_package_install_commands(), [*default_commands, copy_src_cmd]
    )

    (build_subdir / "lib" / "charm").mkdir(parents=True)

    pytest_check.equal(
        plugin._get_package_install_commands(),
        [*default_commands, copy_src_cmd, copy_lib_cmd],
    )

    (build_subdir / "src").rmdir()

    pytest_check.equal(
        plugin._get_package_install_commands(), [*default_commands, copy_lib_cmd]
    )


def test_install_commands_quote_pylock_file(pylock_plugin: plugins.PylockPlugin):
    spec = {
        "plugin": "pylock",
        "source": ".",
        "pylock-file": "pylock.dev.toml",
    }
    pylock_plugin._options = plugins.PylockPluginProperties.unmarshal(spec)
    pylock_plugin._get_pip = lambda: "pip"  # ty: ignore[invalid-assignment]

    assert "pip install --requirement=pylock.dev.toml" in (
        pylock_plugin._get_package_install_commands()
    )


@pytest.mark.parametrize(
    "pylock_file",
    ["pylock.toml", "pylock.dev.toml", "pylock.foo-bar.toml"],
)
def test_valid_pylock_file_names(pylock_file: str):
    spec = {"plugin": "pylock", "source": ".", "pylock-file": pylock_file}

    assert plugins.PylockPluginProperties.unmarshal(spec).pylock_file == pylock_file


@pytest.mark.parametrize(
    "pylock_file",
    ["requirements.txt", "lock.toml", "mylock.toml", "pylock.json", "pylock"],
)
def test_invalid_pylock_file_names(pylock_file: str):
    spec = {"plugin": "pylock", "source": ".", "pylock-file": pylock_file}

    with pytest.raises(ValueError, match="not a valid PEP 751 lock file name"):
        plugins.PylockPluginProperties.unmarshal(spec)


def test_get_rm_command(
    pylock_plugin: plugins.PylockPlugin, install_path: pathlib.Path
):
    assert (
        f"rm -rf {install_path / 'venv/bin'}/!(activate)"
        in pylock_plugin.get_build_commands()
    )


def test_no_get_rm_command(
    pylock_plugin: plugins.PylockPlugin, install_path: pathlib.Path
):
    spec = {
        "plugin": "pylock",
        "source": ".",
        "pylock-keep-bins": True,
    }
    pylock_plugin._options = plugins.PylockPluginProperties.unmarshal(spec)
    assert (
        f"rm -rf {install_path / 'venv/bin'}/!(activate)"
        not in pylock_plugin.get_build_commands()
    )
