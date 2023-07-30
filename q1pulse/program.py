import os
import time
import logging
from contextlib import contextmanager
from numbers import Number

from .lang.conditions import CounterFlags
from .lang.exceptions import Q1InternalError, Q1ValueError
from .lang.triggers import TriggerCounter, Trigger
from .lang.math_expressions import Expression
from .lang.timeline import Timeline
from .lang.registers import Registers
from .lang.register import Register
from .lang.register_statements import RegisterAssignment
from .lang.loops import RangeLoop, LinspaceLoop, ArrayLoop
from .assembler.generator import Q1asmGenerator

logger = logging.getLogger(__name__)

class Program:
    def __init__(self, path=None):
        self.sequence_builders = {}
        self.path = path if path is not None else os.path.join('q1','_prog')
        self.R = Registers(self, local=False)
        self.repetitions = 1
        self._q1asm = {}
        self._loop_cnt = 0
        self._triggers = []
        # shared timeline for all sequencers
        self._timeline = Timeline()

    def add_sequence_builder(self, sequence_builder):
        name = sequence_builder.name
        self.sequence_builders[name] = sequence_builder
        setattr(self, name, sequence_builder)
        sequence_builder.start_sequence(self, self._timeline)

    def __getitem__(self, item):
        if item not in self.sequence_builders:
            raise Exception(f'no sequencer named {item}')
        return self.sequence_builders[item]

    def describe(self):
        for builder in self.sequence_builders.values():
            builder.describe()

    def seq_filename(self, name):
        os.makedirs(self.path, exist_ok=True)
        return os.path.join(self.path, f'q1seq_{name}.json')

    def compile(self, annotate=False, add_comments=True,
                listing=False, json=True, optimize=1):
        # store compiled sequences
        self._q1asm = {}

        start_compile = time.perf_counter()
        for builder in self.sequence_builders.values():
            g = Q1asmGenerator(add_comments=add_comments,
                               optimize=optimize)
            g.repetitions = self.repetitions
            start = time.perf_counter()
            builder.compile(g, annotate=annotate)
            end = time.perf_counter()
            d1 = (end-start)*1000
            start = end
            filename = self.seq_filename(builder.name) if listing or json else None
            g.assemble(listing=listing, json_output=json, filename=filename)
            self._q1asm[builder.name] = g.q1asm
            end = time.perf_counter()
            d2 = (end-start)*1000
            logger.debug(f'compile {builder.name} {d1:5.2f} {d2:5.2f}')
        duration = time.perf_counter() - start_compile
        logger.debug(f'Total compilation {duration*1000:5.2f}')

    def q1asm(self, name):
        return self._q1asm[name]

    def _add_statement(self, statement, init_section=False):
        if not isinstance(statement, RegisterAssignment):
            raise Q1InternalError(f'Illegal statement for program {statement}')
        for builder in self.sequence_builders.values():
            builder._add_statement(statement, init_section=init_section)

    def loop_range(self, start_stop, stop=None, step=None):
        ''' range loop '''
        return self.__loop(RangeLoop(self._loop_cnt, start_stop, stop, step))

    def loop_linspace(self, start, end, n, endpoint=True):
        ''' repeat loop '''
        return self.__loop(LinspaceLoop(self._loop_cnt, start, end, n, endpoint))

    def loop_array(self, values):
        ''' array loop '''
        return self.__loop(ArrayLoop(self._loop_cnt, values))

    @contextmanager
    def __loop(self, loop):
        self._loop_cnt += 1
        for s in self.sequence_builders.values():
            s.enter_loop(loop)

        yield loop.loopvar

        for s in self.sequence_builders.values():
            s.exit_loop(loop)

    @contextmanager
    def parallel(self):
        self._timeline.disable_update()
        yield
        self._timeline.enable_update()

    @contextmanager
    def conditional(self, counters, t_offset=0, evaluation_time=0):
        for s in self.sequence_builders.values():
            s.enter_conditional(counters, t_offset=t_offset, evaluation_time=evaluation_time)
        flags = CounterFlags(self)
        yield flags
        for s in self.sequence_builders.values():
            s.exit_conditional()

    @contextmanager
    def condition(self, operator):
        for s in self.sequence_builders.values():
            s.enter_condition(operator)
        yield
        for s in self.sequence_builders.values():
            s.exit_condition()

    def configure_trigger(self, sequencer_name, invert=False):
        addr = len(self._triggers)+1
        trigger = Trigger(sequencer_name, address=addr, invert=invert)
        self._triggers.append(trigger)
        self.sequence_builders[sequencer_name].trigger = trigger
        return trigger

    def add_trigger_counter(self, trigger, threshold=1, invert=False):
        counter = TriggerCounter(trigger, threshold=threshold, invert=invert)
        for s in self.sequence_builders.values():
            s._add_trigger_counter(counter)
        return counter

    def latch_enable(self, counters, t_offset=0):
        for s in self.sequence_builders.values():
            s.latch_enable(counters, t_offset=t_offset)

    def latch_reset(self, t_offset=0):
        for s in self.sequence_builders.values():
            s.latch_reset(t_offset=t_offset)

    def add_comment(self, comment):
        for s in self.sequence_builders.values():
            s.add_comment(comment)

    def wait(self, t):
        if isinstance(t, Number):
            if t < 0:
                raise Q1ValueError('Wait time must be positive')
            self._timeline.set_pulse_end(self._timeline.current_time + t)
        else:
            for s in self.sequence_builders.values():
                s._add_reg_wait(t)

    def block_pulse(self, duration, sequencers, amplitudes, t_offset=0):
        if not isinstance(duration, (Register, Expression)):
            self._timeline.disable_update()
            for s, a in zip(sequencers, amplitudes):
                if isinstance(s, str):
                    s = self[s]
                s.block_pulse(duration, a, t_offset=t_offset)
            self._timeline.enable_update()
        else:
            if not self._timeline.is_running:
                raise Q1ValueError('Variable pulse length not possible in parallel section')
            self.set_offsets(sequencers, amplitudes, t_offset=t_offset)
            self.wait(duration)
            self.set_offsets(sequencers, [0.0]*len(sequencers), t_offset=0)

    def ramp(self, duration, sequencers, v_start, v_stop, t_offset=0):
        self._timeline.disable_update()
        for s, v1, v2 in zip(sequencers, v_start, v_stop):
            if isinstance(s, str):
                s = self[s]
            s.ramp(duration, v1, v2, t_offset=t_offset)
        self._timeline.enable_update()

    def set_offsets(self, sequencers, offsets, t_offset=0):
        self._timeline.disable_update()
        for s, offset in zip(sequencers, offsets):
            if isinstance(s, str):
                s = self[s]
            s.set_offset(offset, t_offset=t_offset)
        self._timeline.enable_update()

