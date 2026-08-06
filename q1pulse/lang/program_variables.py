import math
from abc import abstractmethod

import numpy as np

from .exceptions import Q1ValueError, Q1TypeError


class Variable:
    def __init__(self, dtype: type, init_scope: str = "load", initial_value: float | int | None = None):
        scopes = ["load", "start", "repeat_loop"]
        if init_scope not in scopes:
            raise Q1ValueError(f"Invalid scope {init_scope}. Valid scopes are {scopes}")
        self._dtype = dtype
        self.init_scope = init_scope
        self.initial_value = initial_value

    @property
    def dtype(self):
        return self._dtype

    @abstractmethod
    def value2python(self, value: int) -> int | float:
        ...

    @abstractmethod
    def value2q1asm(self, value: float | int) -> int:
        ...

    def __repr__(self):
        return f"var {self.dtype.__name__}"


class IntVariable(Variable):
    def __init__(self, init_scope: str = "load", initial_value: int | None = None):
        if initial_value is not None and not isinstance(initial_value, int):
            raise Q1TypeError(f"{initial_value} ({type(initial_value)}) cannot be assigned to int")
        super().__init__(int, init_scope=init_scope, initial_value=initial_value)

    def value2python(self, value: int) -> int:
        """Return signed int"""
        return _u32_int(value)

    def value2q1asm(self, value: float | int) -> int:
        """Return unsigned int32"""
        # make unsigned
        return _int_u32(value)


class FloatVariable(Variable):
    def __init__(self, init_scope: str = "load", initial_value: float | None = None):
        if initial_value is not None and (
                not isinstance(initial_value, float)
                or initial_value > 1.0
                or initial_value < -1.0):
            raise Q1TypeError(f"{initial_value} ({type(initial_value)}) cannot be assigned to float")
        super().__init__(float, init_scope=init_scope, initial_value=initial_value)

    def value2python(self, value: int) -> int | float:
        """return float"""
        return _32_float(value)

    def value2q1asm(self, value: float | int) -> int:
        """Return unsigned int32"""
        return _float_to_f32(value)


def _u32_int(value):
    return np.int32(np.uint64(value))


def _32_float(value):
    _f2i32 = (1 << 31) - 1
    return _u32_int(value) / _f2i32


def _int_u32(value):
    return value & 0xFFFF_FFFF


def _float_to_f32(value):
    if value < -1.0 or value > 1.0:
        raise Q1ValueError(f"Fixed point value out of range: {value}")
    _f2i32 = (1 << 31) - 0.1
    return _int_u32(math.floor(value * _f2i32))
