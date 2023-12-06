import sys, argparse
from threading import Lock, Timer
from typing import Callable

# Hacky fix to import from parent folder
path_slip = __file__.split('/')
sys.path.append('/'.join(path_slip[0:len(path_slip)-2]))

from Network import NetworkLayer
from RDT import Packet, getPackets, debug_log

class Receiver:
    # State control variables
    recv_buffer = ['']*10   # Buffer that holds out-of-order packets received
    expected_ack = 0
    running = False
    status_lock = Lock()    # Lock for running status
    control_lock = Lock()   # Lock for control variables


    def __init__(self, conn: NetworkLayer, recv_callback: Callable[[str], any], ws=10, timeout_sec=2):
        self.conn = conn
        self.ws = ws
        self.recv_callback = recv_callback
        self.timeout_sec = timeout_sec


    # Main method of the sender, should be only called once before the stop
    # method is called
    def run(self):
        with self.status_lock:
            if self.running:
                print('ERROR: Receiver instance already running')
                return
            self.running = True

        debug_log('Started Selective Repeat receiver!')
        debug_log(f'WINDOW SIZE: {self.ws}\n')

        # Create asynchronous timers for each sequence number
        self.timers = [Timer(self.timeout_sec, self._handle_timeout, args=[seq]) for seq in range(self.ws)]

        while self.running:
            data_recv = self.conn.udt_receive()
            if data_recv == '':
                continue
            # Get packets that are not corrupt and receive them
            pkts = getPackets(data_recv)
            for p in pkts:
                self.recv(p)

        debug_log('Stopped Selective Repeat receiver!')
    

    def stop(self):
        with self.status_lock:
            if not self.running:
                print('ERROR: Receiver not running, can\'t stop')
                return
            self.running = False

        # Stop all timers
        for timer in self.timers:
            timer.cancel()
        
        self.base = 0
        self.next_seq = 0
        self.pkts_in_air = dict()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Selective Repeat Receiver.')
    parser.add_argument('role', help='Role.')
    parser.add_argument('server', help='Server.')
    parser.add_argument('port', help='Port.', type=int)
    args = parser.parse_args()

    recv_buffer = ''
    def callback(msg: str):
        recv_buffer += msg

    try:
        conn = NetworkLayer(args.role, args.server, args.port)
        recver = Receiver(conn, callback)
    except:
        pass
