.. _pylock-file:


``pylock.toml`` file
====================

A ``pylock.toml`` file in your charm's root directory specifies the exact
versions and artifact hashes of your charm's dependencies, in the
tool-agnostic format defined by `PEP 751`_.

.. seealso::

    `PEP 751 – A file format to record Python dependencies for installation
    reproducibility <https://peps.python.org/pep-0751/>`_

This file is required if your charm uses the :ref:`craft_parts_pylock_plugin`.

Unlike :ref:`uv.lock <uv-lock-file>`, ``pylock.toml`` isn't tied to a single
tool. You can generate it with whichever locker your project already uses, for
example:

.. code-block:: bash

    uv export --format pylock.toml -o pylock.toml
    # or
    pdm lock --format pylock
    # or
    pip lock <your-requirements> -o pylock.toml

The file name must be ``pylock.toml`` or ``pylock.<name>.toml``; pip uses the
name to recognize the lock format.

Add this file to version control, so that your charm can be built after a
checkout by running ``charmcraft pack``. You shouldn't manually edit this file;
regenerate it with your locking tool when dependencies change.


.. _PEP 751: https://peps.python.org/pep-0751/
