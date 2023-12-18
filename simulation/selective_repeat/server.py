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
    start_time = 0

    def __init__(self, server: str, port: str, response_func: Callable=None, logger: Logger=None):
        Thread.__init__(self)
        self.logger = logger
        self.server = server
        self.port = port
        self.response_func = response_func
        if self.response_func == None:
            self.response_func = default_reponse

    def run(self):
        # Initialize state variables
        global recv_buffer
        recv_buffer = ''

        # Callback called by Receiver when data arrives
        def recv_callback(msg: str):
            global recv_buffer
            recv_buffer += msg

        try:
            self.conn = NetworkLayer('server', self.server, self.port)
            self.sender = Sender(self.conn, ws=c.WINDOW_SIZE, timeout_sec=c.TIMEOUT, logger=self.logger)
            self.recver = Receiver(self.conn, ws=c.WINDOW_SIZE, logger=self.logger)
            sender_t = Thread(target=self.sender.run)
            recver_t = Thread(target=self.recver.run, args=[recv_callback])
            recver_t.start()
            self.start_time = time_ns()

            while self.recver.last_recv_time == 0 or time() < self.recver.last_recv_time + c.TIMEOUT + 5 :
                pass

            self.recver.stop()
            recver_t.join()
            sender_t.start()

            # Send captalized text as response to client
            for chunk in utils.getChunks(c.PACKET_SIZE, recv_buffer):
                self.sender.send(self.response_func(chunk))
            recv_buffer = '' # Clean buffer

            # Wait communication to end
            while self.sender.pending_packets() and time() < self.sender.last_recv_time + 5:
                pass

            self.sender.stop()
            sender_t.join()
            self.conn.disconnect()

        except:
            if self.sender: self.sender.stop()
            if self.recver: self.recver.stop()
            if self.conn: self.conn.disconnect()


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
        server = Server(args.server, args.port, uppercase, Logger())
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
