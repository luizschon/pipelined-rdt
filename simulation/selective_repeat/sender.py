import sys, argparse
from threading import Thread, Lock, Timer
from typing import Callable

# Hacky fix to import from parent folder
path_slip = __file__.split('/')
sys.path.append('/'.join(path_slip[0:len(path_slip)-2]))

from Network import NetworkLayer
from RDT import Packet, getPackets, debug_log

class Sender:
    # State control variables
    base = 0
    next_seq = 0
    pkts_in_air = dict()
    running = False
    status_lock = Lock()    # Lock for running status
    control_lock = Lock()   # Lock for control variables


    def __init__(self, conn: NetworkLayer, ws=10, timeout_sec=2):
        self.conn = conn
        self.ws = ws
        self.timeout_sec = timeout_sec


    # Timeout handler for each packet in-air, called by Timer theading objects
    def _handle_timeout(self, seq: int):
        # TODO: review if this lock is needed
        # with self.control_lock:
            pkt = self.pkts_in_air.get(seq)
            if not pkt:
                raise RuntimeError(f'''SR Sender: tried to resend packet with seq {seq}, 
                                   but is not in pkts_in_air list, maybe the packet arrived 
                                   as the timeout happened if control_lock is not aquired''')

            debug_log(f'[sr sender] WARNING: Timeout on seq {seq}, resending packet...')
            debug_log(f'            DATA:    {pkt.get_byte_S()}')
            self.conn.udt_send(pkt.get_byte_S())
            self.timers[seq].start()    # No need to cancel timer, since it triggered


    # Method called from layer above (server or client) to send data through
    # reliable tunnel 
    def send(self, data: str):
        with self.status_lock:
            if not self.running:
                print('ERROR: Run sender before calling "send" method')

        with self.control_lock:
            if (len(self.pkts_in_air) == self.ws):
                return

            pkt = Packet(self.next_seq, str(data))
            self.pkts_in_air.append(pkt)
            debug_log(f'[sr sender]: Sent packet, seq: {self.next_seq}')
            self.conn.udt_send(pkt.get_byte_S())

            # TODO handle timers better, maybe abstract to its own class
            timer = self.timers[self.next_seq]
            if not timer.is_alive():
                timer.start()
            else:
                timer.cancel()
                timer.start()

            self.next_seq = (self.next_seq + 1) % self.ws


    # Internal function that handles data being received. Calls data recv
    # callback specified by user (server or client)
    def _recv(self, pkt: Packet):
        seq = pkt.seq_num
        msg = pkt.msg_S

        if not pkt.is_ack_pack():
            debug_log(f'[sr sender] WARNING: Expected ACK, got "{msg or None}", data: {pkt.get_byte_S()}')
            debug_log(f'            DATA:    {pkt.get_byte_S()}')
            return

        with self.control_lock:
            if not self.pkts_in_air.get(seq):
                debug_log(f'[sr sender] WARNING: Received unexpected ACK, seq: {seq}')
                return

            # Stop timer for received seq number
            self.timers[seq].cancel()
            debug_log(f'[sr sender]: Received ACK, seq: {seq}')

            # Updates base. Should be equal to the least recent seq sent
            self.pkts_in_air.remove(seq)
            self.base = self.pkts_in_air.keys()[0]
            debug_log(f'[sr sender]: Shifted base: {self.base}')


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

        # Create asynchronous timers for each sequence number
        self.timers = [Timer(self.timeout_sec, self._handle_timeout, args=[seq]) for seq in range(self.ws)]

        while self.running:
            data_recv = self.conn.udt_receive()
            if data_recv == '':
                continue
            # Get packets that are not corrupt and receive them
            pkts = getPackets(data_recv)
            for p in pkts:
                self._recv(p)

        debug_log('Stopped Selective Repeat sender!')
    

    def stop(self):
        with self.status_lock:
            if not self.running:
                print('ERROR: Sender not running, can\'t stop')
                return
            self.running = False

        # Stop all timers
        for timer in self.timers:
            timer.cancel()
        
        self.base = 0
        self.next_seq = 0
        self.pkts_in_air = dict()


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
        runner.join()
    except Exception as err:
        print('ERROR: ' + type(err).__name__)
        print(err)
        if sender != None:
            sender.stop()
            runner.join()
        if sender != None:
            conn.disconnect()
