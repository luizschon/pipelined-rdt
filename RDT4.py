import argparse, Network
from RDT import Packet, debug_log  # For Packet class
from time import sleep, time_ns
from abc import ABC, abstractmethod
from threading import Thread, Semaphore, Lock

ACK  = "1"

class RDT4_Protocol(ABC):
    @abstractmethod
    def send(self, msg: str) -> None:
        pass

    @abstractmethod
    def receive(self) -> bytearray:
        pass


class GoBackN(RDT4_Protocol):
    def __init__(self, role_S: str, server_S: str, port: str):
        self._network = Network.NetworkLayer(role_S, server_S, port)
        self._window_size = 5
        self._timeout_ns = 300_000_000 # 300 milliseconds
        self._recv_buffer = ""

    def disconnect(self):
        self._network.disconnect()

    def __handle_timeout(self):
        self.__start_timer()
        # Resends all packets sent but not ACKed
        for packet in self._packets_in_air:
            self._network.udt_send(packet.get_byte_S())

    def __start_timer(self):
        with self._timeout_lock:
            self._timer_start = time_ns()

    def __stop_timer(self):
        with self._timeout_lock:
            self._timer_start = 0

    def __timer_expired(self) -> bool:
        with self._timeout_lock:
            # If timer_start is 0, then the timer should be considered stopped
            return self._timer_start != 0 and time_ns() > self._timer_start + self._timeout_ns

    def __handle_recv_data(self, data: str):
        packet = Packet.from_byte_S(data)
        # FIXME study what happens if packet is corrupted
        if Packet.corrupt(data) or not packet.is_ack_pack():
            return
        
        with self._seq_num_lock:
            # Verify how many packets were ACKed.
            # FIXME Maybe this can be ambiguous, but checking the next seq num
            # should help a bit. But we should be fine
            if self._base > packet.seq_num:
                packets_acked = self._window_size - self._base + packet.seq_num
            else:
                packets_acked = packet.seq_num - self._base + 1

            # "Move" sliding window to the seq number of the ACK packet
            # resulting in cumulative ACK behaviour
            self._base += packets_acked % self._window_size
            debug_log(f"SENDER: Received ACK for seq {packet.seq_num}")
            debug_log(f"SENDER: Cumulative ACK for {packets_acked} packets")

            # Remove ACKed packets from the from of the "in air" buffer
            self._packets_in_air = self._packets_in_air[packets_acked:]

            if self._base == self._next_seq_num:
                debug_log("SENDER: All packets ACKed, stopped timer")
                self.__stop_timer()  # We are up-to-date with the data sent
            else:
                debug_log("SENDER: Restarted timer")
                self.__start_timer() # Restarts timer
            
            # Releases space in the senders thread window
            self._data_semph.release(packets_acked)

    def __rtd_send(self, msg: str) -> None:
        # Block sender thread from exploding the window size
        self._data_semph.acquire() 

        with self._seq_num_lock:
            packet = Packet(self._next_seq_num, msg)
            self._packets_in_air.append(packet)
            debug_log(f"SENDER: Sent packet seq {self._next_seq_num}")
            self._network.udt_send(packet.get_byte_S())

            # First start of the timer. Subsequent restarts will be handled by 
            # the main thread.
            if self._base == self._next_seq_num:
                debug_log("SENDER: Started timer (likely first time)")
                self.__start_timer()

            self._next_seq_num = (self._next_seq_num + 1) % self._window_size

    def __rtd_receive(self, data: str):
        packet = Packet.from_byte_S(data)
        # Sends ACK for last received seq to notify that the data recv is wrong.
        if Packet.corrupt(data) or packet.seq_num != self._expected_seq_num:
            self._network.udt_send(Packet(self._last_recv_seq_num, ACK).get_byte_S())
        
        # Adds received data to buffer and sends ACK packet.
        self._recv_buffer += packet.msg_S
        self._network.udt_send(Packet(self._expected_seq_num, ACK).get_byte_S())
        self._last_recv_seq_num = self._expected_seq_num
        self._expected_seq_num = (self._expected_seq_num + 1) % self._window_size
        
    def send(self, msg):
        # Initialize control and state variables.
        self._base = 0
        self._next_seq_num = 0
        self._packets_in_air = []
        # Initialize semaphore used to synchronize data being sent.
        self._data_semph = Semaphore(self._window_size)
        # Initialize lock for handling the timeout and seq number control, since
        # the sender and main thread can read/write to it at the same time.
        self._timeout_lock = Lock()
        self._seq_num_lock = Lock()

        # Initialize sender thread
        def sender_task(message):
            # TODO Bufferize message to fit into packets
            buffer = message
            for data in buffer:
                self.__rtd_send(data)

        sender_t = Thread(target=sender_task, args=[msg])
        # Sender thread will send the packets in the background and synchronize
        # the data by itself.
        sender_t.run() 

        # Observes the data being received and the timer.
        # Since in this simulation the layer below (Network Layer) does not
        # notify us when data arrives, we have to pool the information from
        # udt_receive().
        while True:
            with self._seq_num_lock:
                # Exit loop if sender thread sent all data and last ACK was received.
                if not sender_t.is_alive() and self._base == self._next_seq_num:
                    break 

            data_recv = self._network.udt_receive()
            if data_recv != "":
                self.__handle_recv_data(data_recv)

            if self.__timer_expired():
                self.__handle_timeout()

        sender_t.join()

    def receive(self) -> str:
        # Initialize control and state variables.
        self._recv_buffer = ""
        self._expected_seq_num = 0
        self._last_recv_seq_num = 0

        # Continuously pool the data received, since the simulated lower layer
        # (Network Layers) does not notify when data reaches us.
        # TODO Define when receivers job is ended so that the connection can be
        # restarted
        while True:
            data_recv = self._network.udt_receive()
            if data_recv != "":
                self.__rtd_receive(data_recv)

        return self._recv_buffer



class SelectiveRepeat(RDT4_Protocol):
    def __init__(self, role_S, server_S, port):
        self._network = Network.NetworkLayer(role_S, server_S, port)
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


class RDT4:
    def __init__(self, protocol: RDT4_Protocol, role: str, server: str, port: str):
        self._protocol = protocol(role, server, port)

    def send(self, msg):
        self._protocol.send(msg)

    def receive(self):
        return self._protocol.receive()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='RDT$ implementation.')
    parser.add_argument('role', help='Role is either client or server.', choices=['client', 'server'])
    parser.add_argument('server', help='Server.')
    parser.add_argument('port', help='Port.', type=int)
    args = parser.parse_args()

    sim = RDT4("gbn", args.role, args.server, args.port)
    if args.role == 'client':
        sim.send(['MSG_FROM_CLIENT'])
        sleep(2)
        print(sim.receive())
        sim.disconnect()

    else:
        sleep(1)
        print(sim.receive())
        sim.send(['MSG_FROM_SERVER'])
        sim.disconnect()
        
