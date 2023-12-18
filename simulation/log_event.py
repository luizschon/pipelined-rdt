import json
from time import time_ns

# Event types
PKT_SENT = 1
ACK_SENT = 2
TIMEOUT = 3
CORRUPT = 4
DUP_ACK = 5
DUP_DATA = 6
OUT_OF_ORDER = 7
ACK_RECV = 8
DATA_RECV = 9

class Event:
    def __init__(self, type, seq, base, data):
        self.type = type
        self.data = data
        self.seq  = seq
        self.base = base
        self.time = time_ns()

    def export(self):
        return {
            'type': self.type,
            'time': self.time,
            'base': self.base,
            'seq': self.seq,
            'data': self.data,
        }

class Logger:
    events = []

    def __init__(self):
        pass

    def mark_event(self, type, base=0, seq=0, data=''):
        self.events.append(Event(type, seq, base, data))
