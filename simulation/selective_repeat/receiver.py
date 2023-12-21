import sys, argparse
from threading import Thread, Lock
from typing import Callable
from time import sleep, time

# Hacky fix to import from parent folder
path_slip = __file__.split('/')
sys.path.append('/'.join(path_slip[0:len(path_slip)-2]))

from Network import NetworkLayer
from RDT import Packet, getPackets, ACK
from utils import debug_log
from log_event import *

class Receiver:
    # State control variables
    base = 0
    next_base = 0
    last_recv_time = 0
    running = False
    status_lock = Lock()    # Lock for running status
    control_lock = Lock()   # Lock for control variables
    # Stats variables
    bytes_recv = 0
    corrupted_pkts = 0
    pkts_sent = 0
    retransmissions = 0

    def __init__(
        self,
        conn: NetworkLayer,
        sender_ack_handler: Callable[[int], any],
        ws=10, logger: Logger=None
    ):
        self.conn = conn
        self.logger = logger
        self.ws = ws
        self.recv_buffer = [None] * ws 
        self.sender_ack_handler = sender_ack_handler

    def _recv(self, pkt: Packet, recv_callback: Callable[[str], any]):
        seq = pkt.seq_num
        msg = pkt.msg_S

        if pkt.is_ack_pack():
            self.sender_ack_handler(seq)
            return

        usable_len = int(self.ws/2)

        debug_log(f'[sr recver]: Received pkt seq: {seq}')
        debug_log(f'[sr recver]: Current base: {self.base}')
        if self.logger: self.logger.mark_event(DATA_RECV, self.base, seq, msg)

        # If seq number is out of the expected waiting range, send repeated ACK.
        # We trust that the sender is correctly synchronized with us, 
        if (seq - self.base) % self.ws + 1 > usable_len:
            debug_log(f'[sr recver]: Pkt outside range, resending ACK...')
            if self.logger: self.logger.mark_event(DUP_DATA, self.base, seq)
            self.pkts_sent += 1
            self.retransmissions += 1
            self.conn.udt_send(Packet(seq, ack=True).get_byte_S())
            return

        # If seq number received is equal to the base, update the base of the 
        # receiving window, otherwise, save packet in the out-of-order buffer.
        if seq == self.base:
            counter = 0
            for buffered in self.recv_buffer:
                if buffered == None:
                    break
                counter += 1

            data = ''.join([msg] + self.recv_buffer[:counter])
            self.base = (self.base + counter + 1) % self.ws

            debug_log(f'[sr recver]: Received base seq number, updating base and sending data to upper-layer')
            debug_log(f'             Pkts ACKed: {counter + 1}')

            # Send data to upper-layer and clean recv buffer
            recv_callback(data)
            self.bytes_recv += len(data)

            self.recv_buffer = self.recv_buffer[counter+1:] + ([None] * (counter+1))
        else:
            relative_seq = (seq - self.base) % usable_len - 1
            if self.recv_buffer[relative_seq] == None:
                # Save out of order package:
                # The seq number relative to the current base
                debug_log(f'[sr recver]: Saving out-of-order pkt')
                if self.logger: self.logger.mark_event(OUT_OF_ORDER, self.base, seq)
                self.recv_buffer[relative_seq] = msg
            else:
                debug_log(f'[sr recver]: Repeated pkt, resending ACK...')
                if self.logger: self.logger.mark_event(DUP_DATA, self.base, seq)
                self.retransmissions += 1

        if self.logger: self.logger.mark_event(ACK_SENT, self.base, seq)
        self.conn.udt_send(Packet(seq, ack=True).get_byte_S())
        self.pkts_sent += 1

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
            self.last_recv_time = time()
            pkts, corrupt = getPackets(data_recv)
            if corrupt:
                self.corrupted_pkts += 1
                if self.logger: self.logger.mark_event(CORRUPT)
            for p in pkts:
                self._recv(p, recv_callback)

        debug_log('Stopped Selective Repeat receiver!')
    
    def stop(self):
        with self.status_lock:
            if not self.running:
                print('ERROR: Receiver not running, can\'t stop')
                return
            self.running = False
        
        self.last_recv_time = 0
        self.base = 0

    def get_stats(self):
        with self.control_lock:
            return {
                'bytes_recv': self.bytes_recv,
                'corrupted_pkts': self.corrupted_pkts,
                'ack_pkts_sent': self.pkts_sent,
                'retransmissions': self.retransmissions,
            }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Selective Repeat Receiver.')
    parser.add_argument('role', help='Role.')
    parser.add_argument('server', help='Server.')
    parser.add_argument('port', help='Port.', type=int)
    args = parser.parse_args()

    global recv_buffer
    recv_buffer = []

    def callback(msg: str):
        recv_buffer.append(msg)

    conn = None
    recver = None
    runner = None
    try:
        conn = NetworkLayer(args.role, args.server, args.port)
        recver = Receiver(conn)
        runner = Thread(target=recver.run, args=[callback])
        runner.start()

        while recver.last_recv_time == 0:
            pass
        while time() < recver.last_recv_time + 5:
            sleep(1)

        recver.stop()
        runner.join()
        conn.disconnect()
        print(f'RECVER BUFFER: {recv_buffer}')

    except (Exception, KeyboardInterrupt) as err:
        print('ERROR: ' + type(err).__name__)
        print(err)
        if recver != None:
            recver.stop()
            runner.join()
        if recver != None:
            conn.disconnect()
    
