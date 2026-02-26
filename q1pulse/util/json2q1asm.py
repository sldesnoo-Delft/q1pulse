import json
import os
from pprint import pprint

import numpy as np


def json2q1asm(filename: str):
    """Reformats a json file with Q1ASM sequence to a .q1asm file.

    A .q1asm file uses Python syntax to present the sequence in a readable format.
    The text can be copied to a Python script.
    """
    with open(filename) as fp:
        sequence = json.load(fp)

    if filename.endswith(".json"):
        q1asm_filename = filename[:-4] + "q1asm"
    else:
        q1asm_filename = filename + ".q1asm"

    with open(q1asm_filename, "w") as fp:
        _write_prog_and_data_txt(sequence, fp)


def _write_prog_and_data_txt(sequence, f):
    if waveforms := sequence.get('waveforms'):
        f.write('waveforms=')
        _pprint_data(waveforms, f)
    if weights := sequence.get('weights'):
        f.write('weights=')
        _pprint_data(weights, f)
    if acquisitions := sequence.get('acquisitions'):
        f.write('acquisitions=')
        pprint(acquisitions, f)
    f.write('\n')
    f.write('seq_prog="""\n')
    _pprint_q1asm_prog(sequence['program'], f)
    f.write('\n"""\n\n')


def _pprint_data(data_dict, f):
    prefix = ' '*12
    f.write('{\n')
    for name, wave in data_dict.items():
        f.write(f"    '{name}':{{\n")
        f.write(f"        'data':\n")
        f.write(prefix)
        # precision of 5 digits is sufficient for 16 bit numbers in range [-1, +1]
        f.write(np.array2string(np.array(wave['data']),
                                prefix=prefix,
                                separator=',',
                                formatter={'float_kind': lambda x: f'{x:9.5f}'},
                                threshold=1000_000))
        f.write(f",\n")
        f.write(f"        'index':{wave['index']},\n")
        f.write(f'        }},\n')
    f.write('    }\n\n')


def _pprint_q1asm_prog(program: str, f):
    lines = program.splitlines()
    for lineno, line in enumerate(lines, 1):
        if ":" in line:
            label, line = line.split(":")
            label = label + ":"
        else:
            label = ""
        line.strip(" ")
        f.write(f"{label:10} {line:40} #{lineno:04d}\n")
