"""Freezing metadata makes one Python call for each dict and list, and none for each plain value.

A plain value is one whose type is exactly ``str``, ``int``, ``float``, ``bool`` or ``None``. The
test counts the Python calls into ``taxomesh/domain/types.py``, the module of the freeze, while one
model is built: metadata with 4 plain values and metadata with 400, in the same dicts and lists,
cost the same number of calls. That is two calls more than empty metadata: one for the list in it
and one for the dict in it. ``docs/design.md``, "Frozen rows", says why this is the cost.
"""

import sys
from collections.abc import Callable
from types import FrameType
from typing import Any

import pytest

from taxomesh.domain import types
from tests.domain.test_frozen_models import METADATA_ROWS

LEAVES: tuple[object, ...] = ("text", 1, 1.5, True, None)


# Any: metadata whose values are the plain values of LEAVES.
def _metadata(values: int) -> dict[str, Any]:
    """Return metadata with ``values`` plain values: half in a list, half in a dict."""
    half = values // 2
    return {
        "list": [LEAVES[n % len(LEAVES)] for n in range(half)],
        "dict": {f"key {n}": LEAVES[n % len(LEAVES)] for n in range(half)},
    }


def _calls_into_the_freeze(build: Callable[[], object]) -> int:
    """Return how many Python calls ``build()`` makes into ``taxomesh/domain/types.py``."""
    calls = 0

    def count(frame: FrameType, event: str, arg: object) -> None:
        nonlocal calls
        if event == "call" and frame.f_code.co_filename == types.__file__:
            calls += 1

    previous = sys.getprofile()
    sys.setprofile(count)
    try:
        build()
    finally:
        sys.setprofile(previous)
    return calls


@pytest.mark.parametrize("model", METADATA_ROWS)
def test_freezing_makes_one_call_for_each_dict_and_list_and_none_for_each_value(model: str) -> None:
    build = METADATA_ROWS[model]
    few, many = _metadata(4), _metadata(400)

    calls_for_empty = _calls_into_the_freeze(lambda: build({}))
    calls_for_few = _calls_into_the_freeze(lambda: build(few))
    calls_for_many = _calls_into_the_freeze(lambda: build(many))

    assert 0 < calls_for_few == calls_for_many, f"{calls_for_few} calls for 4 values, {calls_for_many} for 400"
    assert calls_for_few - calls_for_empty == 2, "one call for the list and one for the dict"
