import sys, argparse
from threading import Thread
from typing import Callable
from time import time, time_ns
from sender import Sender
from receiver import Receiver

# Hacky fix to import from parent folder
path_slip = __file__.split('/')
sys.path.append('/'.join(path_slip[0:len(path_slip)-2]))

from Network import NetworkLayer
from log_event import Logger
import constants as c
import utils

def default_reponse(data: str):
    return data

class Server(Thread):
    def __init__(
        self,
        server: str, port: str,
        response_func: Callable[[str], str]=None,
        logger: Logger=None
    ):
        Thread.__init__(self)
        self.logger = logger
        self.server = server
        self.port = port
        self.response_func = response_func or default_reponse

    def run(self):
        # Initialize state variables
        global recv_buffer
        recv_buffer = ''

        self.conn = NetworkLayer('server', self.server, self.port)
        self.sender = Sender(self.conn, ws=c.WINDOW_SIZE, timeout_sec=c.TIMEOUT, logger=self.logger)
        self.recver = Receiver(self.conn, self.sender.handle_ack, ws=c.WINDOW_SIZE, logger=self.logger)

        # Callback called by Receiver when data arrives. Processes data and send
        # back to the client.
        def recv_callback(msg: str):
            global recv_buffer
            recv_buffer += msg
            for chunk in utils.getChunks(c.PACKET_SIZE, msg):
                print(self.response_func(chunk))
                self.sender.send(self.response_func(chunk))

        # Runs sender and recver threads separately
        sender_t = Thread(target=self.sender.run)
        recver_t = Thread(target=self.recver.run, args=[recv_callback])
        sender_t.start()
        recver_t.start()

        # Waits for no data to arrive for some time before closing connection to
        # the client
        while self.recver.last_recv_time == 0 or time() < self.recver.last_recv_time + c.TIMEOUT + 5 :
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
    parser = argparse.ArgumentParser(description='Selective Repeat Server.')
    parser.add_argument('server', help='Server.')
    parser.add_argument('port', help='Port.', type=int)
    args = parser.parse_args()

    def uppercase(data: str):
        return data.upper()

    try:
        server = Server(args.server, args.port, uppercase, logger=Logger())
        server.start()
        server.join()

        elapsed_time = (time_ns() - server.start_time)/10**9
        stats = server.get_stats()
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
