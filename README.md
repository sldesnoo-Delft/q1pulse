#q1pulse
Pulse sequence builder and compiler for q1asm. 
q1pulse is a simple library to compile pulse sequence to q1asm, the assembly language of Qblox instruments.
It purpose is to provide a very simple API and at the same time explore the possibilities of q1asm and the QCM adn QRM.

q1pulse is inspired on pulse_lib: https://github.com/stephanlphilips/pulse_lib


Python API.
Generates statement tree with timing information

instrument.add_control:
* 1 or 2 channels

instrument.add_readout

Timeline:
* parallel
* wait

Program:
* wait
* block_pulse, ramp

Pulses:
* block_pulse
* ramp

Loops:
loop_linspace -> loop_var
loop(n), loop(start, stop[, step]) -> loop_var
repeat(n)

Registers and Expressions.
Floating point values for RT settings: awg_offset, awg_gain.

Function arguments can be constant, register of expression.
* wait(reg)
# not yet for ramp args


Loops and expression evaluation allocate temporary registers.
These registers are freed after the scope of the loop and expression.

Floating point:
