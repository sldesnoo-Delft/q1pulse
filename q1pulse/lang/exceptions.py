
class Q1Exception(Exception):
    '''
    Base for Q1Pulse exceptions.
    '''
    pass

class Q1InternalError(Q1Exception):
    '''
    Raised when something unexpected fails in Q1Pulse
    most likely caused by coding error in Q1Pulse.
    '''


class Q1NameError(Q1Exception):
    '''
    Raised when a register is not defined, or already defined.
    '''
    pass

class Q1TypeError(Q1Exception):
    '''
    Raised when expression or argument types do not match.
    '''

class Q1ValueError(Q1Exception):
    '''
    Raised when invalid value is passed.
    '''

class Q1CompileError(Q1Exception):
    '''
    Raised when the error is detected during compilation.
    '''

class Q1SequenceError(Q1Exception):
    '''
    Raised when the error is detected during compilation.
    '''
    def __init__(self, msg, traceback):
        self.msg = msg
        self.traceback = traceback

class Q1MemoryError(Q1Exception):
    '''
    Raised when no free register is left to allocate.
    '''

class Q1TimingError(Q1Exception):
    '''
    Raised when the timing of commands doesn't fit.
    '''

class Q1StateError(Q1Exception):
    '''
    Raised when program or sequence is modified after compilation.
    '''

class Q1InputOverloaded(Q1Exception):
    '''
    Raised when the input of QRM is overloaded during acquisition.
    Exception can be suppressed with `q1pulse.set_exception_on_overload(False)`.
    '''
