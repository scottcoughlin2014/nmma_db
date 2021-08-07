#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) Michael Coughlin (2021)
#
# This file is part of nmma_db.
#
# nmma is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# nmma is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with nmma.  If not, see <http://www.gnu.org/licenses/>.

"""Setup the nmma_db package
"""

# ignore all invalid names (pylint isn't good at looking at executables)
# pylint: disable=invalid-name

from __future__ import print_function

import os
import sys

from setuptools import setup, find_packages

import versioneer


def get_scripts(scripts_dir="bin"):
    """Get relative file paths for all files under the ``scripts_dir``"""
    scripts = []
    for (dirname, _, filenames) in os.walk(scripts_dir):
        scripts.extend([os.path.join(dirname, fn) for fn in filenames])
    return scripts


# from setup_utils import (CMDCLASS, get_setup_requires, get_scripts)

# -- dependencies -------------------------------------------------------------

# build dependencies
# setup_requires = get_setup_requires()

# package dependencies
install_requires = [
    "aiohttp",
    "aiohttp-middlewares",
    "aiohttp_swagger3",
    "arrow",
    "bcrypt",
    "bilby_pipe",
    "odmantic",
    "psycopg2-binary",
    "pymongo",
    "redis",
    "simplejson",
    "sqlalchemy",
    "uvloop",
]

# For documenation
extras_require = {
    'doc': [
        'matplotlib',
        'ipython',
        'sphinx',
        'numpydoc',
        'sphinx_rtd_theme',
        'sphinxcontrib_programoutput',
    ],
}

# test dependencies
tests_require = [
    "pytest>=3.1",
    "pytest-aiohttp",
    "freezegun",
    "sqlparse",
    "bs4",
]
if sys.version < "3":
    tests_require.append("mock")

# -- run setup ----------------------------------------------------------------

setup(
    # metadata
    name="nmma_db",
    provides=["nmma_db"],
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    description="A python package for setting up NMMA based fits",
    long_description=("nmma is a python package for setting up NMMA based fits"),
    author="Michael Coughlin",
    author_email="michael.coughlin@ligo.org",
    license="GPLv3",
    url="https://github.com/mcoughlin/nmma_db/",
    # package content
    packages=find_packages(),
    scripts=get_scripts(),
    include_package_data=False,
    # dependencies
    install_requires=install_requires,
    tests_require=tests_require,
    extras_require=extras_require,
    # classifiers
    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Intended Audience :: Science/Research",
        "Intended Audience :: End Users/Desktop",
        "Intended Audience :: Developers",
        "Natural Language :: English",
        "Topic :: Scientific/Engineering",
        "Topic :: Scientific/Engineering :: Astronomy",
        "Topic :: Scientific/Engineering :: Physics",
        "Operating System :: POSIX",
        "Operating System :: Unix",
        "Operating System :: MacOS",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
    ],
)
