from os import path
from typing import Dict, List, Tuple

from setuptools import setup


VERSION_PATH = path.join(path.abspath(path.dirname(__file__)), "VERSION")
with open(VERSION_PATH, encoding="utf-8", mode="r") as f:
    VERSION = f.read().strip()


def _long_description() -> Tuple[str, str]:
    return open("README.md", "r", encoding="utf-8").read(), "text/markdown"


_dependencies = [
    "argparse",
    "decorator",
    "hiredis",
    "redis",
    "typing_extensions>=4.8.0",
]

_dev_dependencies = [
    "black==23.12.1",
    "build==1.0.3",
    "isort==5.8.0",
    "mypy~=1.7.0",
    "pre-commit==2.20.0",
    "removestar==1.3.1",
    "safety==2.3.4",
    "twine==4.0.2",
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


long_description, long_description_content_type = _long_description()

setup(
    author="Danny Guinther",
    author_email="dannyguinther@gmail.com",
    classifiers=[
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
    ],
    description="Redis-based Queue Management",
    keywords="redis, qless, job",
    license="MIT License",
    long_description=long_description,
    long_description_content_type=long_description_content_type,
    name="qless-with-throttles",
    packages=[
        "qless",
        "qless.abstract",
        "qless.queue_resolvers",
        "qless.workers",
        "qmore",
    ],
    package_data={"qless": ["lua/*.lua"]},
    package_dir={
        "qless": "qless",
        "qless.abstract": "qless/abstract",
        "qless.queue_resolvers": "qless/queue_resolvers",
        "qless.workers": "qless/workers",
        "qmore": "qmore",
    },
    extras_require=_extra_requires(),
    include_package_data=True,
    install_requires=_install_requires(),
    scripts=["bin/qless-py-worker"],
    tests_requires=_test_requires(),
    url="http://github.com/tdg5/qless-py",
    version=VERSION,
)
