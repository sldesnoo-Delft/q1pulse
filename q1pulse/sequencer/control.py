import logging
import numpy as np

from .sequencer import SequenceBuilder
from .sequencer_data import Wave, WaveCollection
from q1pulse.lang.exceptions import Q1ValueError, Q1TypeError
from q1pulse.lang.math_expressions import Expression
from q1pulse.lang.register import Register
from q1pulse.lang.timed_statements import (
        SetMarkersStatement,
        AwgDcOffsetStatement, AwgGainStatement,
        ShiftPhaseStatement, SetPhaseStatement,
        ResetPhaseStatement,
        PlayWaveStatement, SetFrequencyStatement,
        )
from q1pulse.util.qblox_version import qblox_version, Version


logger = logging.getLogger(__name__)


class ControlBuilder(SequenceBuilder):
    def __init__(self, name, enabled_paths, max_output_voltage,
                 nco_frequency=None):
        super().__init__(name)
        self._enabled_paths = enabled_paths
        self.max_output_voltage = max_output_voltage
        self._nco_frequency = nco_frequency
        self._waves = WaveCollection()
        self._mixer_gain_ratio = None
        self._mixer_phase_offset_degree = None

    @property
    def enabled_paths(self):
        return self._enabled_paths

    @property
    def nco_frequency(self):
        return self._nco_frequency

    @nco_frequency.setter
    def nco_frequency(self, value):
        self._nco_frequency = value

    @property
    def mixer_gain_ratio(self):
        return self._mixer_gain_ratio

    @mixer_gain_ratio.setter
    def mixer_gain_ratio(self, value):
        self._mixer_gain_ratio = value

    @property
    def mixer_phase_offset_degree(self):
        return self._mixer_phase_offset_degree

    @mixer_phase_offset_degree.setter
    def mixer_phase_offset_degree(self, value):
        self._mixer_phase_offset_degree = value

    def add_wave(self, name, data):
        if np.any((data > 1.0) | (data < -1.0)):
            logger.error(f"Invalid data: {data}")
            raise Q1ValueError(
                f"channel {self.name} amplitude of wave {name} out of range: ({np.min(data), np.max(data)}")
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

    def set_frequency(self, frequency, t_offset=0):
        '''
        Args:
            frequency (float): nco frequency in Hz
        '''
        t1 = self.current_time + t_offset
        self.set_pulse_end(t1)
        self._add_statement(SetFrequencyStatement(t1, frequency))

    def reset_phase(self, t_offset=0):
        t1 = self.current_time + t_offset
        self.set_pulse_end(t1)
        self._add_statement(ResetPhaseStatement(t1))

    def shift_phase(self, delta, t_offset=0, hires_reg=True):
        '''
        Args:
            hires_reg:
                Convert register to exactly phase if True, else
                convert register value with relative error of 2e-4.

        NOTE:
            When `phase` is a Register many instructions are added for the
            conversion of the `phase` This costs ~188 ns when hires_reg=False.
            When hires_reg=True this costs ~268 ns.

            When `phase` is a constant in q1asm, then the resolution is 1e-9.
            No extra time is needed.
        '''
        t1 = self.current_time + t_offset
        self.set_pulse_end(t1)

        if qblox_version < Version('0.16.0'):
            # WORKAROUND: Qblox sequencer inverts phase delta when frequency is negative
            if self._nco_frequency and self._nco_frequency < 0:
                delta = -delta
        self._add_statement(ShiftPhaseStatement(t1, delta, hires_reg))

    def set_phase(self, phase, t_offset=0, hires_reg=True):
        '''
        Args:
            hires_reg:
                Convert register to exactly phase if True, else
                convert register value with relative error of 2e-4.

        NOTE:
            When `phase` is a Register many instructions are added for the
            conversion of the `phase` This costs ~188 ns when hires_reg=False.
            When hires_reg=True this costs ~268 ns.
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

    def shaped_pulse(self, wave0, amplitude0=None, wave1=None, amplitude1=None, t_offset=0):
        '''
        When amplitude is None, it is assumed that the gain has already been set to
        the right value.
        '''
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
            if amplitude0 is not None:
                self.set_gain(amplitude0, amplitude1)
            self.play(wave0, wave1)
            self.wait(duration)

    def ramp(self, duration, v_start, v_end, v_after=0.0, t_offset=0):
        if isinstance(duration, (Register, Expression)):
            raise Q1TypeError('Ramp duration cannot be a variable or expression; '
                              'Unroll loop using Python for-loop.')

        ramp_loop_time = 100 # @@@ make argument with default.
        self.add_comment(f'ramp({duration}, {v_start}, {v_end})')
        with self._local_timeline(t_offset=t_offset, duration=duration):
            if duration <= ramp_loop_time:
                # w_ramp is a wave from 0 to 1.0
                w_ramp = self._waves.get_ramp(duration)
                self.set_gain(v_end - v_start)
                self.set_offset(v_start)
                self.play(w_ramp)
                self.wait(duration)
            elif (isinstance(v_start, (Register, Expression))
                  or isinstance(v_end, (Register, Expression))):
                # divide duration till smallest multiple of 4 larger than or equal to 100
                shift = 0
                wave_duration = duration
                while wave_duration > 200 and wave_duration % 8 == 0:
                    wave_duration >>= 1
                    shift += 1
                self.Rs._ramp_step = (v_end - v_start)
                if shift >= 1:
                    self.Rs._ramp_step >>= shift
                # w_ramp is a wave from 0 to 1.0
                w_ramp = self._waves.get_ramp(wave_duration)
                self.Rs._ramp_offset = v_start
                self.set_gain(self.Rs._ramp_step)
                with self._seq_repeat(1 << shift):
                    self.set_offset(self.Rs._ramp_offset)
                    self.play(w_ramp)
                    self.Rs._ramp_offset += self.Rs._ramp_step
                    self.wait(wave_duration)
            else:
                step = (v_end - v_start) * ramp_loop_time / duration
                # step is a fixed point value in q1asm.  Resolution is 1/65536 of LSB output.
                lsb = 1/(2**15)
                if abs(step) > lsb:
                    gain = step
                    min_lsb_steps = 2**6
                    if abs(step) < lsb*min_lsb_steps:
                        # decrease ramp, increase gain for better accuracy
                        w_ramp = self._waves.get_ramp(ramp_loop_time, stop=1/min_lsb_steps)
                        gain = step * min_lsb_steps
                    else:
                        w_ramp = self._waves.get_ramp(ramp_loop_time)
                    # divmod, but with rem [1,100], and n > 1
                    n, rem = divmod(duration-1, ramp_loop_time)
                    #  @@@if n <= (5 if rem > 0 else 6): unroll loop!

                    rem += 1
                    self.Rs._ramp_offset = v_start
                    self.set_gain(gain)
                    with self._seq_repeat(n):
                        self.set_offset(self.Rs._ramp_offset)
                        self.play(w_ramp)
                        self.Rs._ramp_offset += step
                        self.wait(ramp_loop_time)
                    # @@@ do no use register
                    self.set_offset(self.Rs._ramp_offset)
                    self.play(w_ramp)
                    self.wait(rem)
                    self.set_gain(0.0)
                else:
                    # steps of 1 LSB
                    min_step = lsb
                    n_steps = int(abs(v_end - v_start) / min_step)
                    if n_steps == 0:
                        n = 0
                        rem = duration
                    else:
                        # minimum time multiple of 4 ns
                        t_step = int(duration / n_steps)
                        t_step = int(t_step / 4) * 4
                        # divmod, but with rem [1,100]
                        n, rem = divmod(duration-1, t_step)
                        rem += 1
                        step = (v_end - v_start) * t_step / duration
                    self.Rs._ramp_offset = v_start
                    if n > 0:
                        with self._seq_repeat(n):
                            self.set_offset(self.Rs._ramp_offset)
                            self.Rs._ramp_offset += step
                            self.wait(t_step)
                    self.set_offset(self.Rs._ramp_offset)
                    self.wait(rem)

            if v_after is not None:
                # set constant value
                self.set_offset(v_after)
            else:
                # assume there will be another instruction setting offset
                pass

    def chirp(self, duration, amplitude, f_start, f_end, t_offset=0):
        if isinstance(duration, (Register, Expression)):
            raise Q1TypeError('Chirp duration cannot be a variable or expression; '
                              'Unroll loop using Python for-loop.')
        if (isinstance(f_start, (Register, Expression))
                or isinstance(f_end, (Register, Expression))):
            raise Q1TypeError('Chirp frequency cannot be a variable or expression; '
                              'Unroll loop using Python for-loop.')

        chirp_loop_time = 100
        f_start = round(f_start)
        f_end = round(f_end)
        if f_start * f_end <= 0:
            raise Q1ValueError('Chirping through f=0.0 Hz is currently not possible')

        self.add_comment(f'chirp({duration}, {amplitude}, {f_start/1e6:7.3f}, {f_end/1e6:7.3f} MHz)')
        with self._local_timeline(t_offset=t_offset, duration=duration):
            f_step = (f_end - f_start) * chirp_loop_time / duration
            # Note: For the loop we need an integer frequency step. This could add a small
            # error of 0.5 Hz per iteration of the loop.
            # The maximum errror for a 10 ms chirp (100_000 iterations) is 0.05 MHz.
            # TODO: for more precision: add f_step fraction (use 64 bit numbers?)
            f_step = round(f_step)
            w_chirpI, w_chirpQ, delta_phase = self._waves.get_chirp(chirp_loop_time, f_step)
            # divmod, but with rem [1,100], and n > 1
            n, rem = divmod(duration-1, chirp_loop_time)
            rem += 1

            # TODO: remove workaround when fixed in firmware
            # Temporarily set NCO frequency for phase shift workaround.
            nco_freq = self.nco_frequency
            self.nco_frequency = f_start

            self.Rs._freq = int(f_start)
            self.set_gain(amplitude, amplitude)
            if n > 0:
                with self._seq_repeat(n):
                    self.shift_phase(delta_phase)
                    self.set_frequency(self.Rs._freq)
                    self.play(w_chirpI, w_chirpQ)
                    self.Rs._freq += f_step
                    self.wait(chirp_loop_time)
            self.shift_phase(delta_phase)
            self.set_frequency(self.Rs._freq)
            self.play(w_chirpI, w_chirpQ)
            self.wait(rem)
            self.set_gain(0.0)
            self.nco_frequency = nco_freq

    def _apply_paths(self, arg0, arg1):
        paths = self._enabled_paths
        if len(paths) == 0:
            raise Q1ValueError('No output paths enabled')

        if len(paths) == 1:
            path = paths[0]
            if arg1 is None:
                return (arg0, None) if path == 0 else (None, arg0)
            else:
                if path == 1:
                    # NOTE:
                    # if 1 path is enabled and 2 arguments are passed, then
                    # IQ should be rotated over pi/2, i.e. multiplied with [[0, 1], [-1, 0]]
                    # This rotation is applied to gain and offset.
                    # The amplitude of the waveform is multiplied by the gain.
                    # The waveforms only have to be swapped.
                    if isinstance(arg1, Wave):
                        return (arg1, arg0)
                    else:
                        return (-arg1, arg0)
                return (arg0, arg1)

        if paths[0] > paths[1]:
            if arg1 is None or isinstance(arg1, Wave):
                return (arg1, arg0)
            else:
                return (-arg1, arg0)

        return (arg0, arg1)

    def _translate_wave(self, wave):
        if wave is None:
            return None
        if isinstance(wave, str):
            return self._waves[wave]
        if isinstance(wave, Wave):
            return wave
        raise Q1TypeError(f'Illegal type {wave}')
