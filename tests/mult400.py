# -*- coding: utf-8 -*-
"""
Created on Wed Nov 10 15:46:59 2021

@author: sdesnoo
"""
import math
import numpy as np

def phase2num(value):
    R0 = math.floor(value * ((1<<31)-0.1)) & 0xFFFF_FFFF
#    print(f'R0:{R0:032b}')
    # -1.0 ... +1.0 => 200 ... 399; 0 ... 199
    # multiply with 200; After shifting it is already unsigned 0 ... 2.0/

    # multiply with 200:
    # shift N bits right to create space for multiplication
    # R1 = R0 >> N
    # R2 = 400*R1 => R2 = 16*R1 + 128*R1 + 256*R1
    # Thus R2 = (R0 >> (N-4)) + (R0 >> (N-7)) + (R0 >> (N-8))
    # use R1 as temp reg, accumulate in R2
    N = 10
    R2 = R0 >> (N-4)
    R1 = R0 >> (N-7)
#    print(f'R0:{R0:032b}, R1:{R1:032b}, R2:{R2:032b}')
    R2 += R1
    R1 = R0 >> (N-8)
    R2 += R1
    R2 += 1<<10
    # finally shift R2 32-N bits, keep remainder in R3
    R3 = (R2 << N) & 0xFFFF_FFFF
#    print(f'R0:{R0:032b}, R1:{R1:032b}, R2:{R2:032b}')
    R2 = R2 >> (32-N)

    return R2, R3


def phase2num2(value):
    R0 = math.floor(value * ((1<<31)-0.1)) & 0xFFFF_FFFF
#    print(f'R0:{R0:032b}')
    # -1.0 ... +1.0 => 200 ... 399; 0 ... 199
    # multiply with 200; After shifting it is already unsigned 0 ... 2.0/

    # multiply with 200:
    # shift N bits right to create space for multiplication
    # R1 = R0 >> N
    # R2 = 25*R1 => R2 = 16*R1 + 128*R1 + 256*R1
    # Thus R2 = (R0 >> (N-4)) + (R0 >> (N-7)) + (R0 >> (N-8))
    # use R1 as temp reg, accumulate in R2
    N = 9
    R2 = R0 >> (N-4)
    R1 = R0 >> (N-7)
#    print(f'R0:{R0:032b}, R1:{R1:032b}, R2:{R2:032b}')
    R2 += R1
    R1 = R0 >> (N-8)
    R2 += R1
    # add before rounding, max 1<<10
    R2 += 3#1<<2
    R2 &= 0xFFFF_FFFF
    # finally shift R2 32-N bits, keep remainder in R3
    R3 = (R2 << N) & 0xFFFF_FFFF
#    print(f'R0:{R0:032b}, R1:{R1:032b}, R2:{R2:032b}')
    R2 = R2 >> (32-N)

    # Same R4 = 400 * R3
    R4 = R3 >> (N-4)
    R1 = R3 >> (N-7)
#    print(f'R0:{R0:032b}, R1:{R1:032b}, R2:{R2:032b}')
    R4 += R1
    R1 = R3 >> (N-8)
    R4 += R1
    R4 += 3# 1<<2
    R4 &= 0xFFFF_FFFF
    # finally shift R2 32-N bits, keep remainder in R5
    R5 = (R4 << N) & 0xFFFF_FFFF
#    print(f'R0:{R0:032b}, R1:{R1:032b}, R2:{R2:032b}')
    R4 = R4 >> (32-N)

    return R2, R4, R5

def get_numbers(i):
    n = int(round((i+2) * 5e8))
    n1,nr = divmod(n, 400*6250)
    n1 %= 400
    n2,n3 = divmod(nr, 6250)
    return n1,n2,n3


for i in np.linspace(-1.0, 1.0, 21, endpoint=True):
#for i in np.linspace(0.0, 0.1, 17, endpoint=False):
    n1,n2,nr2 = get_numbers(i)
#    print(f'{n:10} value:{n1:3}, value2:{n2:3}, r:{r2:6}')

#    value,r = phase2num(i)
##    print(f'{i:6.3f} n:{n1:3},{n2:3}, value:{value:3}      {r/2**32:8.6f} {nr/(400*6250):8.6f}')
#    value2,r2 = phase2num(r / 2**31)
    value,value2,r2 = phase2num2(i)
#    print(f'{i:6.3f} value:{value:3}, R2:{value:08b}, r:{r:032b}')
#    print(f'{i:6.3f} value2:{value2:3}, R2:{value2:08b}, r2:{r2:032b}')
    print(f'{i:6.3f} n: {n1:3},{n2:3}, value: {value:3},{value2:3}, {r2/2**32:8.6f} {r2/2**32*6250:3.0f}' +
          f' delta:{n1-value:3},{n2-value2:3}')
#    print()
