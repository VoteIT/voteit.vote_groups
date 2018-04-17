# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.rst')).read()
CHANGES = open(os.path.join(here, 'CHANGES.rst')).read()


requires = (
    'pyramid',
    'voteit.core',
    'voteit.irl',
    'typing',
    'zope.copy',
)


setup(
    name='voteit.vote_groups',
    version='0.1dev',
    description='Vote groups for VoteIT',
    long_description=README + '\n\n' + CHANGES,
    classifiers=[
        "Programming Language :: Python",
        "Framework :: Pylons",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
    ],
    author='VoteIT development team + contributors',
    author_email='info@voteit.se',
    url='http://www.voteit.se',
    keywords='web pylons pyramid voteit',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=requires,
    tests_require=requires,
    license='GPL',
    test_suite="voteit.vote_groups",
    entry_points="""
        [fanstatic.libraries]
        vote_groups_lib = voteit.vote_groups.fanstaticlib:vote_groups_lib
        """,
)
