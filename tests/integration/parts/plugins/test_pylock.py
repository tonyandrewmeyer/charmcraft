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

import pathlib
import subprocess
import sys

import craft_application
import pytest

pytestmark = [
    pytest.mark.skipif(sys.platform != "linux", reason="craft-parts is linux-only")
]


@pytest.fixture(autouse=True)
def add_part(
    service_factory: craft_application.ServiceFactory, project_path: pathlib.Path
):
    service_factory.get("project").get().parts = {
        "my-charm": {
            "plugin": "pylock",
            "source": str(project_path),
            "source-type": "local",
        }
    }


@pytest.fixture
def pylock_project(project_path: pathlib.Path) -> None:
    # ``pip lock`` (the PEP 751 lock file generator) is itself experimental and
    # was added in pip 25.1; skip if this runner's pip can't produce one.
    result = subprocess.run(
        [sys.executable, "-m", "pip", "lock", "ops", "--output", "pylock.toml"],
        cwd=project_path,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.skip(f"could not generate a pylock.toml with this pip:\n{result.stderr}")

    source_dir = project_path / "src"
    source_dir.mkdir()
    (source_dir / "charm.py").write_text("# Charm file")


@pytest.mark.slow
@pytest.mark.usefixtures("pylock_project")
def test_pylock_plugin(
    service_factory: craft_application.ServiceFactory, tmp_path: pathlib.Path
):
    install_path = tmp_path / "parts" / "my-charm" / "install"
    stage_path = tmp_path / "stage"

    service_factory.lifecycle.run("stage")

    # Check that the part install directory looks correct.
    assert (install_path / "src" / "charm.py").read_text() == "# Charm file"
    assert (install_path / "venv" / "lib").is_dir()
    # The locked dependency was installed into the venv.
    assert next((install_path / "venv" / "lib").glob("python*/site-packages/ops"))

    # Check that the stage directory looks correct.
    assert (stage_path / "src" / "charm.py").read_text() == "# Charm file"
    assert (stage_path / "venv" / "lib").is_dir()
    assert not (stage_path / "venv" / "lib64").is_symlink()
