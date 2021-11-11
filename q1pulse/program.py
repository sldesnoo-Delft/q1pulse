import os
from contextlib import contextmanager
from numbers import Number

from .model.timeline import Timeline
from .model.registers import Registers
from .model.register_statements import RegisterAssignment
from .model.loops import RangeLoop, LinspaceLoop
from .assembler.generator import Q1asmGenerator


class Program:
    def __init__(self, sequence_builders, path=None):
        self.sequence_builders = sequence_builders
        self.path = path if path is not None else os.path.join('q1','_prog')
        os.makedirs(self.path, exist_ok=True)
        self.R = Registers(self, local=False)
        self.repetitions = 1 # TODO @@@ implement overall loop
        self._loop_cnt = 0
        # shared timeline for all sequencers
        self._timeline = Timeline()

        # for all sequencers add attribute with sequence
        for name, builder in sequence_builders.items():
            setattr(self, name, builder)
            builder.start_sequence(self._timeline)

    def __getitem__(self, item):
        if item not in self.sequence_builders:
            raise Exception(f'no sequencer named {item}')
        return self.sequence_builders[item]

    def describe(self):
        for builder in self.sequence_builders.values():
            builder.describe()

    def seq_filename(self, name):
        return os.path.join(self.path, f'q1seq_{name}.json')

    def compile(self, verbose=False, annotate=False, add_comments=True, listing=False):
        for builder in self.sequence_builders.values():
            filename = self.seq_filename(builder.name)
            g = Q1asmGenerator(add_comments=add_comments)
            builder.compile(g, annotate=annotate)

            if verbose:
                print(f'seq_{builder.name}="""')
                print(g.q1asm_prog())
                print('"""')
                print()
            if listing:
                g.save_prog_and_data_txt(filename.replace('.json','.txt'))
            g.save_prog_and_data_json(filename)

    def _add_statement(self, statement):
        if not isinstance(statement, RegisterAssignment):
            raise Exception(f'Illegal statement for program {statement}')
        for builder in self.sequence_builders.values():
            builder._add_statement(statement)

    def loop(self, start_stop, stop=None, step=None):
        ''' range loop '''
        return self.__loop(RangeLoop(start_stop, stop, step))

    def loop_linspace(self, start, end, n):
        ''' repeat loop '''
        return self.__loop(LinspaceLoop(start, end, n))

    @contextmanager
    def __loop(self, loop):
        label = f'loop_{self._loop_cnt}'
        loop.set_number(self._loop_cnt)
        self._loop_cnt += 1
        for s in self.sequence_builders.values():
            s.enter_loop(label, loop)
#        self._timeline.reset() # probably not needed. All time is relative. Other perspective: time is repeated.

        yield loop.loopvar

        for s in self.sequence_builders.values():
            s.exit_loop()
#        self._timeline.reset()


    @contextmanager
    def parallel(self):
        self._timeline.disable_update()
        yield
        self._timeline.enable_update()

    def add_comment(self, comment):
        for s in self.sequence_builders.values():
            s.add_comment(comment)

    def wait(self, t):
        if isinstance(t, Number):
            self._timeline.set_pulse_end(self._timeline.current_time + t)
        else:
            for s in self.sequence_builders.values():
                s._add_reg_wait(t)

    def block_pulse(self, duration, sequencers, amplitudes, t_offset=0):
        self._timeline.disable_update()
        for s, a in zip(sequencers, amplitudes):
            if isinstance(s, str):
                s = self[s]
            s.block_pulse(duration, a, t_offset)
        self._timeline.enable_update()

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

