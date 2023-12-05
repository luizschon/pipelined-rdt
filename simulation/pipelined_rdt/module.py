import sys
from time import time
from abc import ABC, abstractmethod
from threading import Thread, Semaphore, Lock

path_slip = __file__.split('/')
sys.path.append('/'.join(path_slip[0:len(path_slip)-2]))
from RDT import Packet, debug_log

ACK = "1"

def getPackets(data_stream: str) -> [Packet]:
    parsed_packets = []
    counter = 0

    while data_stream != "":
        packet_len = int(data_stream[0:Packet.length_S_length])    

        # Sanity check to guarantee that the remaining data is greater or equal
        # than the parsed packet length, otherwise, we would have a runtime error
        if len(data_stream) < packet_len:
            return parsed_packets

        packet_stream = data_stream[0:packet_len]
        debug_log(f"getPackets P{counter+1}: {packet_stream}")
        data_stream = data_stream[packet_len:]

        # If one of the packets is corrupt, stop execution and return parsed packets
        if Packet.corrupt(packet_stream):
            debug_log("getPackets: Found corrupt packet in data stream, aborting parsing...")
            break

        parsed_packets.append(Packet.from_byte_S(packet_stream))
        counter += 1

    debug_log(f"getPackets: Found {len(parsed_packets)} packets")
    return parsed_packets
    

class PipeRDT_Protocol(ABC):
    @abstractmethod
    def disconnect(self) -> None:
        pass

    @abstractmethod
    def send(self, msg: str) -> None:
        pass

    @abstractmethod
    def receive(self) -> str:
        pass


class PipeRDT:
    def __init__(self, protocol: PipeRDT_Protocol, role: str, server: str, port: str):
        self._protocol = protocol(role, server, port)

    def disconnect(self):
        self._protocol.disconnect()

    def send(self, msg):
        self._protocol.send(msg)

    def receive(self):
        return self._protocol.receive()

