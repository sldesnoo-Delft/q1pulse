from abc import ABC, abstractmethod

class BuilderBase(ABC):

    @abstractmethod
    def _add_statement(self, name, init_section=False):
        pass


class Statement(ABC):

    @abstractmethod
    def write_instruction(self, generator):
        pass

