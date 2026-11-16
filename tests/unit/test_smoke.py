"""골격 스모크 테스트. 설치된 패키지와 하위 패키지가 import되는지만 본다."""

import importlib

import pytest

SUBPACKAGES = ("common", "ingest", "transform", "mart", "validate", "serving")


def test_package_imports():
    assert importlib.import_module("quantdata").__name__ == "quantdata"


@pytest.mark.parametrize("name", SUBPACKAGES)
def test_subpackage_imports(name):
    importlib.import_module(f"quantdata.{name}")
