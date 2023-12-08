import sys, argparse
from threading import Lock
from typing import Callable

# Hacky fix to import from parent folder
path_slip = __file__.split('/')
sys.path.append('/'.join(path_slip[0:len(path_slip)-2]))

from Network import NetworkLayer
from RDT import Packet, getPackets, debug_log, ACK

class Receiver:
    # State control variables
    base = 0
    next_base = 0
    running = False
    status_lock = Lock()    # Lock for running status
    control_lock = Lock()   # Lock for control variables

    def __init__(self, conn: NetworkLayer, ws=10):
        self.conn = conn
        self.ws = ws
        self.recv_buffer = ['']*(ws) 

    def _recv(self, pkt: Packet, recv_callback: Callable[[str], any]):
        seq = pkt.seq_num
        msg = pkt.msg_S
        usable_len = int(self.ws/2)

        debug_log(f'[sr recver]: Received pkt seq: {seq}')
        debug_log(f'[sr recver]: Current base: {self.base}')

        # If seq number is out of the expected waiting range, send repeated ACK.
        # We trust that the sender is correctly synchronized with us, 
        if (seq - self.base) % self.ws + 1 > usable_len:
            debug_log(f'[sr recver]: Pkt outside range, resending ACK...')
            self.conn.udt_send(Packet(seq, ACK))
            return

        # If seq number received is equal to the base, update the base of the 
        # receiving window, otherwise, save packet in the out-of-order buffer.
        if seq == self.base:
            counter = 0
            while self.recv_buffer[counter] != '':
                counter += 1

            data = msg.join(recv_buffer[0:counter+1], '')
            self.base = (self.base + counter + 1) % self.ws

            debug_log(f'[sr recver]: Received base seq number, updating base and sending data to upper-layer')
            debug_log(f'             DATA: {data}')
            debug_log(f'             Pkts ACKed: {counter + 1}')

            # Send data to upper-layer and clean recv buffer
            recv_callback(data)
            recv_buffer = recv_buffer[:counter+1] + ([''] * counter)
        else:
            # Save out of order package:
            # The seq number relative to the current base
            debug_log(f'[sr recver]: Saving out-of-order pkt')
            relative_seq = (seq - self.base) % usable_len - 1
            recv_buffer[relative_seq] = msg

    # Main method of the receiver, should be only called once before the stop
    # method is called
    def run(self, recv_callback: Callable[[str], any]):
        with self.status_lock:
            if self.running:
                print('ERROR: Receiver instance already running')
                return
            self.running = True

        debug_log('Started Selective Repeat receiver!')
        debug_log(f'WINDOW SIZE: {self.ws}\n')

        while self.running:
            data_recv = self.conn.udt_receive()
            if data_recv == '':
                continue
            # Get packets that are not corrupt and receive them
            pkts = getPackets(data_recv)
            for p in pkts:
                self._recv(p, recv_callback)

        debug_log('Stopped Selective Repeat receiver!')
    
    def stop(self):
        with self.status_lock:
            if not self.running:
                print('ERROR: Receiver not running, can\'t stop')
                return
            self.running = False
        
        self.base = 0
        self.expected_ack = 0


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
