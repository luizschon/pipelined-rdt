import argparse, sys
from threading import Thread, Semaphore, Lock
from time import time, sleep
from module import PipeRDT_Protocol, getPackets, ACK

path_slip = __file__.split('/')
sys.path.append('/'.join(path_slip[0:len(path_slip)-2]))
from Network import NetworkLayer
from RDT import Packet, debug_log

class SelectiveRepeat(PipeRDT_Protocol):
    def __init__(self, role_S, server_S, port):
        self._network = NetworkLayer(role_S, server_S, port)
        self._window_size = 5
        self._timeout = 3
        self._seq_num = 0
        self._buffer = bytearray()

    def disconnect(self):
        self._network.disconnect()

    def send(self, msg: str) -> None:
        pass

    def receive(self) -> bytearray:
        pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='RDT4 implementation.')
    parser.add_argument('role', help='Role is either client or server.', choices=['client', 'server'])
    parser.add_argument('server', help='Server.')
    parser.add_argument('port', help='Port.', type=int)
    args = parser.parse_args()

    sim = SelectiveRepeat(args.role, args.server, args.port)
    if args.role == 'client':
        sim.send(['MSG_FROM_CLIENT', 'MSG_1', 'MSG_2', 'MSG_3', 'MSG_4', 'MSG_5', 'MSG_6', 'MSG_7', 'MSG_1', 'MSG_2', 'MSG_3', 'MSG_4', 'MSG_5', 'MSG_6', 'MSG_7'])
        sleep(1)
        print(sim.receive())
        sim.disconnect()

    else:
        print(sim.receive())
        sleep(1)
        sim.send(['MSG_FROM_SERVER', 'MSG_1', 'MSG_2', 'MSG_3', 'MSG_4', 'MSG_5', 'MSG_6', 'MSG_7', 'MSG_1', 'MSG_2', 'MSG_3', 'MSG_4', 'MSG_5', 'MSG_6', 'MSG_7'])
        sim.disconnect()
        