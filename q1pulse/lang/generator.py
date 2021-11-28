from abc import ABC, abstractmethod

class GeneratorBase(ABC):
    @abstractmethod
    def add_comment(self, line, init_section=False):
        pass

    @abstractmethod
    def jmp(self, label):
        pass

    @abstractmethod
    def jlt(self, register, n, label):
        pass

    @abstractmethod
    def jge(self, register, n, label):
        pass

    @abstractmethod
    def loop(self, register, label):
        pass

    @abstractmethod
    def move(self, source, destination, init_section=False):
        pass

    @abstractmethod
    def add(self, lhs, rhs, destination):
        pass

    @abstractmethod
    def sub(self, lhs, rhs, destination):
        pass

    @abstractmethod
    def asl(self, lhs, rhs, destination):
        pass

    @abstractmethod
    def asr(self, lhs, rhs, destination):
        pass

    @abstractmethod
    def bits_not(self, source, destination):
        pass

    @abstractmethod
    def bits_and(self, lhs, rhs, destination):
        pass

    @abstractmethod
    def bits_or(self, lhs, rhs, destination):
        pass

    @abstractmethod
    def bits_xor(self, lhs, rhs, destination):
        pass

    @abstractmethod
    def wait_till(self, time):
        pass

    @abstractmethod
    def wait_reg(self, time, reg):
        pass

    @abstractmethod
    def awg_offset(self, time, offset0, offset1):
        pass

    @abstractmethod
    def awg_gain(self, time, gain0, gain1):
        pass

    @abstractmethod
    def play(self, time, wave0, wave1):
        pass

    @abstractmethod
    def acquire(self, time, section, bin_index):
        pass