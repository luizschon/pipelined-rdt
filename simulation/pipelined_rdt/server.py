import argparse, time
from module import PipeRDT, PipeRDT_Protocol
from go_back_n import GoBackN
from selective_repeat import SelectiveRepeat

class RDT4_Server:
    def __init__(self, protocol: PipeRDT_Protocol, port: str) -> None:
        pass

    def send_data(self, data):
        pass

    def receive_data(self) -> str:
        pass

    def recv_close_connection(self):
        pass

    def wait_close_connection(self):
        pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='UPPER CASE server.')
    parser.add_argument('port', help='Port.', type=int)
    args = parser.parse_args()

    timeout = 1000  # close connection if no new data within 5 seconds
    time_of_last_data = time.time()
    server = RDT4_Server(GoBackN, args.port)
    try:
        while not server.recv_close_connection():
            msg = server.receive_data()
            res = msg.upper()
            server.send_data(res)
        server.wait_close_connection()
    except (KeyboardInterrupt, SystemExit):
        print("Ending connection...")
    except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
        print("Ending connection...")
    finally:
        print("Connection ended.")



