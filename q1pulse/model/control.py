from .math_expressions import Expression
from .register import Register
from .sequence import SequenceBuilder
from .timed_statements import (
        AwgDcOffsetStatement, AwgGainStatement,
        ShiftPhaseStatement, SetPhaseStatement,
        PlayWaveStatement
        )
from .loops import loopable
from .sequencer_data import Wave


# @@@ DC vs IQ ??


class ControlBuilder(SequenceBuilder):
    def __init__(self, name, enabled_paths, nco_frequency=None):
        super().__init__(name)
        self._enabled_paths = enabled_paths
        self._nco_frequency = nco_frequency

    @loopable
    def set_offset(self, value0, value1=None, t_offset=0):
        value0, value1 = self._apply_paths(value0, value1)
        t1 = self.current_time + t_offset
        self._add_statement(AwgDcOffsetStatement(t1, value0, value1))

    @loopable
    def set_gain(self, value0, value1=None, t_offset=0):
        value0, value1 = self._apply_paths(value0, value1)
        t1 = self.current_time + t_offset
        self._add_statement(AwgGainStatement(t1, value0, value1))

    @loopable
    def play(self, wave0, wave1=None, t_offset=0):
        wave0, wave1 = self._apply_paths(wave0, wave1)
        t1 = self.current_time + t_offset
        wave0 = self._translate_wave(wave0)
        wave1 = self._translate_wave(wave1)
        self._add_statement(PlayWaveStatement(t1, wave0, wave1))

    @loopable
    def shift_phase(self, delta, t_offset=0, hires_regs=False):
        t1 = self.current_time + t_offset
        self._add_statement(ShiftPhaseStatement(t1, delta, hires_regs))

    @loopable
    def set_phase(self, phase, t_offset=0, hires_regs=False):
        t1 = self.current_time + t_offset
        self._add_statement(SetPhaseStatement(t1, phase, hires_regs))

    @loopable
    def block_pulse(self, duration, amplitude, amplitude2=None, t_offset=0):
        if not isinstance(duration, (Register, Expression)):
            with self._local_timeline(t_offset=t_offset, duration=duration):
                self._add_statement(AwgDcOffsetStatement(self.current_time, amplitude, amplitude2))
                self.wait(duration)
                self._add_statement(AwgDcOffsetStatement(self.current_time, 0.0, 0.0))
        else:
            # TODO: try to make this cleaner and more flexible.
            if not self._timeline.is_running:
                raise Exception('Variable pulse length not possible in parallel section')
            self._add_statement(AwgDcOffsetStatement(self.current_time, amplitude, amplitude2))
            self._program.wait(duration)
            self._add_statement(AwgDcOffsetStatement(self.current_time, 0.0, 0.0))


#    @loopable
    # TODO @@@ can v_start/v_end be registers? only if they are managed loopvars. Introduce additional f-register
    # for variable duration: unroll!
    def ramp(self, duration, v_start, v_end, t_offset=0):
        with self._local_timeline(t_offset=t_offset, duration=duration):
            # w_ramp is a wave from 0 to 1.0
            self.set_offset(v_start)
            if duration <= 100:
                w_ramp = self._waves.get_ramp(duration)
                self.set_gain(1.0)
                self.play(w_ramp)
                self.wait(duration)
                self.set_offset(v_end)
                self.set_gain(0.0)
            else:
                # divmod, but with rem [1,100], and n > 1
                n, rem = divmod(duration-1, 100)
                rem += 1
                w_ramp = self._waves.get_ramp(100)
                self.Rs._ramp_offset = v_start
                # increment is a fixed point value.
                # Note: rounding errors become significant when n > 10000, i.e. 1 ms.
                increment = (v_end - v_start) / n

                gain = (v_end - v_start) * 100 / duration
                self.set_gain(gain)
                self.play(w_ramp)
                with self._seq_repeat(n):
                    self.Rs._ramp_offset += increment
                    self.wait(100)
                    self.set_offset(self.Rs._ramp_offset)
                    self.play(w_ramp)

                self.wait(rem)
                self.set_offset(v_end)
                self.set_gain(0.0)

    def _apply_paths(self, arg0, arg1):
        if len(self._enabled_paths) == 0:
            raise Exception('No output paths enabled')

        args = (arg0, arg1)
        if len(self._enabled_paths) == 1:
            path = self._enabled_paths[0]
            if arg1 is not None:
                raise Exception('Only 1 output path enabled')

            return (arg0, None) if path == 0 else (None, arg0)

        # channels could be swapped
        return (args[i] for i in self._enabled_paths)

    def _translate_wave(self, wave):
        if wave is None:
            return None
        if isinstance(wave, str):
            return self._waves[wave]
        if isinstance(wave, Wave):
            return wave
        raise Exception(f'Illegal type {wave}')

