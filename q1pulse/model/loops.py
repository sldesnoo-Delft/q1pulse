from functools import wraps
from dataclasses import dataclass
from abc import abstractmethod, ABC

class Loop(ABC):
    def set_number(self, number):
        self._number = number

    @property
    @abstractmethod
    def loopvar(self):
        pass

class RepeatLoop(Loop):
    def __init__(self, n):
        self._n = n

    def set_number(self, number):
        self._number = number
        self._reg_name = f'_i{self._number}'

    @property
    def n(self):
        return self._n

    @property
    def loopvar(self):
        return None

    def reg_name(self):
        return self._reg_name

class RangeLoop(Loop):
    def __init__(self, start_stop, stop=None, step=None):
        if stop is None:
            self._start = 0
            self._stop = start_stop
        else:
            self._start = start_stop
            self._stop = stop
        self._step = 1 if step is None else step

    def set_number(self, number):
        self._number = number
        self._reg_name = f'_i{self._number}'
        self._loopvar = LoopVar(self._reg_name)
        self._loop_stop = f'_stop{self._number}'

    @property
    def start(self):
        return self._start

    @property
    def stop(self):
        return self._stop

    @property
    def step(self):
        return self._step

    @property
    def loopvar(self):
        return self._loopvar

    def reg_names(self):
        return [self._reg_name, self._loop_stop]

class LinspaceLoop(Loop):
    def __init__(self, start, stop, n, endpoint=True):
        if max(start,stop) > 1.0 or min(start,stop) < -1.0:
            raise Exception('value out of range [-1.0, 1.0]')
        self._start = start
        self._stop = stop
        self._n = n
        self._endpoint = endpoint
        step_divisor = (n-1) if endpoint else n
        self._increment = (stop - start)/step_divisor

    def set_number(self, number):
        self._number = number
        self._reg_names = [
                f'_i{self._number}',
                f'_f{self._number}',
                ]
        self._loopvar = LoopVar(self._reg_names[1])

    @property
    def n(self):
        return self._n

    @property
    def start(self):
        return self._start

    @property
    def stop(self):
        return self._stop

    @property
    def endpoint(self):
        return self._endpoint

    @property
    def increment(self):
        return self._increment

    @property
    def loopvar(self):
        return self._loopvar

    def reg_names(self):
        return self._reg_names


@dataclass
class LoopVar:
    reg_name: str


def loopable(func):

    @wraps(func)
    def func_wrapper(self, *args, **kwargs):
        args = list(args)
        kwargs = kwargs.copy()
        for i,arg in enumerate(args):
            if isinstance(arg, LoopVar):
                args[i] = self.Rs[arg.reg_name]
        for k,v in kwargs.items():
            if isinstance(v, LoopVar):
                kwargs[k] = self.Rs[v.reg_name]

        return func(self, *args, **kwargs)


    return func_wrapper

