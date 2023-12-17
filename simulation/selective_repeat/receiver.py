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

class Receiver:
    # State control variables
    base = 0
    next_base = 0
    last_recv_time = 0
    running = False
    status_lock = Lock()    # Lock for running status
    control_lock = Lock()   # Lock for control variables

    def __init__(self, conn: NetworkLayer, ws=10):
        self.conn = conn
        self.ws = ws
        self.recv_buffer = [None] * ws 

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
            self.conn.udt_send(Packet(seq, ACK).get_byte_S())
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
            self.recv_buffer = self.recv_buffer[counter+1:] + ([None] * (counter+1))
            self.conn.udt_send(Packet(seq, ACK).get_byte_S())
        else:
            relative_seq = (seq - self.base) % usable_len - 1
            if self.recv_buffer[relative_seq] == None:
                # Save out of order package:
                # The seq number relative to the current base
                debug_log(f'[sr recver]: Saving out-of-order pkt')
                self.recv_buffer[relative_seq] = msg
            else:
                debug_log(f'[sr recver]: Repeated pkt, resending ACK...')
                self.conn.udt_send(Packet(seq, ACK).get_byte_S())

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
            pkts = getPackets(data_recv)
            for p in pkts:
                self._recv(p, recv_callback)

        debug_log('\nStopped Selective Repeat receiver!')
    
    def stop(self):
        with self.status_lock:
            if not self.running:
                print('ERROR: Receiver not running, can\'t stop')
                return
            self.running = False
        
        self.last_recv_time = 0
        self.base = 0

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
    
