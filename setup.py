# Copyright 2018, ETH Zurich - Swiss Seismological Service SED
'''
setup.py for ramsis-sfm
'''

import sys
from setuptools import setup

if sys.version_info[:2] < (3, 8):
    raise RuntimeError('Python version >= 3.8 required.')


_authors = []

_authors_email = [
    ]

_install_requires = [
    ]

_extras_require = {
    }

_name = 'etas'
_version = 0.1
_description = (
)

_packages = ['etas',
             'runnable_code',
             'utils']

_entry_points = {
    }

# ----------------------------------------------------------------------------
setup(
    name=_name,
    version=_version,
    author=' (SED, ETHZ),'.join(_authors),
    author_email=', '.join(_authors_email),
    description=_description,
    license='AGPL',
    packages=_packages,
    entry_points=_entry_points,
    install_requires=_install_requires,
    extras_require=_extras_require,
    include_package_data=True,
    zip_safe=False,
)
