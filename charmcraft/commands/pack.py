# Copyright 2020-2021 Canonical Ltd.
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

"""Infrastructure for the 'pack' command."""

import os
import pathlib
import zipfile
from argparse import Namespace
from typing import List

from craft_cli import emit

from charmcraft import env, parts
from charmcraft.cmdbase import BaseCommand, CommandError
from charmcraft.commands import build
from charmcraft.manifest import create_manifest
from charmcraft.parts import Step
from charmcraft.utils import SingleOptionEnsurer, load_yaml, useful_filepath

# the minimum set of files in a bundle
MANDATORY_FILES = ["bundle.yaml", "README.md"]


def build_zip(zippath, prime_dir):
    """Build the final file."""
    zipfh = zipfile.ZipFile(zippath, "w", zipfile.ZIP_DEFLATED)
    for dirpath, dirnames, filenames in os.walk(prime_dir, followlinks=True):
        dirpath = pathlib.Path(dirpath)
        for filename in filenames:
            filepath = dirpath / filename
            zipfh.write(str(filepath), str(filepath.relative_to(prime_dir)))

    zipfh.close()


_overview = """
Build and pack a charm operator package or a bundle.

You can `juju deploy` the resulting `.charm` or bundle's `.zip`
file directly, or upload it to Charmhub with `charmcraft upload`.

For the charm you must be inside a charm directory with a valid
`metadata.yaml`, `requirements.txt` including the `ops` package
for the Python operator framework, and an operator entrypoint,
usually `src/charm.py`.  See `charmcraft init` to create a
template charm directory structure.

For the bundle you must already have a `bundle.yaml` (can be
generated by Juju) and a README.md file.
"""


