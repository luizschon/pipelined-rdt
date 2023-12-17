import sys, argparse
from threading import Thread, Lock
from time import time
from sender import Sender
from receiver import Receiver

# Hacky fix to import from parent folder
path_slip = __file__.split('/')
sys.path.append('/'.join(path_slip[0:len(path_slip)-2]))

from Network import NetworkLayer
from constants import *
import utils

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Selective Repeat Server.')
    parser.add_argument('server', help='Server.')
    parser.add_argument('port', help='Port.', type=int)
    args = parser.parse_args()

    # Initialize state variables
    global recv_buffer
    recv_buffer = ''
    conn = sender = recver = None
    sender_t = recver_t = None

    # Callback called by Receiver when data arrives
    def recv_callback(msg: str):
        global recv_buffer
        recv_buffer += msg

    try:
        conn = NetworkLayer('server', args.server, args.port)
        sender = Sender(conn, ws=WINDOW_SIZE, timeout_sec=TIMEOUT)
        recver = Receiver(conn, ws=WINDOW_SIZE)

        # Received data from client
        recver_t = Thread(target=recver.run, args=[recv_callback])
        recver_t.start()

        while recver.last_recv_time == 0 or time() < recver.last_recv_time + TIMEOUT + 5 :
            pass

        recver.stop()
        recver_t.join()

        sender_t = Thread(target=sender.run)
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
            
    except (Exception, KeyboardInterrupt) as err:
        print('ERROR: ' + type(err).__name__)
        print(err)
        if conn:
            sender.stop()
            sender_t.join()
            recver.stop()
            recver_t.join()
            conn.disconnect()

    sys.stderr.write('\n')
    sys.stderr.write(f'sender: {sender.get_stats()}\n')
    sys.stderr.write(f'recver: {recver.get_stats()}\n')
    sys.stderr.write(f'conn  : {conn.get_stats()}\n')