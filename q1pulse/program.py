import os
import time
import logging
import uuid
from collections import defaultdict
from contextlib import contextmanager
from numbers import Number
from typing import Any

from q1pulse.lang.conditions import CounterFlags
from q1pulse.lang.exceptions import Q1InternalError, Q1ValueError, Q1SyntaxError, Q1MemoryError
from q1pulse.lang.feedback import FeedbackEventID
from q1pulse.lang.triggers import TriggerCounter, Trigger
from q1pulse.lang.math_expressions import Expression, Operand
from q1pulse.lang.loops import RangeLoop, LinspaceLoop, ArrayLoop
from q1pulse.lang.program_variables import Variable
from q1pulse.lang.registers import Registers
from q1pulse.lang.register import Register
from q1pulse.lang.register_statements import RegisterAssignment, AllocateVariable
from q1pulse.lang.timeline import Timeline
from q1pulse.assembler.generator import Q1asmGenerator

logger = logging.getLogger(__name__)


class Program:
    verbose = False

    def __init__(self, path=None):
        self.uuid = uuid.uuid4()
        self.sequence_builders = {}
        self.path = path
        # NOTE: global registers are added to ALL sequencers.
        self.R = Registers(self, local=False)
        self.repetitions = 1
        self._q1asm: dict[str, dict[str, Any]] = {}
        self._q1registers: dict[str, dict[str, str]] = {}
        self._var_registers: dict[str, dict[str, str]] = {}  # variable registers per sequencer with short name!
        self._loop_cnt = 0
        self._triggers = []
        self._feedback_event_ids: list[FeedbackEventID] = []
        # shared timeline for all sequencers
        self._timeline = Timeline()

    def add_sequence_builder(self, sequence_builder):
        name = sequence_builder.name
        self.sequence_builders[name] = sequence_builder
        setattr(self, name, sequence_builder)
        sequence_builder.start_sequence(self, self._timeline)

    def __getitem__(self, item):
        if item not in self.sequence_builders:
            raise Exception(f"no sequencer named {item}")
        return self.sequence_builders[item]

    def describe(self):
        for builder in self.sequence_builders.values():
            builder.describe()

    def seq_filename(self, name):
        os.makedirs(self.path, exist_ok=True)
        return os.path.join(self.path, f"q1seq_{name}.json")

    def compile(self, annotate=False, add_comments=True,
                listing=False, json=True, optimize=1):
        # store compiled sequences
        self._q1asm = {}
        self._feedback_routing: dict[int, list[str]] = defaultdict(list)

        start_compile = time.perf_counter()
        for name, builder in self.sequence_builders.items():
            g = Q1asmGenerator(add_comments=add_comments,
                               optimize=optimize,
                               isa_version=builder.isa_version)
            g.repetitions = self.repetitions
            start = time.perf_counter()
            builder.compile(g, annotate=annotate)
            end = time.perf_counter()
            d1 = (end-start)*1000
            start = end
            if listing or json:
                if self.path is None:
                    logger.warning("Set Q1Instrument.path or program.path for Q1ASM output to file.")
                    g.assemble()
                else:
                    filename = self.seq_filename(name)
                    g.assemble(listing=listing, json_output=json, filename=filename)
            else:
                g.assemble()
            max_instructions = 16384  # Maximum for QRM is lower, but module type information is missing...
            if g.n_q1asm_instructions > max_instructions:
                raise Q1MemoryError("Program too big for instruction memory: "
                                    f"{g.n_q1asm_instructions} > {max_instructions}.")
            self._q1asm[name] = g.q1asm
            self._q1registers[name] = g.registers
            for event_id in builder.subscribed_event_ids:
                self._feedback_routing[event_id].append(name)

            duplicate_variables = set(self.R.variables.keys()) & set(builder.Rs.variables.keys())
            if duplicate_variables:
                raise Q1SyntaxError(f"Duplicate variable names: {duplicate_variables}")
            variable_name_mapping = {name: f"R.{name}" for name in self.R.variables}
            variable_name_mapping |= {name: f"Rs.{name}" for name in builder.Rs.variables}
            self._var_registers[name] = {
                short_name: g.registers[name] for short_name, name in variable_name_mapping.items()
                }

            end = time.perf_counter()
            d2 = (end-start)*1000
            if Program.verbose:
                logger.debug(f"compile {name} {d1:5.2f} {d2:5.2f} ms")
        duration = time.perf_counter() - start_compile
        logger.debug(f"Total compilation {duration*1000:5.2f} ms")

    def q1asm(self, name):
        return self._q1asm[name]

    def list_variables(self) -> dict[str, dict[str, Variable]]:
        res = {}
        res["program"] = self.R.variables
        for name, builder in self.sequence_builders.items():
            res[name] = builder.Rs.variables
        return res

    @property
    def register_mapping(self) -> dict[str, dict[str, str]]:
        return self._q1registers

    @property
    def variable_register_mapping(self) -> dict[str, dict[str, str]]:
        return self._var_registers

    @property
    def feedback_routing(self) -> dict[int, list[str]]:
        return self._feedback_routing

    def _add_statement(self, statement, init_section=False):
        if not isinstance(statement, RegisterAssignment | AllocateVariable):
            raise Q1InternalError(f"Illegal statement for program: {statement}")
        for builder in self.sequence_builders.values():
            builder._add_statement(statement, init_section=init_section)

    def loop_range(self, start_stop, stop=None, step=None):
        """ range loop """
        return self.__loop(RangeLoop(self._loop_cnt, start_stop, stop, step))

    def loop_linspace(self, start, end, n, endpoint=True):
        """ repeat loop """
        return self.__loop(LinspaceLoop(self._loop_cnt, start, end, n, endpoint))

    def loop_array(self, values):
        """ array loop """
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
    def if_(self, condition: Operand):
        for s in self.sequence_builders.values():
            s.enter_if(condition)
        yield
        for s in self.sequence_builders.values():
            s.exit_if()

    @contextmanager
    def elif_(self, condition: Operand):
        for s in self.sequence_builders.values():
            s.enter_elif(condition)
        yield
        for s in self.sequence_builders.values():
            s.exit_elif()

    @property
    @contextmanager
    def else_(self):
        for s in self.sequence_builders.values():
            s.enter_else()
        yield
        for s in self.sequence_builders.values():
            s.exit_else()

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

    def configure_trigger(self, sequencer_name: str, invert: bool = False) -> Trigger:
        addr = len(self._triggers)+1
        trigger = Trigger(sequencer_name, address=addr, invert=invert)
        self._triggers.append(trigger)
        self.sequence_builders[sequencer_name].trigger = trigger
        return trigger

    def add_trigger_counter(self, trigger: Trigger, threshold: int = 1, invert: bool = False) -> TriggerCounter:
        counter = TriggerCounter(trigger, threshold=threshold, invert=invert)
        for s in self.sequence_builders.values():
            s._add_trigger_counter(counter)
        return counter

    def latch_enable(self, enable: bool, t_offset: int = 0):
        for s in self.sequence_builders.values():
            s.latch_enable(enable, t_offset=t_offset)

    def latch_reset(self, t_offset: int = 0):
        for s in self.sequence_builders.values():
            s.latch_reset(t_offset=t_offset)

    def register_feedback_event(self, name: str) -> FeedbackEventID:
        for event in self._feedback_event_ids:
            if event.name == name:
                raise Q1ValueError(f"Feedback event with name '{name}' has already been registered")
        event_id = 20 + len(self._feedback_event_ids)
        feedback_event_id = FeedbackEventID(name, event_id)
        self._feedback_event_ids.append(feedback_event_id)
        return feedback_event_id

    def add_comment(self, comment):
        for s in self.sequence_builders.values():
            s.add_comment(comment)

    def wait(self, t):
        if isinstance(t, Number):
            if t < 0:
                raise Q1ValueError("Wait time must be positive")
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
                raise Q1ValueError("Variable pulse length not possible in parallel section")
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
