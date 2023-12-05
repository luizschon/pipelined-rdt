import argparse, time
from module import PipeRDT, PipeRDT_Protocol
from go_back_n import GoBackN
from selective_repeat import SelectiveRepeat

class RDT4_Client:
    def __init__(self, protocol: PipeRDT_Protocol, port: str) -> None:
        pass

    def send_data(self, data):
        pass

    def receive_data(self) -> str:
        pass

    def close_connection(self):
        pass

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Quotation client talking to a Pig Latin server.')
    parser.add_argument('port', help='Port.', type=int)
    args = parser.parse_args()

    msgs = [
    	'The art of debugging is figuring out what you really told your program to do rather than what you thought you told it to do. -- Andrew Singer', 
    	'The good news about computers is that they do what you tell them to do. The bad news is that they do what you tell them to do. -- Ted Nelson', 
    	'It is hardware that makes a machine fast. It is software that makes a fast machine slow. -- Craig Bruce',
        'The art of debugging is figuring out what you really told your program to do rather than what you thought you told it to do. -- Andrew Singer',
        'The computer was born to solve problems that did not exist before. - Bill Gates']

    timeout = 1000  # send the next message if not response
    time_of_last_data = time.time()
    client = RDT4_Client(GoBackN, args.port)
    try:
        client.send_data(msgs)
        res = client.receive_data()
        print(res)
    except (KeyboardInterrupt, SystemExit):
        print("Ending connection...")
    except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
        print("Ending connection...")
    finally:
        client.close_connection()
        print("Connection ended.")