class PackCommand(BaseCommand):
    """Build the bundle or the charm.

    If charmcraft.yaml missing or its 'type' key indicates a charm,
    use the "build" infrastructure to create the charm.

    Otherwise pack the bundle.
    """

    name = "pack"
    help_msg = "Build the charm or bundle"
    overview = _overview
    needs_config = False  # optional until we fully support charms here

    def fill_parser(self, parser):
        """Add own parameters to the general parser."""
        parser.add_argument(
            "--debug",
            action="store_true",
            help="Launch shell in build environment upon failure",
        )
        parser.add_argument(
            "--destructive-mode",
            action="store_true",
            help=(
                "Pack charm using current host which may result in breaking "
                "changes to system configuration"
            ),
        )
        parser.add_argument(
            "-e",
            "--entrypoint",
            type=SingleOptionEnsurer(useful_filepath),
            help=("The executable which is the operator entry point; defaults to 'src/charm.py'"),
        )
        parser.add_argument(
            "-r",
            "--requirement",
            action="append",
            type=useful_filepath,
            help=(
                "File(s) listing needed PyPI dependencies (can be used multiple "
                "times); defaults to 'requirements.txt'"
            ),
        )
        parser.add_argument(
            "--shell",
            action="store_true",
            help="Launch shell in build environment in lieu of packing",
        )
        parser.add_argument(
            "--shell-after",
            action="store_true",
            help="Launch shell in build environment after packing",
        )
        parser.add_argument(
            "--bases-index",
            action="append",
            type=int,
            help="Index of 'bases' configuration to build (can be used multiple "
            "times); defaults to all",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force packing even after finding lint errors",
        )

    def run(self, parsed_args):
        """Run the command."""
        # decide if this will work on a charm or a bundle
        if self.config.type == "charm" or not self.config.project.config_provided:
            self._pack_charm(parsed_args)
        elif self.config.type == "bundle":
            if parsed_args.entrypoint is not None:
                raise CommandError("The -e/--entry option is valid only when packing a charm")
            if parsed_args.requirement is not None:
                raise CommandError(
                    "The -r/--requirement option is valid only when packing a charm"
                )
            self._pack_bundle(parsed_args)
        else:
            raise CommandError("Unknown type {!r} in charmcraft.yaml".format(self.config.type))

    def _pack_charm(self, parsed_args) -> List[pathlib.Path]:
        """Pack a charm."""
        emit.progress("Packing the charm.")
        # adapt arguments to use the build infrastructure
        build_args = Namespace(
            **{
                "debug": parsed_args.debug,
                "destructive_mode": parsed_args.destructive_mode,
                "from": self.config.project.dirpath,
                "entrypoint": parsed_args.entrypoint,
                "requirement": parsed_args.requirement,
                "shell": parsed_args.shell,
                "shell_after": parsed_args.shell_after,
                "bases_indices": parsed_args.bases_index,
                "force": parsed_args.force,
            }
        )

        # mimic the "build" command
        validator = build.Validator(self.config)
        args = validator.process(build_args)
        emit.trace(f"Working arguments: {args}")
        builder = build.Builder(args, self.config)
        charms = builder.run(parsed_args.bases_index, destructive_mode=build_args.destructive_mode)
        emit.message("Charms packed:")
        for charm in charms:
            emit.message(f"    {charm}")

    def _pack_bundle(self, parsed_args) -> List[pathlib.Path]:
        """Pack a bundle."""
        emit.progress("Packing the bundle.")
        if parsed_args.shell:
            build.launch_shell()
            return []

        project = self.config.project

        if self.config.parts:
            config_parts = self.config.parts.copy()
        else:
            # "parts" not declared, create an implicit "bundle" part
            config_parts = {"bundle": {"plugin": "bundle"}}

        # a part named "bundle" using plugin "bundle" is special and has
        # predefined values set automatically.
        bundle_part = config_parts.get("bundle")
        if bundle_part and bundle_part.get("plugin") == "bundle":
            special_bundle_part = bundle_part
        else:
            special_bundle_part = None

        # get the config files
        bundle_filepath = project.dirpath / "bundle.yaml"
        bundle_config = load_yaml(bundle_filepath)
        if bundle_config is None:
            raise CommandError(
                "Missing or invalid main bundle file: {!r}.".format(str(bundle_filepath))
            )
        bundle_name = bundle_config.get("name")
        if not bundle_name:
            raise CommandError(
                "Invalid bundle config; missing a 'name' field indicating the bundle's name in "
                "file {!r}.".format(str(bundle_filepath))
            )

        if special_bundle_part:
            # set prime filters
            for fname in MANDATORY_FILES:
                fpath = project.dirpath / fname
                if not fpath.exists():
                    raise CommandError("Missing mandatory file: {!r}.".format(str(fpath)))
            prime = special_bundle_part.setdefault("prime", [])
            prime.extend(MANDATORY_FILES)

            # set source if empty or not declared in charm part
            if not special_bundle_part.get("source"):
                special_bundle_part["source"] = str(project.dirpath)

        if env.is_charmcraft_running_in_managed_mode():
            work_dir = env.get_managed_environment_home_path()
        else:
            work_dir = project.dirpath / build.BUILD_DIRNAME

        # run the parts lifecycle
        emit.trace(f"Parts definition: {config_parts}")
        lifecycle = parts.PartsLifecycle(
            config_parts,
            work_dir=work_dir,
            project_dir=project.dirpath,
            ignore_local_sources=[bundle_name + ".zip"],
        )
        try:
            lifecycle.run(Step.PRIME)
        except (RuntimeError, CommandError) as error:
            if parsed_args.debug:
                emit.trace(f"Error when running PRIME step: {error}")
                build.launch_shell()
            raise

        # pack everything
        create_manifest(lifecycle.prime_dir, project.started_at, None, [])
        zipname = project.dirpath / (bundle_name + ".zip")
        build_zip(zipname, lifecycle.prime_dir)

        emit.message(f"Created {str(zipname)!r}.")

        if parsed_args.shell_after:
            build.launch_shell()

        return [zipname]
