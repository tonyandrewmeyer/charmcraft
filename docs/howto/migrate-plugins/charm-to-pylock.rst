.. _howto-migrate-to-pylock:

.. meta::
    :description: How to migrate a charm from the Charm plugin to the pylock plugin in Charmcraft, using a PEP 751 pylock.toml lock file.

Migrate from the Charm plugin to the pylock plugin
==================================================

For charms that ship a `PEP 751`_ ``pylock.toml`` lock file, Charmcraft has a
:ref:`craft_parts_pylock_plugin`. This guide shows how to migrate from the
default Charm plugin to the pylock plugin.

The pylock plugin is tool-agnostic: it installs the lock file with pip, so the
tool that produced ``pylock.toml`` (uv, PDM, pip-tools, ...) doesn't need to be
present in the build environment. Like the other Python-family plugins, it
removes the need to maintain a hand-written ``requirements.txt``.

.. admonition:: Experimental
    :class: important

    pip's support for installing from ``pylock.toml`` is experimental and was
    added in pip 26.1. The plugin upgrades pip in the build venv before
    installing, but the behavior may change in future pip releases.

Update the project file
-----------------------

Update the project file to include the correct parts definition. If the charm
doesn't have an explicit ``parts`` section, create one as follows:

.. code-block:: yaml
    :caption: charmcraft.yaml

    parts:
      my-charm:  # This can be named anything you want
        plugin: pylock
        source: .

List the charm's dependencies
-----------------------------

List the charm's runtime dependencies wherever your locking tool reads them
from, typically the ``dependencies`` key of a :ref:`pyproject-toml-file`.

.. code-block:: toml
    :caption: pyproject.toml
    :emphasize-lines: 6-9

    [project]
    name = "my-charm"
    version = "0.0.1"
    requires-python = ">=3.10"

    # Dependencies of the charm code.
    dependencies = [
        "ops>=3,<4",
    ]

List charm library dependencies
-------------------------------

Charm libraries are distributed either as regular Python packages under the
`charmlibs <https://documentation.ubuntu.com/charmlibs>`_ namespace, or hosted
on Charmhub. Python packages should be listed in the charm's dependencies.

Like the other Python-family plugins, the pylock plugin doesn't install
transitive dependencies for Charmhub-hosted libraries. If any of these charm
libraries have ``PYDEPS``, add them to the charm's dependencies.

To find library dependencies, check each loaded library file for its
``PYDEPS`` by running the following command at the root of the charm project:

.. code-block:: bash

    find lib -name "*.py" -exec awk '/PYDEPS = \[/,/\]/' {} +

Add them to the ``dependencies`` key in ``pyproject.toml``.

Lock the dependencies
---------------------

Generate a :ref:`pylock-file` with whichever locking tool your project uses.
Make sure any extras or dependency groups you need are resolved into the lock
file at this point, since the plugin installs exactly what the lock file
records. For example:

.. code-block:: bash

    uv export --format pylock.toml -o pylock.toml

Add the resulting ``pylock.toml`` to version control, so that your charm can be
built after a checkout by running ``charmcraft pack``.

If your lock file uses the alternate ``pylock.<name>.toml`` form, point the
plugin at it:

.. code-block:: yaml
    :caption: charmcraft.yaml
    :emphasize-lines: 5

    parts:
      my-charm:
        plugin: pylock
        source: .
        pylock-file: pylock.production.toml

Include extra files
-------------------

The pylock plugin only includes the contents of the ``src`` and ``lib``
directories as well as the generated virtual environment. If other files such
as a charm's icon were previously included from the main directory, stage them
in a new part that uses the :ref:`craft_parts_dump_plugin`:

.. code-block:: yaml
    :caption: charmcraft.yaml
    :emphasize-lines: 5-10

    parts:
      my-charm:
        plugin: pylock
        source: .
      version-file:
        plugin: dump
        source: .
        stage:
          - charm_version
          - icon.svg


.. _PEP 751: https://peps.python.org/pep-0751/
