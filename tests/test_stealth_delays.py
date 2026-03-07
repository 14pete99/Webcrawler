"""Tests for app.stealth.delays module."""

import asyncio

import pytest

from app.stealth.delays import async_delay, make_delay_func


class TestMakeDelayFunc:
    def test_uniform_within_bounds(self):
        fn = make_delay_func(1000, 3000, distribution="uniform")
        for _ in range(50):
            val = fn()
            assert 1.0 <= val <= 3.0

    def test_gaussian_within_clamped_bounds(self):
        fn = make_delay_func(1000, 3000, distribution="gaussian")
        for _ in range(50):
            val = fn()
            assert 1.0 <= val <= 3.0

    def test_poisson_within_clamped_bounds(self):
        fn = make_delay_func(1000, 3000, distribution="poisson")
        for _ in range(50):
            val = fn()
            assert 1.0 <= val <= 3.0

    def test_lognormal_within_clamped_bounds(self):
        fn = make_delay_func(1000, 3000, distribution="lognormal")
        for _ in range(50):
            val = fn()
            assert 1.0 <= val <= 3.0

    def test_default_is_uniform(self):
        fn = make_delay_func(500, 1500)
        for _ in range(50):
            val = fn()
            assert 0.5 <= val <= 1.5

    def test_returns_callable(self):
        fn = make_delay_func()
        assert callable(fn)

    def test_returns_float(self):
        fn = make_delay_func()
        assert isinstance(fn(), float)

    def test_zero_range(self):
        fn = make_delay_func(1000, 1000, distribution="uniform")
        assert fn() == 1.0


class TestAsyncDelay:
    @pytest.mark.asyncio
    async def test_none_func_no_delay(self):
        await async_delay(None)  # should return immediately

    @pytest.mark.asyncio
    async def test_calls_delay_func(self):
        called = []
        def fake_delay():
            called.append(True)
            return 0.001
        await async_delay(fake_delay)
        assert len(called) == 1
