#! /usr/bin/env python

from setuptools import setup

setup(
    name='qless-with-throttles',
    version='0.11.4',
    description='Redis-based Queue Management',
    long_description='Fork of seomoz/qless-py with support for throttles.',
    url='http://github.com/tdg5/qless-py',
    author='Danny Guinther',
    author_email='dannyguinther@gmail.com',
    license="MIT License",
    keywords='redis, qless, job',
    packages=[
        'qless',
        'qless.workers'
    ],
    package_dir={
        'qless': 'qless',
        'qless.workers': 'qless/workers'
    },
    package_data={
        'qless': [
            'lua/*.lua'
        ]
    },
    include_package_data=True,
    scripts=[
        'bin/qless-py-worker'
    ],
    extras_require={
        'ps': [
            'setproctitle'
        ]
    },
    install_requires=[
        'argparse',
        'decorator',
        'hiredis',
        'redis',
        'six',
        'simplejson'
    ],
    tests_requires=[
        'coverage',
        'mock',
        'nose',
        'rednose',
        'setuptools>=17.1'
    ],
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent'
    ]
)
