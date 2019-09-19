from datetime import timedelta
from sovereign.decorators import memoize


def test_memoize_decorator():
    """ We know the decorator works because the inside function is only called once. """

    def inner():
        inner.calls = getattr(inner, 'calls', 0)
        inner.calls += 1
        return 'something so that it gets memoized'

    @memoize(5)
    def cached_function():
        return inner()

    @memoize(timedelta(hours=1))
    def cached_function2():
        return inner()

    for _ in range(100):
        cached_function()

    assert inner.calls == 1

    for _ in range(100):
        cached_function2()

    assert inner.calls == 2
