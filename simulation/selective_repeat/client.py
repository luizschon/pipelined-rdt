import sys, argparse
from threading import Thread, Lock
from sender import Sender
from receiver import Receiver

# Hacky fix to import from parent folder
path_slip = __file__.split('/')
sys.path.append('/'.join(path_slip[0:len(path_slip)-2]))

from Network import NetworkLayer
from constants import *
import utils

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Selective Repeat Client. Prints response to stdout')
    parser.add_argument('server', help='Server.')
    parser.add_argument('port', help='Port.', type=int)
    parser.add_argument('file', help='File.')
    args = parser.parse_args()

    # Initialize state variables
    global recv_buffer
    recv_buffer = ''
    conn = sender = recver = None
    sender_t = recver_t = None
    # Mutex to control access to recv_buffer, since the recver and main threads
    # will both access it simutaneously
    buffer_mutex = Lock() 

    # Callback called by Receiver when data arrives
    def recv_callback(msg: str):
        global recv_buffer
        with buffer_mutex:
            recv_buffer += msg

    try:
        conn = NetworkLayer('client', args.server, args.port)
        sender = Sender(conn, ws=WINDOW_SIZE, timeout_sec=TIMEOUT)
        recver = Receiver(conn, ws=WINDOW_SIZE)
        # Runs sender and recver threads separately
        sender_t = Thread(target=sender.run)
        recver_t = Thread(target=recver.run, args=[recv_callback])

        with open(args.file) as f:
            sender_t.start()
            buffer = f.read()
            bytes_pending = len(buffer)

            # Sends data in PACKET_SIZE sized chunks to server
            for chunk in utils.getChunks(PACKET_SIZE, buffer):
                sender.send(chunk)
            
            while sender.pending_packets():
                pass

            sender.stop()
            sender_t.join()
            recver_t.start()

            # Waits for every byte in the response to be recved
            while bytes_pending:
                buffer_mutex.acquire()
                bytes_pending -= len(recv_buffer)
                sys.stdout.write(recv_buffer)
                recv_buffer = ''
                buffer_mutex.release()

            recver.stop()
            recver_t.join()
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