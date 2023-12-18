import sys, argparse
from threading import Thread, Lock
from sender import Sender
from receiver import Receiver

# Hacky fix to import from parent folder
path_slip = __file__.split('/')
sys.path.append('/'.join(path_slip[0:len(path_slip)-2]))

from Network import NetworkLayer
from log_event import Logger
from constants import *
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

        # Callback called by Receiver when data arrives
        def recv_callback(msg: str):
            global recv_buffer
            with buffer_mutex:
                recv_buffer += msg

        # Mutex to control access to recv_buffer, since the recver and main threads
        # will both access it simutaneously
        buffer_mutex = Lock() 
        self.conn = NetworkLayer('client', self.server, self.port)
        self.sender = Sender(self.conn, ws=WINDOW_SIZE, timeout_sec=TIMEOUT, logger=self.logger)
        self.recver = Receiver(self.conn, ws=WINDOW_SIZE, logger=self.logger)
        # Runs sender and recver threads separately
        sender_t = Thread(target=self.sender.run)
        recver_t = Thread(target=self.recver.run, args=[recv_callback])

        # Sends data in PACKET_SIZE sized chunks to server
        bytes_pending = len(self.data_buffer)
        sender_t.start()
        for chunk in utils.getChunks(PACKET_SIZE, self.data_buffer):
            self.sender.send(chunk)
        
        while self.sender.pending_packets():
            pass

        self.sender.stop()
        sender_t.join()
        recver_t.start()

        # Waits for every byte in the response to be recved
        while bytes_pending:
            buffer_mutex.acquire()
            bytes_pending -= len(recv_buffer)
            sys.stdout.write(recv_buffer)
            recv_buffer = ''
            buffer_mutex.release()

        self.recver.stop()
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
        client = Client(args.server, args.port, args.file, Logger('client'))
        client.start()
        client.join()
        print([e.export() for e in client.logger.events])

    except (Exception, KeyboardInterrupt) as err:
        print('ERROR: ' + type(err).__name__)
        print(err)