import sys, argparse
from time import sleep

# Hacky fix to import from parent folder
path_slip = __file__.split('/')
sys.path.append('/'.join(path_slip[0:len(path_slip)-1]) + '/selective_repeat')

from selective_repeat.server import Server
from selective_repeat.client import Client
from log_event import Logger

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Simulation.')
    parser.add_argument('filename', help='File to be transmitted', type=str)
    parser.add_argument('server_port', help='Simulation Port.', type=int)
    parser.add_argument('--vis_port', help='Visualization Port.', type=int, required=False)
    args = parser.parse_args()

    # Response function used by server
    def uppercase(data: str):
        return data.upper()

    try:
        data = []
        with open(args.filename) as f:
            data = f.read()

        server_log = Logger()
        client_log = Logger()
        server = Server('localhost', args.server_port, logger=server_log, response_func=uppercase)
        client = Client('localhost', args.server_port, data, client_log)
        server.start()
        sleep(1)
        client.start()
        client.join()
        server.join()

        vis_data = {
            'server_stats': server.get_stats(),
            'client_stats': client.get_stats(),
            'server_events': [e.export() for e in server.logger.events],
            'client_events': [e.export() for e in client.logger.events],
        }
        print(vis_data)

    except (Exception, KeyboardInterrupt) as err:
        print(err)
