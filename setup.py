from typing import Dict, List

from setuptools import setup


_dependencies = [
    "argparse",
    "decorator",
    "hiredis",
    "redis",
]

_dev_dependencies = [
    "black==21.5b2",
    "click<8.1",
    "isort==5.8.0",
    "mypy~=1.7.0",
    "pre-commit==2.20.0",
    "removestar==1.3.1",
    "safety==2.3.5",
    "types-decorator==5.1.8.4",
    "types-mock==5.1.0.2",
]

_test_dependencies = [
    "coverage",
    "mock",
    "nose",
    "rednose",
    "setuptools>=17.1",
]


def _extra_requires() -> Dict:
    return {
        "all": [_dependencies, _dev_dependencies, _test_dependencies],
        "deps": _dependencies,
        "dev": _dev_dependencies,
        "test": _test_dependencies,
    }


def _install_requires() -> List:
    return _dependencies


def _test_requires() -> List:
    return _test_dependencies


setup(
    name="qless-with-throttles",
    version="0.12.0a2",
    description="Redis-based Queue Management",
    long_description="Fork of seomoz/qless-py with support for throttles.",
    url="http://github.com/tdg5/qless-py",
    author="Danny Guinther",
    author_email="dannyguinther@gmail.com",
    license="MIT License",
    keywords="redis, qless, job",
    packages=["qless", "qless.queue_resolvers", "qless.workers", "qmore"],
    package_dir={
        "qless": "qless",
        "qless.queue_resolvers": "qless/queue_resolvers",
        "qless.workers": "qless/workers",
        "qmore": "qmore",
    },
    package_data={"qless": ["lua/*.lua"]},
    include_package_data=True,
    scripts=["bin/qless-py-worker"],
    extras_require=_extra_requires(),
    install_requires=_install_requires(),
    tests_requires=_test_requires(),
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
    ],
)
