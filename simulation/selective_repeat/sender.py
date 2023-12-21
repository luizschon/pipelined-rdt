import sys, argparse
from threading import Thread, Lock, Semaphore
from time import sleep

# Hacky fix to import from parent folder
path_slip = __file__.split('/')
sys.path.append('/'.join(path_slip[0:len(path_slip)-2]))

from Network import NetworkLayer
from RDT import Packet, getPackets
from async_timer import AsyncTimer
from utils import debug_log
from log_event import *

class Sender:
    # State control variables
    base = 0
    next_seq = 0
    pkts_in_air = dict()
    running = False
    timer = []
    status_lock = Lock()    # Lock for running status
    control_lock = Lock()   # Lock for control variables
    # Stats variables
    bytes_sent = 0
    pkts_sent = 0
    retransmissions = 0

    def __init__(self, conn: NetworkLayer, ws=10, timeout_sec=2, logger: Logger=None):
        self.conn = conn
        self.logger = logger
        self.ws = ws
        self.semph = Semaphore(int(ws/2))
        self.timer = [AsyncTimer(timeout_sec, self._handle_timeout, args=[seq]) for seq in range(ws)]

    # Timeout handler for each packet in-air, called by Timer threading objects
    def _handle_timeout(self, seq: int):
        with self.control_lock:
            pkt = self.pkts_in_air[seq]
            debug_log(f'[sr sender]: TIMEOUT, resending seq: {seq}, curr base: {self.base}')
            if self.logger: self.logger.mark_event(TIMEOUT, self.base, seq, pkt.msg_S)
            self.conn.udt_send(pkt.get_byte_S())
            self.pkts_sent += 1
            self.bytes_sent += len(pkt.msg_S)
            self.retransmissions += 1
            self.timer[seq].start()

    # Method called from layer above (server or client) to send data through
    # reliable tunnel 
    def send(self, data: str):
        self.semph.acquire()
        with self.status_lock:
            if not self.running:
                print('ERROR: Run sender before calling "send" method')

        with self.control_lock:
            seq = self.next_seq
            pkt = Packet(seq, str(data))
            self.pkts_in_air[seq] = pkt

            debug_log(f'[sr sender]: Sent packet, seq: {seq}, msg len: {len(data)}, curr base: {self.base}')
            if self.logger: self.logger.mark_event(PKT_SENT, self.base, seq, data)

            self.conn.udt_send(pkt.get_byte_S())
            self.pkts_sent += 1
            self.bytes_sent += len(pkt.msg_S)

            self.timer[seq].start()
            self.next_seq = (self.next_seq + 1) % self.ws

    # Method called from upper-layer to notify sender that ack was received by
    # receiver. Updates base and releases sender's semaphores
    def handle_ack(self, seq: int):
        with self.control_lock:
            if not self.pkts_in_air.get(seq):
                debug_log(f'[sr sender] WARNING: Received unexpected ACK, seq: {seq}')
                if self.logger: self.logger.mark_event(DUP_ACK, self.base, seq)
                return

            debug_log(f'[sr sender]: Received ACK, seq: {seq}, curr base: {self.base}')
            self.timer[seq].stop()
            del self.pkts_in_air[seq]
            old_base = self.base

            # Updates base. Should be equal to the least recent seq sent
            if len(self.pkts_in_air) != 0:
                self.base = next(iter(self.pkts_in_air)) # Get first key of dict
            else:
                self.base = self.next_seq

            if self.logger: self.logger.mark_event(ACK_RECV, self.base, seq)

            # Release semaphores only if base changed
            if self.base != old_base:
                debug_log(f'[sr sender]: Shifted base: {self.base}')
                self.semph.release((self.base - old_base) % self.ws)

    # Main method of the sender, should be only called once before the stop
    # method is called
    def run(self):
        with self.status_lock:
            if self.running:
                print('ERROR: Sender instance already running')
                return
            self.running = True

        debug_log('Started Selective Repeat sender!')
        debug_log(f'WINDOW SIZE: {self.ws}\n')

        while self.running:
            pass

        debug_log('Stopped Selective Repeat sender!')
    
    def stop(self):
        with self.status_lock:
            if not self.running:
                print('ERROR: Sender not running, can\'t stop')
                return
            self.running = False

        for timer in self.timer: timer.stop()
        self.base = 0
        self.next_seq = 0
        self.pkts_in_air = dict()

    def pending_packets(self) -> bool:
        with self.control_lock:
            return len(self.pkts_in_air) > 0

    def get_stats(self):
        with self.control_lock:
            return {
                'bytes_sent': self.bytes_sent,
                'retransmissions': self.retransmissions,
                'pkts_sent': self.pkts_sent,
            }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Selective Repeat Sender.')
    parser.add_argument('role', help='Role.')
    parser.add_argument('server', help='Server.')
    parser.add_argument('port', help='Port.', type=int)
    args = parser.parse_args()

    conn = None
    sender = None
    runner = None
    try:
        conn = NetworkLayer(args.role, args.server, args.port)
        sender = Sender(conn)
        runner = Thread(target=sender.run)
        runner.start()

        for msg in "o guga eh favoravel a brotherage, o tempo todo me aparece esse lobo pidao".split(' '):
            sender.send(msg)
        while sender.pending_packets():
            sleep(1)

        sender.stop()
        runner.join()
        sleep(5)
        conn.disconnect()

    except (Exception, KeyboardInterrupt) as err:
        print('ERROR: ' + type(err).__name__)
        print(err)
        if sender != None:
            sender.stop()
            runner.join()
        if conn != None:
            conn.disconnect()
