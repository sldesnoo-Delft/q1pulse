from .sequencer import SequenceBuilder
from .sequencer_data import Wave, WaveCollection
from ..lang.exceptions import Q1ValueError, Q1TypeError
from ..lang.math_expressions import Expression
from ..lang.register import Register
from ..lang.timed_statements import (
        SetMarkersStatement,
        AwgDcOffsetStatement, AwgGainStatement,
        ShiftPhaseStatement, SetPhaseStatement,
        PlayWaveStatement
        )


class ControlBuilder(SequenceBuilder):
    def __init__(self, name, enabled_paths, max_output_voltage,
                 nco_frequency=None):
        super().__init__(name)
        self._enabled_paths = enabled_paths
        self.max_output_voltage = max_output_voltage
        self._nco_frequency = nco_frequency
        self._waves = WaveCollection()

    def add_wave(self, name, data):
        return self._waves.add_wave(name, data)

    def set_markers(self, value, t_offset=0):
        t1 = self.current_time + t_offset
        self.set_pulse_end(t1)
        self._add_statement(SetMarkersStatement(t1, value))

    def set_offset(self, value0, value1=None, t_offset=0):
        value0, value1 = self._apply_paths(value0, value1)
        t1 = self.current_time + t_offset
        self.set_pulse_end(t1)
        self._add_statement(AwgDcOffsetStatement(t1, value0, value1))

    def set_gain(self, value0, value1=None, t_offset=0):
        value0, value1 = self._apply_paths(value0, value1)
        t1 = self.current_time + t_offset
        self.set_pulse_end(t1)
        self._add_statement(AwgGainStatement(t1, value0, value1))

    def play(self, wave0, wave1=None, t_offset=0):
        wave0, wave1 = self._apply_paths(wave0, wave1)
        t1 = self.current_time + t_offset
        self.set_pulse_end(t1)
        wave0 = self._translate_wave(wave0)
        wave1 = self._translate_wave(wave1)
        self._add_statement(PlayWaveStatement(t1, wave0, wave1))

    def shift_phase(self, delta, t_offset=0, hires_reg=False):
        '''
        Args:
            hires_reg:
                If then and `phase` is a Register, use 2 registers for
                conversion of phase, i.e. resolution = 1/(400*400)

        NOTE:
            When `phase` is a Register many instructions are added for the
            conversion of the `phase` This costs ~150 ns when hires_reg=False.
            When hires_reg=True this costs ~500 ns.

            When `phase` is a constant in q1asm, then the resolution is 1e-9.
            No extra time is needed.
        '''
        t1 = self.current_time + t_offset
        self.set_pulse_end(t1)
        self._add_statement(ShiftPhaseStatement(t1, delta, hires_reg))

    def set_phase(self, phase, t_offset=0, hires_reg=False):
        '''
        Args:
            hires_reg:
                If then and `phase` is a Register, use 2 registers for
                conversion of phase, i.e. resolution = 1/(400*400)

        NOTE:
            hires_reg adds many instructions. Execution costs ~500 ns.
            When `phase` is a Register the conversion costs ~ 50 ns.
        '''
        t1 = self.current_time + t_offset
        self.set_pulse_end(t1)
        self._add_statement(SetPhaseStatement(t1, phase, hires_reg))

    def block_pulse(self, duration, amplitude0, amplitude1=None, t_offset=0):
        self.add_comment(f'block_pulse({duration}, {amplitude0}, {amplitude1})')
        if not isinstance(duration, (Register, Expression)):
            with self._local_timeline(t_offset=t_offset, duration=duration):
                self.set_offset(amplitude0, amplitude1)
                self.wait(duration)
                self.set_offset(0.0, None)
        else:
            # TODO: try to make this cleaner and more flexible.
            if not self._timeline.is_running:
                raise Q1ValueError('Variable pulse length not possible in parallel section')
            self.set_offset(amplitude0, amplitude1)
            self._program.wait(duration)
            self.set_offset(0.0, None)

    def shaped_pulse(self, wave0, amplitude0, wave1=None, amplitude1=None, t_offset=0):
        wave0 = self._translate_wave(wave0)
        wave1 = self._translate_wave(wave1)
        wave0_name = wave0.name if wave0 is not None else None
        wave1_name = wave1.name if wave1 is not None else None
        self.add_comment(f'shaped_pulse({wave0_name}, {amplitude0}, {wave1_name}, {amplitude1})')

        duration = max(
                len(wave0.data) if wave0 is not None else 0,
                len(wave1.data) if wave1 is not None else 0
                )
        with self._local_timeline(t_offset=t_offset, duration=duration):
            self.set_gain(amplitude0, amplitude1)
            self.play(wave0, wave1)
            self.wait(duration)
            self.set_gain(0.0, None)

    def ramp(self, duration, v_start, v_end, v_after=0.0, t_offset=0):
        if isinstance(duration, (Register, Expression)):
            raise Q1TypeError('Ramp duration cannot be a variable or expression; '
                              'Unroll loop using Python for-loop.')

        self.add_comment(f'ramp({duration}, {v_start}, {v_end})')
        with self._local_timeline(t_offset=t_offset, duration=duration):
            # w_ramp is a wave from 0 to 1.0
            if duration <= 100:
                w_ramp = self._waves.get_ramp(duration)
                self.set_gain(v_end - v_start)
                self.set_offset(v_start)
                self.play(w_ramp)
                self.wait(duration)
            elif (isinstance(v_start, (Register, Expression))
                  or isinstance(v_end, (Register, Expression))):
                # divide duration till smallest multiple of 4 larger than or equal to 200
                shift = 0
                wave_duration = duration
                while wave_duration > 200 and wave_duration % 8 == 0:
                    wave_duration >>=1
                    shift += 1
                self.Rs._ramp_step = (v_end - v_start)
                if shift >= 1:
                    self.Rs._ramp_step >>= shift
                w_ramp = self._waves.get_ramp(wave_duration)
                self.Rs._ramp_offset = v_start
                self.set_gain(self.Rs._ramp_step)
                with self._seq_repeat(1 << shift):
                    self.set_offset(self.Rs._ramp_offset)
                    self.play(w_ramp)
                    self.Rs._ramp_offset += self.Rs._ramp_step
                    self.wait(wave_duration)
            else:
                step = (v_end - v_start) * 100 / duration
                # step is a fixed point value in q1asm.  Resolution is 1/65536 of LSB output.
                # Gain range: -1/32768 ... +1/32768
                if abs(step) > 1/(2**15):
                    # divmod, but with rem [1,100], and n > 1
                    n, rem = divmod(duration-1, 100)
                    rem += 1
                    w_ramp = self._waves.get_ramp(100)
                    self.Rs._ramp_offset = v_start

                    self.set_gain(step)
                    with self._seq_repeat(n):
                        self.set_offset(self.Rs._ramp_offset)
                        self.play(w_ramp)
                        self.Rs._ramp_offset += step
                        self.wait(100)
                    self.set_offset(self.Rs._ramp_offset)
                    self.play(w_ramp)
                    self.wait(rem)
                else:
                    # steps of 1 LSB
                    min_step = 1/(2**16)
                    n_steps = int(abs(v_end - v_start) / min_step)
                    # minimum time multiple of 4 ns
                    t_step = int(duration / n_steps)
                    t_step = int(t_step / 4) * 4
                    # divmod, but with rem [1,100], and n > 1
                    n, rem = divmod(duration-1, t_step)
                    rem += 1
                    step = (v_end - v_start) * t_step / duration
                    self.Rs._ramp_offset = v_start
                    with self._seq_repeat(n):
                        self.set_offset(self.Rs._ramp_offset)
                        self.Rs._ramp_offset += step
                        self.wait(t_step)
                    self.set_offset(self.Rs._ramp_offset)
                    self.wait(rem)

            if v_after is not None:
                # set constant value
                self.set_offset(v_after)
                self.set_gain(0.0)
            else:
                # assume there will be another instruction setting offset and gain.
                pass

    def _apply_paths(self, arg0, arg1):
        if len(self._enabled_paths) == 0:
            raise Q1ValueError('No output paths enabled')

        if len(self._enabled_paths) == 1:
            path = self._enabled_paths[0]
            if arg1 is not None:
                raise Q1ValueError('Only 1 output path enabled')

            return (arg0, None) if path == 0 else (None, arg0)

        # channels could be swapped
        args = (arg0, arg1)
        return (args[i] for i in self._enabled_paths)

    def _translate_wave(self, wave):
        if wave is None:
            return None
        if isinstance(wave, str):
            return self._waves[wave]
        if isinstance(wave, Wave):
            return wave
        raise Q1TypeError(f'Illegal type {wave}')

