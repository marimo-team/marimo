import sys

import pytest

from marimo._runtime.copy import (
    ReadOnlyError,
    ShallowCopy,
    ZeroCopy,
    _Copy,
    shadow_wrap,
    shallow_copy,
    unwrap_copy,
    zero_copy,
)


def test_shadow_wrap() -> None:
    base = 1
    shadow = shadow_wrap(_Copy, base)
    assert shadow == base
    assert base == shadow
    assert isinstance(shadow, _Copy)
    assert isinstance(shadow, int)
    assert str(shadow) == "1"
    assert shadow.__class__.__name__ == "int"
    assert shadow + 1 == 2
    assert 1 + shadow == 2


@pytest.mark.xfail(
    sys.version_info >= (3, 13),
    reason="__slots__ conflicts with class variable in Python 3.13",
)
def test_shadow_wrap_ro_attr() -> None:
    class namespace: ...

    base = namespace()
    base.attr = 1
    shadow = shadow_wrap(_Copy, base)

    assert isinstance(shadow, _Copy)
    assert isinstance(shadow, namespace)
    assert shadow.__class__.__name__ == "namespace"
    assert shadow.attr == 1
    # assignment should fail
    with pytest.raises(ReadOnlyError):
        shadow.attr = 2


def test_shadow_wrap_ro_get() -> None:
    base = [1, 2, 3]
    shadow = shadow_wrap(_Copy, base)

    assert base == shadow
    # assignment should fail
    with pytest.raises(ReadOnlyError):
        shadow[0] = 2


@pytest.mark.xfail(
    sys.version_info >= (3, 13),
    reason="__slots__ conflicts with class variable in Python 3.13",
)
def test_shadow_wrap_mutable_ref() -> None:
    class namespace: ...

    base = namespace()
    base.attr = 1
    base.arr = [1, 2, 3]
    shadow = shadow_wrap(_Copy, base)

    assert base.attr == shadow.attr
    assert base.arr is shadow.arr

    base.arr[0] = 2
    base.arr[2] = 2
    base.arr.append(4)
    base.attr = 2

    assert base.attr == shadow.attr
    assert base.arr is shadow.arr


def test_zero_copy() -> None:
    base = [1]
    shadow = zero_copy(base)
    assert shadow == base
    assert base == shadow
    assert isinstance(shadow, ZeroCopy)
    assert isinstance(shadow, list)
    assert str(shadow) == "[1]"
    assert shadow.__class__.__name__ == "list"
    assert shadow + [1] == [1, 1]
    assert id(unwrap_copy(shadow)) == id(base)


def test_shallow_copy() -> None:
    base = [1]
    shadow = shallow_copy(base)
    assert shadow == base
    assert base == shadow
    assert isinstance(shadow, ShallowCopy)
    assert isinstance(shadow, list)
    assert str(shadow) == "[1]"
    assert shadow.__class__.__name__ == "list"
    assert shadow + [1] == [1, 1]
    assert id(unwrap_copy(shadow)) != id(base)


def test_double_zero() -> None:
    base = [1]
    shadow = zero_copy(base)
    shadow2 = zero_copy(shadow)
    assert shadow2 == base
    assert isinstance(unwrap_copy(shadow2), list)
    assert not isinstance(unwrap_copy(shadow2), ZeroCopy)
    assert id(unwrap_copy(shadow2)) == id(base)


def test_double_shallow() -> None:
    base = [1]
    shadow = shallow_copy(base)
    shadow2 = shallow_copy(shadow)
    assert shadow2 == base
    assert isinstance(unwrap_copy(shadow2), list)
    assert not isinstance(unwrap_copy(shadow2), ShallowCopy)
    assert id(unwrap_copy(shadow2)) != id(base)


def test_cross_zero_shallow() -> None:
    base = [1]
    shadow = zero_copy(base)
    shadow2 = shallow_copy(shadow)
    assert shadow2 == base
    assert isinstance(unwrap_copy(shadow2), list)
    assert not isinstance(unwrap_copy(shadow2), ZeroCopy)
    assert id(unwrap_copy(shadow2)) != id(base)


def test_cross_shallow_zero() -> None:
    base = [1]
    shadow = shallow_copy(base)
    shadow2 = zero_copy(shadow)
    assert shadow2 == base
    assert isinstance(unwrap_copy(shadow2), list)
    assert not isinstance(unwrap_copy(shadow2), ShallowCopy)
    assert id(unwrap_copy(shadow2)) != id(base)
