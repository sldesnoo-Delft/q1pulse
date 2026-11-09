from abc import ABC, abstractmethod


class Statement(ABC):

    @abstractmethod
    def write_instruction(self, generator):
        pass

