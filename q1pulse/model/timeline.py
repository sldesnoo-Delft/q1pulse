
class Timeline:
    def __init__(self):
        self._current_time = 0
        self._end_time = 0
        self._disabled = 0

    def disable_update(self):
        self._disabled += 1

    def enable_update(self):
        if not self._disabled:
            raise Exception('Cannot enable updates if not disabled')
        self._disabled -= 1
        if not self._disabled:
            self._current_time = self._end_time

    @property
    def is_running(self):
        return not self._disabled

    @property
    def current_time(self):
        return self._current_time

    def set_pulse_end(self, value):
        if not self._disabled:
            self._current_time = value
        self._end_time = max(value, self._current_time)

    @property
    def end_time(self):
        return self._end_time

    def reset(self):
        self._current_time = 0
        self._end_time = 0
        self._disabled = 0
