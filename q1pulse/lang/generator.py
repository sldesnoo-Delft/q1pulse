from abc import ABC, abstractmethod
from contextlib import contextmanager

class GeneratorBase(ABC):
    @property
    @abstractmethod
    def repetitions(self):
        pass

    @repetitions.setter
    @abstractmethod
    def repetitions(self, value):
        pass

    @abstractmethod
    def start_main(self):
        pass

    @abstractmethod
    def finalize(self):
        pass

    @abstractmethod
    def add_comment(self, line, init_section=False):
        pass

    @abstractmethod
    def set_label(self, label):
        '''
        Label to be added to next instruction
        '''
        pass

    @abstractmethod
    def adjust_time(self, duration):
        pass

    @abstractmethod
    def sync(self, time):
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
    def wait_reg(self, time, reg):
        pass

    @abstractmethod
    def set_mrk(self, time, value):
        pass

    @abstractmethod
    def awg_offset(self, time, offset0, offset1):
        pass

    @abstractmethod
    def awg_gain(self, time, gain0, gain1):
        pass

    @abstractmethod
    def reset_phase(self, time):
        pass

    @abstractmethod
    def set_phase(self, time, phase, hires_regs):
        pass

    @abstractmethod
    def add_phase(self, time, delta, hires_regs):
        pass

    @abstractmethod
    def play(self, time, wave0, wave1):
        pass

    @abstractmethod
    def acquire(self, time, section, bin_index):
        pass

    @abstractmethod
    def acquire_weighed(self, time, bins, bin_index, weight0, weight1):
        pass

    @abstractmethod
    @contextmanager
    def scope(self):
        pass

    @abstractmethod
    def get_temp_reg(self):
        ''' Allocates an assembler register for temporary use within scope. '''
        pass

    @abstractmethod
    def allocate_reg(self, name):
        pass
