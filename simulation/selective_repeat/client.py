import sys, argparse
from threading import Thread, Lock
from sender import Sender
from receiver import Receiver
from time import time_ns

# Hacky fix to import from parent folder
path_slip = __file__.split('/')
sys.path.append('/'.join(path_slip[0:len(path_slip)-2]))

from Network import NetworkLayer
from log_event import Logger
import constants as c
import utils

class Client(Thread):
    def __init__(self, server, port, data, logger: Logger=None):
        Thread.__init__(self)
        self.logger = logger
        self.data_buffer = data
        self.server = server
        self.port = port

    def run(self):
        # Initialize state variables
        global recv_buffer
        recv_buffer = ''

        # Mutex to control access to recv_buffer, since the recver and main threads
        # will both access it simutaneously
        buffer_mutex = Lock() 
        self.conn = NetworkLayer('client', self.server, self.port)
        self.sender = Sender(self.conn, ws=c.WINDOW_SIZE, timeout_sec=c.TIMEOUT, logger=self.logger)
        self.recver = Receiver(self.conn, self.sender.handle_ack, ws=c.WINDOW_SIZE, logger=self.logger)

        # Callback called by Receiver when data arrives
        def recv_callback(msg: str):
            global recv_buffer
            with buffer_mutex:
                recv_buffer += msg

        # Runs sender and recver threads separately
        sender_t = Thread(target=self.sender.run)
        recver_t = Thread(target=self.recver.run, args=[recv_callback])
        sender_t.start()
        recver_t.start()

        # Sends data in PACKET_SIZE sized chunks to server
        bytes_pending = len(self.data_buffer)
        print(f'bytes pending: {bytes_pending}')
        for chunk in utils.getChunks(c.PACKET_SIZE, self.data_buffer):
            self.sender.send(chunk)
        
        # Waits for every byte in the response to be recved before closing the
        # connection to the server
        while bytes_pending:
            buffer_mutex.acquire()
            bytes_pending -= len(recv_buffer)
            sys.stdout.write(recv_buffer)
            recv_buffer = ''
            buffer_mutex.release()

        self.sender.stop()
        self.recver.stop()
        sender_t.join()
        recver_t.join()
        self.conn.disconnect()

    def get_conn_stats(self):
        return self.conn.get_stats()

    def get_stats(self):
        return {
            **self.conn.get_stats(),
            'sender': self.sender.get_stats(),
            'recver': self.recver.get_stats(),
        }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Selective Repeat Client. Prints response to stdout')
    parser.add_argument('server', help='Server.')
    parser.add_argument('port', help='Port.', type=int)
    parser.add_argument('file', help='File.')
    args = parser.parse_args()

    try:
        data = []
        with open(args.file) as f:
            data = f.read()

        client = Client(args.server, args.port, data, Logger())
        client.start()
        timer = time_ns()
        client.join()

        elapsed_time = (time_ns() - timer)/10**9
        stats = client.get_stats()
        throughput = stats['bytes_sent'] + stats['bytes_recv']
        throughput = throughput*8/elapsed_time
        goodput = stats['sender']['bytes_sent'] + stats['recver']['bytes_recv']
        goodput = goodput*8/elapsed_time
        
        sys.stderr.write('\n')
        sys.stderr.write(f"Throughput: {throughput:.2f} bps\n")
        sys.stderr.write(f"Goodput: {goodput:.2f} bps\n")
        sys.stderr.write(f"Total non-ACK pkts: {stats['sender']['pkts_sent']}\n")
        sys.stderr.write(f"Total ACK pkts: {stats['recver']['ack_pkts_sent']}\n")
        sys.stderr.write(f"Total non-ACK retransmissions: {stats['sender']['retransmissions']}\n")
        sys.stderr.write(f"Total ACK retransmissions: {stats['recver']['retransmissions']}\n")
        sys.stderr.write(f"Total non-ACK corrupt pkts: {stats['recver']['corrupted_pkts']}\n")
        sys.stderr.write(f"Total ACK corrupt pkts: {stats['sender']['corrupted_pkts']}\n")
        sys.stderr.write(f"Total elapsed time: {elapsed_time}s\n")
        sys.stderr.write('\n')
        

    except (Exception, KeyboardInterrupt) as err:
        print('ERROR: ' + type(err).__name__)
        print(err)
