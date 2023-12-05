import argparse, sys
from threading import Thread, Semaphore, Lock
from time import time, sleep
from module import PipeRDT_Protocol, getPackets, ACK

path_slip = __file__.split('/')
sys.path.append('/'.join(path_slip[0:len(path_slip)-2]))
from Network import NetworkLayer
from RDT import Packet, debug_log

class GoBackN(PipeRDT_Protocol):
    def __init__(self, role: str, server: str, port: str):
        self._network = NetworkLayer(role, server, port)
        self._window_size = 10
        self._timeout = 1
        self._recv_buffer = ""
        self._timer_start = 0
        self._role = role

    def disconnect(self):
        debug_log(f"[{self._role}] Disconnecting...")
        self._network.disconnect()

    def __handle_timeout(self):
        debug_log(f"[{self._role}] SENDER: TIMEOUT, going back {len(self._packets_in_air)} packets")
        self.__start_timer()
        # Resends all packets sent but not ACKed
        for packet in self._packets_in_air:
            self._network.udt_send(packet.get_byte_S())

    def __start_timer(self):
        with self._timeout_lock:
            self._timer_start = time()

    def __stop_timer(self):
        with self._timeout_lock:
            self._timer_start = 0

    def __timer_expired(self) -> bool:
        with self._timeout_lock:
            # If timer_start is 0, then the timer should be considered stopped
            return self._timer_start != 0 and time() > self._timer_start + self._timeout

    def __handle_recv_data(self, data: str):
        # FIXME study what happens if packet is corrupted
        packets = getPackets(data)

        for p in packets:
            if not p.is_ack_pack():
                debug_log(f"[{self._role}] SENDER: Expected ACK packet")
                return
            
            with self._seq_num_lock:
                # Verify how many packets were ACKed.
                # FIXME Maybe this can be ambiguous, but checking the next seq num
                # should help a bit. But we should be fine
                debug_log(f"WINDOW: {self._window_size}")
                debug_log(f"BASE: {self._base}")
                debug_log(f"SEQ: {p.seq_num}")

                def to_the_left_of_base():
                    return self._base - p.seq_num == 1 or p.seq_num - self._base == self._window_size - 1

                # Case the whole window has been sent and seq_num is one position
                # to the left of base, then its a retransmission
                if p.seq_num == self._last_seq_num:
                    packets_acked = 0
                elif p.seq_num >= self._base:
                    packets_acked = p.seq_num - self._base + 1
                elif p.seq_num < self._base:
                    packets_acked = self._window_size - self._base + p.seq_num + 1

                # "Move" sliding window to the seq number of the ACK packet
                # resulting in cumulative ACK behaviour
                self._base += packets_acked % self._window_size
                self._last_seq_num = p.seq_num
                debug_log(f"[{self._role}] SENDER: Received ACK for seq {p.seq_num}")
                debug_log(f"[{self._role}] SENDER: Cumulative ACK for {packets_acked} packets")

                # Remove ACKed packets from the from of the "in air" buffer
                self._packets_in_air = self._packets_in_air[packets_acked:]

                if self._packets_in_air is None:
                    debug_log(f"[{self._role}] SENDER: All in-air packets ACKed, stopped timer")
                    self.__stop_timer()  # We are up-to-date with the data sent
                elif packets_acked > 0:
                    debug_log(f"[{self._role}] SENDER: Restarted timer")
                    self.__start_timer() # Restarts timer
                
                # Releases space in the senders thread window
                if packets_acked > 0:
                    self._data_semph.release(packets_acked)

    def __rtd_send(self, msg: str, is_last=False) -> None:
        # Block sender thread from exploding the window size
        self._data_semph.acquire() 

        with self._seq_num_lock:
            packet = Packet(self._next_seq_num, msg, is_last)
            self._packets_in_air.append(packet)

            debug_log(f"[{self._role}] SENDER: Sent packet seq {self._next_seq_num}")
            if is_last:
                debug_log(f"[{self._role}] SENDER: LAST PACKET")

            self._network.udt_send(packet.get_byte_S())

            # First start of the timer. Subsequent restarts will be handled by 
            # the main thread.
            if self._base == self._next_seq_num:
                debug_log(f"[{self._role}] SENDER: Started timer")
                self.__start_timer()

            self._next_seq_num = (self._next_seq_num + 1) % self._window_size

    def __rtd_receive(self, data: str):
        # The data received via udt_receive could contain more than one packet, so
        # we need do separate them, parsing each separately, checking if they are
        # valid, a sending ACK for the latest one (cumulative ACK)
        packets = getPackets(data)

        if len(packets) == 0:
            debug_log(f"[{self._role}] RECVER: No valid packets parsed (corrupted), resending last ACK")

        for p in packets:
            if p.seq_num != self._expected_seq_num:
                debug_log(f"[{self._role}] RECVER: Expected seq num {self._expected_seq_num}, got {p.seq_num}, resending last ACK")
                break

            self._recv_first_packet = True

            # Sets flag if packet received was the last in the stream
            if p.is_fin_pack():
                debug_log(f"[{self._role}] RECVER: Detected FIN flag")
                self._fin_recv = True

            # Adds received data to buffer and sends ACK packet.
            self._recv_buffer += p.msg_S
            self._last_recv_seq_num = self._expected_seq_num
            self._expected_seq_num = (self._expected_seq_num + 1) % self._window_size

        if self._recv_first_packet:
            debug_log(f"[{self._role}] RECVER: Sending ACK for seq num {self._last_recv_seq_num}")
            self._network.udt_send(Packet(self._last_recv_seq_num, ACK).get_byte_S())
       
    def send(self, msg):
        # Initialize control and state variables.
        self._base = 0
        self._next_seq_num = 0
        self._last_seq_num = -1
        self._packets_in_air = []
        # Initialize semaphore used to synchronize data being sent.
        self._data_semph = Semaphore(self._window_size)
        # Initialize lock for handling the timeout and seq number control, since
        # the sender and main thread can read/write to it at the same time.
        self._timeout_lock = Lock()
        self._seq_num_lock = Lock()

        # Initialize sender thread
        def sender_task(message: list):
            # TODO Bufferize message to fit into packets
            buffer = message
            for idx, data in enumerate(buffer):
                self.__rtd_send(data, idx == len(buffer)-1)

        sender_t = Thread(target=sender_task, args=[msg])
        # Sender thread will send the packets in the background and synchronize
        # the data by itself.
        sender_t.start() 

        # Observes the data being received and the timer.
        # Since in this simulation the layer below (Network Layer) does not
        # notify us when data arrives, we have to pool the information from
        # udt_receive().
        while True:
            with self._seq_num_lock:
                # Exit loop if sender thread sent all data and last ACK was received.
                if not sender_t.is_alive() and len(self._packets_in_air) == 0:
                    break 

            data_recv = self._network.udt_receive()
            if data_recv != "":
                self.__handle_recv_data(data_recv)

            if self.__timer_expired():
                self.__handle_timeout()

        # Now all data transfered is up-to-date and ACKed, we should synchronize
        # the termination between client and server.
        # The mechanism takes inspiration in the TCP flow control
        # TODO

        debug_log(f"[{self._role}] SENDER: FINISHED")
        sender_t.join()

    def receive(self) -> str:
        # Initialize control and state variables.
        self._recv_buffer = ""
        self._expected_seq_num = 0
        self._last_recv_seq_num = 0
        self._recv_first_packet = False
        self._fin_recv = False

        # Continuously pool the data received, since the simulated lower layer
        # (Network Layers) does not notify when data reaches us.
        # TODO Define when receivers job is ended so that the connection can be
        # restarted
        while not self._fin_recv:
            data_recv = self._network.udt_receive()
            if data_recv != "":
                print("DATA_RECV: " + data_recv)
                self.__rtd_receive(data_recv)

        return self._recv_buffer


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='RDT4 implementation.')
    parser.add_argument('role', help='Role is either client or server.', choices=['client', 'server'])
    parser.add_argument('server', help='Server.')
    parser.add_argument('port', help='Port.', type=int)
    args = parser.parse_args()

    sim = GoBackN(args.role, args.server, args.port)
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
        