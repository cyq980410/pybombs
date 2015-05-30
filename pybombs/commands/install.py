#
# Copyright 2015 Free Software Foundation, Inc.
#
# This file is part of GNU Radio
#
# GNU Radio is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
#
# GNU Radio is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GNU Radio; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.
#
""" PyBOMBS command: install """

import copy
from pybombs.commands import PyBombsCmd
from pybombs import simple_tree
from pybombs import recipe
from pybombs import package_manager

class PyBombsInstall(PyBombsCmd):
    """ Install or update a package """
    cmds = {
        'install': 'Install listed packages',
        'update': 'Update listed packages',
    }

    @staticmethod
    def setup_subparser(parser, cmd=None):
        """
        Set up a subparser for 'install'
        """
        parser.add_argument(
                'packages',
                help="List of packages to install",
                action='append',
                default=[],
                nargs='*'
        )
        parser.add_argument(
                '--print-tree',
                help="Print dependency tree",
                action='store_true',
        )
        if cmd == 'install':
            parser.add_argument(
                    '-u', '--update',
                    help="If packages are already installed, update them instead.",
                    action='store_true',
            )

    def __init__(self, cmd, args):
        PyBombsCmd.__init__(self,
                cmd, args,
                load_recipes=True,
                require_prefix=True,
                require_inventory=False,
        )
        self.args.packages = args.packages[0] # wat?
        if len(self.args.packages) == 0 and not args.all:
            self.log.error("No packages specified.")
            exit(1)
        self.update_if_exists = (cmd == 'update' or self.args.update)
        self.fail_if_not_exists = (cmd == 'update')

    def run(self):
        """ Go, go, go! """
        install_tree = simple_tree.SimpleTree()
        pm = package_manager.PackageManager()
        packages_to_update = []
        ### Step 1: Make a list of packages to install
        # Loop through all packages to install
        for pkg in self.args.packages:
            print 'adding ', pkg
            # Check is a valid package:
            if not pm.exists(pkg):
                self.log.error("Package does not exist: {}".format(pkg))
                exit(1)
            # Check if we already covered this package
            if pkg in install_tree.get_nodes():
                continue
            # Check if package is already installed:
            if not pm.installed(pkg):
                if self.fail_if_not_exists:
                    self.log.error("Package {} is not installed. Aborting.".format(pkg))
                    exit(1)
                install_tree.insert_at(pkg)
                self._add_deps_recursive(install_tree, pkg)
            elif self.update_if_exists:
                packages_to_update.append(pkg)
                install_tree.insert_at(pkg)
                self._add_deps_recursive(install_tree, pkg)
            # If it's already installed, but we didn't select update, just
            # do nothing.
        self.log.debug("Install tree:")
        if self.log.getEffectiveLevel() <= 20 or self.args.print_tree:
            install_tree.pretty_print()
        ### Step 2: Recursively install, starting at the leaf nodes
        while not install_tree.empty():
            pkg = install_tree.pop_leaf_node()
            if not pm.exists(pkg):
                self.log.error("Package {} can't be found!".format(pkg))
                exit(1)
            if pkg in packages_to_update:
                self.log.debug("Updating package: {}".format(pkg))
                pm.update(pkg)
            else:
                self.log.debug("Installing package: {}".format(pkg))
                pm.install(pkg)

    def _add_deps_recursive(self, install_tree, pkg):
        """
        Recursively add dependencies to the install tree.
        """
        deps = recipe.Recipe(self.recipe_manager.get_recipe_filename(pkg)).deps
        deps_to_install = [dep for dep in deps if not dep in install_tree.get_nodes()]
        if len(deps_to_install) == 0:
            return
        install_tree.insert_at(deps_to_install, pkg)
        for dep in deps_to_install:
            if isinstance(dep, list):
                # I honestly have no clue why this happens, yet sometimes
                # it does.
                continue
            self._add_deps_recursive(install_tree, dep)

