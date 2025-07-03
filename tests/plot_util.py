import matplotlib.pyplot as pt


def plot_output(instruments):
    for instrument in instruments:
        if hasattr(instrument, 'plot'):
            pt.figure()
            pt.title(instrument.name)
            instrument.plot()
            pt.legend()
            pt.grid(True)
