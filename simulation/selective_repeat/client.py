import sys, argparse
from threading import Thread, Lock
from sender import Sender
from receiver import Receiver
from time import time

# Hacky fix to import from parent folder
path_slip = __file__.split('/')
sys.path.append('/'.join(path_slip[0:len(path_slip)-2]))

from Network import NetworkLayer
from log_event import *
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
        for chunk in utils.getChunks(c.PACKET_SIZE, self.data_buffer):
            self.sender.send(chunk)
        
        # Waits for every byte in the response to be recved
        while bytes_pending:
            buffer_mutex.acquire()
            bytes_pending -= len(recv_buffer)
            sys.stdout.write(recv_buffer)
            recv_buffer = ''
            buffer_mutex.release()

        # Waits for no data to arrive for some time before closing connection to
        # the server, in case ACK sent got lost
        sys.stderr.write('Waiting a few seconds before closing connection with server\n')
        while time() < self.recver.last_recv_time + c.TIMEOUT + 5 :
            pass

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
        client.join()

        first_pkt_time = client.logger.events[0].export()['time']
        last_pkt_time  = client.logger.events[-1].export()['time']

        elapsed_time = (last_pkt_time - first_pkt_time)/10**9
        stats = client.get_stats()
        throughput = stats['bytes_sent'] + stats['bytes_recv']
        throughput = throughput*8/elapsed_time
        goodput = stats['sender']['bytes_sent'] + stats['recver']['bytes_recv']
        goodput = goodput*8/elapsed_time

        sys.stderr.write('\n')
        sys.stderr.write(f"Throughput: {throughput:.2f} bps\n")
        sys.stderr.write(f"Goodput: {goodput:.2f} bps\n")
        sys.stderr.write(f"Total data pkts: {stats['sender']['pkts_sent']}\n")
        sys.stderr.write(f"Total ACK pkts: {stats['recver']['ack_pkts_sent']}\n")
        sys.stderr.write(f"Total data retransmissions: {stats['sender']['retransmissions']}\n")
        sys.stderr.write(f"Total ACK retransmissions: {stats['recver']['retransmissions']}\n")
        sys.stderr.write(f"Total corrupted pkts: {stats['recver']['corrupted_pkts']}\n")
        sys.stderr.write(f"Total elapsed time: {elapsed_time}s\n")
        

    except (Exception, KeyboardInterrupt) as err:
        sys.stderr.write('ERROR: ' + type(err).__name__ + '\n')
        sys.stderr.write(str(err))
        sys.stderr.write('\n')
