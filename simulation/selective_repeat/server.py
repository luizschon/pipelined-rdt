import sys, argparse
from threading import Thread, Lock
from time import time
from sender import Sender
from receiver import Receiver

# Hacky fix to import from parent folder
path_slip = __file__.split('/')
sys.path.append('/'.join(path_slip[0:len(path_slip)-2]))

from Network import NetworkLayer
from log_event import Logger
from constants import *
import utils

class Server(Thread):
    def __init__(self, server: str, port: str, logger: Logger=None):
        Thread.__init__(self)
        self.logger = logger
        self.server = server
        self.port = port

    def run(self):
        # Initialize state variables
        global recv_buffer
        recv_buffer = ''

        # Callback called by Receiver when data arrives
        def recv_callback(msg: str):
            global recv_buffer
            recv_buffer += msg

        conn = NetworkLayer('server', self.server, self.port)
        sender = Sender(conn, ws=WINDOW_SIZE, timeout_sec=TIMEOUT, logger=self.logger)
        recver = Receiver(conn, ws=WINDOW_SIZE, logger=self.logger)
        sender_t = Thread(target=sender.run)
        recver_t = Thread(target=recver.run, args=[recv_callback])
        recver_t.start()

        while recver.last_recv_time == 0 or time() < recver.last_recv_time + TIMEOUT + 5 :
            pass

        recver.stop()
        recver_t.join()

        sender_t.start()

        # Send captalized text as response to client
        for chunk in utils.getChunks(PACKET_SIZE, recv_buffer):
            sender.send(chunk)
        recv_buffer = '' # Clean buffer

        # Wait communication to end
        while sender.pending_packets() and time() < sender.last_recv_time + 5:
            pass

        sender.stop()
        sender_t.join()
        conn.disconnect()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Selective Repeat Server.')
    parser.add_argument('server', help='Server.')
    parser.add_argument('port', help='Port.', type=int)
    args = parser.parse_args()

    try:
        server = Server(args.server, args.port, Logger('server'))
        server.start()
        server.join()
        print([e.export() for e in server.logger.events])

            
    except (Exception, KeyboardInterrupt) as err:
        print('ERROR: ' + type(err).__name__)
        print(err)