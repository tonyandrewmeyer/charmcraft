# Copyright 2023,2025 Canonical Ltd.
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
import sys
from textwrap import dedent
from typing import Any

import pytest
from overrides import override

from charmcraft import extensions
from tests.extensions.test_extensions import FakeExtension


class TestExtension(FakeExtension):
    """A fake test Extension that has complete behavior"""

    name = "test-extension"
    bases = [("ubuntu", "22.04")]

    @override
    def get_root_snippet(self) -> dict[str, Any]:
        """Return the root snippet to apply."""
        return {"terms": ["https://example.com/test"]}


@pytest.fixture
def fake_extensions(stub_extensions):
    extensions.register(TestExtension.name, TestExtension)


@pytest.mark.parametrize(
    ("charmcraft_yaml", "expected"),
    [
        pytest.param(
            dedent(
                f"""
                name: test-charm-name
                type: charm
                summary: test-summary
                description: test-description
                extensions: [{TestExtension.name}]
                base: ubuntu@22.04
                platforms:
                  amd64:
                parts:
                  my-part:
                    plugin: nil
                """
            ),
            dedent(
                """\
                name: test-charm-name
                summary: test-summary
                description: test-description
                base: ubuntu@22.04
                platforms:
                  amd64: null
                parts:
                  my-part:
                    plugin: nil
                type: charm
                terms:
                - https://example.com/test
                """
            ),
            id="platforms",
        ),
        pytest.param(
            dedent(
                f"""
                name: test-charm-name
                type: charm
                summary: test-summary
                description: test-description
                extensions: [{TestExtension.name}]
                bases:
                  - name: ubuntu
                    channel: "22.04"
                """
            ),
            dedent(
                """\
                name: test-charm-name
                summary: test-summary
                description: test-description
                parts:
                  charm:
                    plugin: charm
                    source: .
                type: charm
                terms:
                - https://example.com/test
                bases:
                - build-on:
                  - name: ubuntu
                    channel: '22.04'
                  run-on:
                  - name: ubuntu
                    channel: '22.04'
                """
            ),
            id="bases",
        ),
    ],
)
def test_expand_extensions_simple(
    monkeypatch, new_path, app, fake_extensions, emitter, charmcraft_yaml, expected
):
    """Expand a charmcraft.yaml with a single extension."""
    (new_path / "charmcraft.yaml").write_text(charmcraft_yaml)
    monkeypatch.setattr(sys, "argv", ["charmcraft", "expand-extensions"])

    app.run()

    emitter.assert_message(expected)
