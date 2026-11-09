from dataclasses import dataclass


@dataclass
class Trigger:
    sequencer_name: str
    address: int
    ''' range: 1 to 15 '''
    invert: bool = False

@dataclass
class TriggerCounter:
    trigger: Trigger
    threshold: int
    invert: bool = False

    @property
    def address(self):
        return self.trigger.address

    @property
    def name(self):
        return self.trigger.sequencer_name

