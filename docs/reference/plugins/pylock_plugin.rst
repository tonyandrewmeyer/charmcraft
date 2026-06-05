.. _craft_parts_pylock_plugin:

pylock plugin
=============

    See also: :ref:`howto-migrate-to-pylock`

The pylock plugin is designed for Python charms written with the
`Operator framework`_ that ship a `PEP 751`_ ``pylock.toml`` lock file.

Unlike the :ref:`uv <craft_parts_uv_plugin>` and
:ref:`poetry <craft_parts_poetry_plugin>` plugins, the pylock plugin doesn't
require the tool that produced the lock file to be present in the build
environment. A ``pylock.toml`` produced by uv, PDM, pip-tools or
``pip lock`` is installed with pip itself, which makes the plugin
tool-agnostic.

.. admonition:: Experimental
    :class: important

    pip's support for installing from ``pylock.toml`` is experimental and was
    added in pip 26.1. The plugin upgrades pip in the build venv to a new
    enough version before installing, but the pip command line for lock files
    may still change between releases.

Keywords
--------

In addition to the :ref:`common part keywords <reference-part-properties>`, the
pylock plugin provides the following plugin-specific keywords.

pylock-file
~~~~~~~~~~~

**Type**: string
**Default**: ``pylock.toml``

The `PEP 751`_ lock file to install from, relative to the part's source. The
name must be ``pylock.toml`` or ``pylock.<name>.toml``; pip uses the file name
to recognize the lock format, so any other name is rejected.

pylock-keep-bins
~~~~~~~~~~~~~~~~

**Type**: boolean
**Default**: False

Whether to keep Python scripts in the virtual environment's :file:`bin`
directory.

How it works
------------

During the build step, the plugin performs the following actions:

#. It creates a virtual environment in the
   :ref:`${CRAFT_PART_INSTALL}/venv <craft_parts_step_execution_environment>`
   directory.
#. It upgrades pip in that environment to a version that can install from a
   ``pylock.toml`` file.
#. It runs :command:`pip install --requirement=pylock.toml` to install the
   exact, hash-pinned packages recorded in the lock file, then runs
   :command:`pip check` to confirm the environment is consistent.
#. It copies any existing :file:`src` and :file:`lib` directories from your
   charm project into the final charm.

Because a ``pylock.toml`` records exact versions and artifact hashes, the
plugin doesn't expose extras or dependency-group selection: lock the desired
set of packages when the lock file is generated.

Example
-------

The following project file can be used with a project that has a
``pylock.toml`` to craft a charm with Ubuntu 26.04 LTS as its base:

.. literalinclude:: pylock-charmcraft.yaml
    :language: yaml


.. _PEP 751: https://peps.python.org/pep-0751/
