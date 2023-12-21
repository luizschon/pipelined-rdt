# Pipelined RTD

## Running the simulation

```bash
$ python3 simulation/selective_repeat/server.py [server] [port]
$ python3 simulation/selective_repeat/client.py [server] [port] [filename]
```

- File: filename of the file that will be transmitted between server and client.

To disable debug logging, change the DEBUG variable in the simulation/constants.py
file.

The data transmitted is written to stdout, so you can optionally pipe
the response of the server to a file while maintaining the debug log
and final stats of the communication.

```bash
$ python3 simulation/selective_repeat/client.py [server] [port] [filename] 1> output_file
```
