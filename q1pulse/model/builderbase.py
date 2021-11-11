from abc import ABC, abstractmethod

class BuilderBase(ABC):

    @abstractmethod
    def _add_statement(self, name, init_section=False):
        pass


class Statement(ABC):

    @abstractmethod
    def write_instruction(self, generator):
        pass


class Typed(ABC):

    @property
    @abstractmethod
    def dtype(self):
        pass


class Expression(Typed, ABC):

    @abstractmethod
    def evaluate(self, builder, destination=None):
        pass

def get_dtype(value):
    if isinstance(value, int):
        return int
    if isinstance(value, float):
        return float
    if isinstance(value, Typed):
        return value.dtype
