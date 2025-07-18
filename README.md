# Q1Pulse
Pulse sequence builder and compiler for Q1ASM.
Q1Pulse is a simple library to compile pulse sequence to Q1ASM, the assembly language of Qblox instruments.
Q1Pulse supports loops, variables and expressions that are translated to Q1ASM.


This project has several goals:
- create a driver to use in the backend of [pulse_lib](https://github.com/stephanlphilips/pulse_lib)
- provide a very simple API to test QCM and QRM
- explore the possibilities of Q1ASM and the QCM and QRM
- have fun with building a compiler for Q1ASM.

Q1Pulse uses a generic language independent of Q1ASM and the constraints of its instruction set.
As a consequence the compiler will have to generate multiple Q1ASM instructions for some Q1Pulse statements.
- Floating point operations are emulated with a fixed point representation.
- Signed integer comparisons are emulated.
- Additional (looped) wait instructions are inserted when a wait time is too long for one instruction.
- Update parameter instructions are inserted only when required.
- NOP instruction are inserted to wait a cycle for a register being updated.
- Temporary registers are used for immediate values when the instruction does not support immediate operand.

Q1Pulse is inspired on [pulse_lib](https://github.com/stephanlphilips/pulse_lib).
The following features of pulse_lib are **not** available in Q1Pulse:
- Virtual matrix for compensation of capacitive coupling of device gates.
- Channel delay compensation.
- Compensation for attenuators on output.
- DC compensation to discharge bias-T.
- Bias-T compensation to compensate for high-pass filter.
These features will be handled by pulse_lib when Q1Pulse is used as pulse_lib backend.

The functionality of Q1Pulse can be tested and explored with
[Q1Simulator](https://github.com/sldesnoo-Delft/q1simulator), a simulator of Q1ASM.

# Q1Pulse API
A Q1Pulse program is written in Python using the Q1Pulse API.
A program consists of instructions like pulses, wait statements, loops and acquisitions
for the QCM and QRM sequencers. An instruction can apply to 1 or more sequencers.
All instructions are executed in sequential order, unless otherwise specified in
a "parallel section". The instruction sequence is synchronized across all the sequencers.

## Program and sequences
A program is created for a Q1Instrument. The instrument definition contains the definition
of the sequencers and their mapping to the output and input channels of the modules.
A program has a sequence for every configured sequencer.
The individual sequences can be accessed via an attribute of the program object or as an index
of the program object.

Every instruction advances the time of all sequencers, unless otherwise specified.
Instructions added to the Program object apply to multiple sequencers simultaneously.
Instructions added to a sequence only affect the timing of the other sequences.

A program can have a **parallel section**. In a parallel section the program time does
**not** advance. So, instructions can be scheduled to overlap. After the parallel section
the time is set after the end of all the instructions in the parallel section.

### Example program and sequences
This simple program shows the use of program object and sequence objects.
```python
    qcm1 = cluster.module1
    qrm2 = cluster.module2

    instrument = Q1Instrument('cluster1')
    instrument.add_qcm(qcm1)
    instrument.add_qrm(qrm2)
    # create named control and readout channels
    instrument.add_control('P1', qcm1.name, [0])
    instrument.add_control('P2', qcm1.name, [1])
    instrument.add_readout('R1', qrm2.name, [], in_channels=[0,1])

    p = instrument.new_program('ramp')

    # sequencer P1
    P1 = p.P1
    # sequencer P2 using indexer
    P2 = p['P2']
    # sequencer R1 (readout)
    R1 = p.R1

    R1.add_acquisition_bins('default', 100)
    # 60 ns acquisition
    R1.integration_length_acq = 60

    # generate a block pulse of 20 ns and amplitude 0.5 on P1
    P1.block_pulse(20, 0.5)
    # After that generate a block pulse of 100 ns and amplitude -0.25 on P2
    P2.block_pulse(100, -0.25)
    # Wait 40 ns after last pulse
    p.wait(40)
    # generate pulse of 200 ns on P1 and P2 simultaneously with amplitudes 0.5 and -0.5
    p.block_pulse(200, [P1, P2], [0.5, -0.5])

    # simultaneous pulses using parallel section:
    # - a block pulse on P1
    # - an overlapping ramp on P2 with an offset of 20 ns
    # - acquisition on R1 starts immediately with parallel section (no offset)
    # - wait(100) has latest end time and determines total duration of section.
    with p.parallel():
        P1.block_pulse(40, -0.1)
        # ramp from 0.05 to 0.4 in 60 ns. Start 20 ns after begin of parallel section
        P2.ramp(60, 0.05, 0.40, t_offset=20)
        R1.acquire('default', 'increment')
        p.wait(100)

    p.repetitions = 100
    p.compile(listing=True, annotate=True)

    instrument.run_program(p)

    data = instrument.get_acquisition_bins('R1', 'default')
```

### Output channels and sequencer instructions
Sequencers can be configured to control 1 or 2 outputs.
Sequencers controlling 1 output will most likely be used to directly control a voltage on the target device.
Sequencers controlling 2 outputs will most likely be used for the generation of RF signals.
Some instructions intended for voltage control, e.g. ramp, will fail on sequencers controlling 2 output
channels.

## Q1Pulse instructions

### Instruction arguments: floating point and nanoseconds
The arguments that specify an amplitude, offset, gain or phase are all specified as
floating point values in the range \[-1.0, 1.0\]. For amplitude and gain the actual value
has to be multiplied with the voltage range of the output channel. The value of the phase
is in units of PI.
The time in instructions is always specified in nanoseconds.

### Program instructions
Program flow and timing instructions:
- wait(t): wait t ns
- loop_range, loop_linspace
- parallel: starts parallel section where time is not incremented automatically

Instructions for simultaneous execution on multiple sequencers where each sequencer is controlling only 1 output:
- block_pulse
- ramp (2)
- set_offsets (1)

Notes:
1. instruction does not advance time in sequence.
2. `ramp` voltage sweep is limited to 50% of full scale.


## QCM Sequence instructions
- add_wave: adds a wave to be used in shaped pulses
- add_comment: add a comment line in the Q1ASM
Basic instructions:
- set_markers (1)
- set_offset, set_gain (1)
- reset_phase, set_phase, shift_phase (1)
- set_frequency (1)
- play (1)
Composite instructions:
- block_pulse
- shaped_pulse
- ramp: creates ramp on 1 output (2)
- chirp: a linear sweep of the frequency (using IQ modulation)

Notes:
1. instruction does not advance time in sequence.
2. `ramp` voltage sweep is limited to 50% of full scale.

## QRM Sequence instructions
QRM can execute all QCM instructions.

QRM specific instructions:
- add_acquisition: add a (binned) acquisition specification
- add_acquisition_weights: add specification for weights
- reset_bin_counter: resets the automatic incrementing bin counter.
- acquire: acquire data, optionally incrementing the bin counter. (1)
- acquire_weighed: acquire data using weighed average, optionally incrementing the bin counter. (1)
- repeated_acquire: N times acquire data, optionally incrementing the bin counter.
- repeated_acquire_weighed: N times acquire data using weighed average, optionally incrementing the bin counter.

Notes:
1. instruction does not advance time in sequence.

## Variables and expressions
Programs can make use of variables that will be translated to Q1ASM registers.
Variables can be global to the program or local to a sequence.
Global variables can be created via the R attribute of the program object, `p.R.amplitude = 0.5`.
Sequence local variables can be created via the Rs attribute of a sequence object, `P1.Rs.t_wait = 200`.
Global variables can be used in program and sequence instructions.
Sequence local variables can only be used in sequence instructions.

### Variable types
The type of a variable can be either float or int. It is inferred on the first assignment and
cannot change within the program.
Internally the float variables are represented as 32 bit **fixed point** values in the range \[-1.0, 1.0].
Integers are 32 bit signed int, unless otherwise specified.
Where needed and as far as possible the compiler inserts additional Q1ASM instructions to emulate
signed int operations.

### Expressions
The following Python operations are supported: `+`, `-`, `<<`, `>>` and bitwise `&`, `|`, `~`.
Evaluation order is determined by the Python operator rules.
The (unsigned) logical shift right is available as function `lsr()`

Notes:
- The shift right operator does a **signed** arithmetic shift right, just like Python does.
  The signed shift is emulated.
- Python has no logical shift right. The function `lsr` is added for this purpose.
- There is no overflow checking on integer and fixed point operations.
  So, 1.0 + 0.5 gives -0.5.

Multiplication and division operators are not implemented, because the emulation with
Q1ASM would take too long to be practical. The emulated multiplication of two 32-bit values
would take more than 1 microsecond.

### Example

```python
    # integers:
    p.R.a = 0
    p.R.b = p.R.a + 1
    p.R.b = 5 + (p.R.a << 1)
    p.R.c = p.R.b + p.R.a
    p.R.c += 5
    p.R.d = 1 - p.R.a

    # floating point:
    p.R.f = 1.0
    p.R.f -= 0.1
    p.R.g = 0.5
    p.R.h = p.R.f - p.R.g

    # sequence variables:
    P1.Rs.x = 9
    P1.Rs.y = P1.Rs.x + p.R.b
    P1.Rs.amplitude = p.R.f - 0.2

    # use of variables and expressions in instruction arguments
    p.wait(p.R.c + 10)
    P1.block_pulse(p.R.d, P1.Rs.amplitude)
```
## Loops
Loops can be created on program level and will be executed on all sequences in parallel to
ensure synchronized execution of all sequences.
There are three types of loops.
- `loop_range` creates a loop in Q1ASM which is similar to `for i in range(...)`.
It uses the same  arguments as `range`.
- `loop_linspace` creates a loop in Q1ASM with a fixed point variable which is similar to `for x in numpy.linspace(...)`
It uses the same  arguments as `numpy.linspace`.
- `loop_array` creates a loop in Q1ASM iterating the values of the array. The array can contain
either integer or float values.
The loops should be used with a `with` statement. The statements return a global variable that can
be used as such.

### Example
```python
    # initialize, varying wait, readout.
    with p.loop_range(100, 1000, 10) as t_wait:
        p.block_pulse(200, gates, v_init)
        p.wait(t_wait)
        p.block_pulse(200, gates, v_readout)

    # create a staircase
    with p.loop_linspace(-0.5, 0.5, 20) as v1:
        P1.block_pulse(200, v1)
```

## Conditional statements

Statements can be executed conditionally on the result of acquisitions or triggers.

Triggers on acquisitions must be defined with
`trigger_x = program.configure_trigger(readout_sequencer_name, invert=False)`.
Acquisition threshold must be set on the sequence with
`seq.thresholded_acq_threshold = value`.
Trigger counters must be defined with on program or sequence with
`counter_x = program.add_trigger_counter(trigger_x, threshold=1, invert=False)`.

Conditional branches must be put in a conditional block. The conditional block
specifies which trigger counters are tested. One or more branches can be added
each with a condition on this set of trigger counters.
The conditions that can be checked are:
- at_least_one_set (OR): at least one of the trigger counters is set.
- none_set (NOR): none of the trigger counters is set.
- all_set (AND): all trigger counters are set.
- not_all_set (NAND): not all trigger counter are set.
- odd (XOR): an odd number of trigger counters is set.
- even (XNOR): an even number of trigger counters is set.

Only subsets of conditions can be used within a conditional block, because
the condition of exactly 1 branch must be true (including the automatically added
else-branch). Allowed combinations:
- with 1 trigger counter are:
  one of (OR, AND, XOR) + one of (NOR, NAND, XNOR)
- with 2 trigger counters:
  - OR + NOR, AND + NAND, or XOR + XNOR
  - AND + NOR + XOR. This is the only combination for 3 branches.
- with 3 or more trigger counters:
  - OR + NOR, AND + NAND, or XOR + XNOR

The duration of a condtional block is fixed. All branches will have equal duration.
Q1Pulse will add wait statements to enforce this equal duration.
This results in a predictable timeline for the program.

Some time is needed between the conditional block statement and the
first statement of any else-branch, because it takes time to skip the
statements of the previous branches.
Some time is also needed to skip the statements of subsequent branches.
This could result in some additional execution time for the block.

The latching of trigger by the trigger counters must be enabled on the
sequencer or on the whole program: `program.latch_enable(counters)`.
The counters are reset with `program.latch_reset()`.
Note that the latch_enable and latch_reset are real-time instructions
that take 4 ns to evaluate.

### Example

```python
    p = instrument.new_program('feedback')
    p.repetitions = 2

    trigger1 = p.configure_trigger('R1')
    counter1 = p.add_trigger_counter(trigger1)

    P1 = p.P1
    R1 = p.R1

    n_acq = p.repetitions
    R1.add_acquisition_bins('measurements', n_acq)
    R1.integration_length_acq = 100
    R1.thresholded_acq_threshold = 0.1

    # program
    R1.acquire('measurements')
    P1.latch_reset()
    p.wait(4)
    P1.latch_enable(\[counter1])
    p.wait(96)
    # 260 ns delay for trigger propagation
    p.wait(260)
    with P1.conditional(\[counter1], evaluation_time=20) as flags:
        with flags.all_set():
            P1.ramp(60, 0.25, 0.25)
        with flags.none_set():
            P1.ramp(60, 0.25, 0.0)
```

## Instrument

```python
    instrument = Q1Instrument()
    instrument.add_qcm(qcm0)
    instrument.add_qrm(qrm1)
    # add sequencers with output channels
    instrument.add_control('q1', qcm0.name, \[0,1])
    instrument.add_control('P1', qcm0.name, \[2])
    instrument.add_control('P2', qcm0.name, \[3])
    instrument.add_readout('R1', qrm1.name, \[1])

    p = instrument.new_program('my_q1_program')
```

## Logging with Q1Simulator
The `log` command can be used in combinator with [Q1Simulator](https://github.com/sldesnoo-Delft/q1simulator).
This will output log messages on the console and can be useful when debugging the code.
The log instruction is added in a comment line and will be ignored by the Pulsar.

```python
    with p.loop_array([0.1, -0.2, 0.3, -0.4, 0.5, -0.6, 0.7]) as v:
        P2.log('amplitude', v, time=True)
        P2.block_pulse(80, v)
```
output:
```
    amplitude:  0.100000 (0CCCCCCC) q1:  -148 rt:   244 ns
    amplitude: -0.200000 (E6666666) q1:   -56 rt:   324 ns
    ...
```
Note: the q1 core has a head start of 200 ns. It starts at t = -200 ns.
This accounts for the time the real-time executor waits in wait_sync.


