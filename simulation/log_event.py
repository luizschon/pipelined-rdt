from time import time
import json

# Event types
PKT_SENT = 1
ACK_SENT = 2
TIMEOUT = 3
CORRUPT = 4
DUP_ACK = 5
DUP_DATA = 6
OUT_OF_ORDER = 7

class Event:
    def __init__(self, role, type, seq, base, data):
        self.type = type
        self.data = data
        self.role = role
        self.seq  = seq
        self.base = base
        self.time = time()

    def export(self):
        return json.dumps({
            'type': self.type,
            'role': self.role,
            'time': self.time,
            'base': self.base,
            'seq': self.seq,
            'data': self.data,
        })

class Logger:
    events = []

    def __init__(self, role):
        self.role = role

    def mark_event(self, type, base, seq, data):
        self.events.append(Event(self.role, type, seq, base, data))