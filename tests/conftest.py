"""tests/<unit|integration|pit>/ 아래 테스트에 디렉토리 이름과 같은 marker를 붙인다.

marker를 빠뜨린 DB 테스트가 `make test`에 섞여 실행되거나, `-m integration`에서
조용히 빠지는 일을 막는다.
"""

import pathlib

import pytest

_TESTS_ROOT = pathlib.Path(__file__).parent
_DIR_MARKERS = ("unit", "integration", "pit")


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items):
    for item in items:
        try:
            top = pathlib.Path(item.path).relative_to(_TESTS_ROOT).parts[0]
        except ValueError:
            continue
        if top in _DIR_MARKERS:
            item.add_marker(getattr(pytest.mark, top))
