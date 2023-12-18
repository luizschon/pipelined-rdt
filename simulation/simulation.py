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
    parser.add_argument('server_port', help='Simulation Port.', type=int)
    parser.add_argument('vis_port', help='Visualization Port.', type=int)
    parser.add_argument('filename', help='File to be transmitted', type=str)
    args = parser.parse_args()

    try:
        # TODO start connection to visualization app
        data = []
        with open(args.filename) as f:
            data = f.read()

        server_log = Logger('server')
        client_log = Logger('client')
        server = Server('localhost', args.server_port, server_log)
        client = Client('localhost', args.server_port, data, client_log)
        server.start()
        client.start()
        client.join()
        server.join()

    except (Exception, KeyboardInterrupt) as err:
        print(err)