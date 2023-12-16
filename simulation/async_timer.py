from threading import Timer
from typing import Callable

class AsyncTimer:
    timer = None

    def __init__(self, timeout_sec: float, callback: Callable[[any], any], args=[]):
        self.timeout = timeout_sec
        self.callback = callback
        self.args = args

    def start(self):
        if self.timer != None:
            self.timer.cancel()
    
        self.timer = Timer(self.timeout, self.callback, args=self.args)
        self.timer.start()

    def stop(self):
        if self.timer != None:
            self.timer.cancel()
        self.timer = None

    def change_timeout(self, timeout: float):
        self.timeout = timeout