stop:
    @killall python3

test-gbn port:
    python3 simulation/pipelined_rdt/go_back_n.py server localhost {{port}} &
    python3 simulation/pipelined_rdt/go_back_n.py client localhost {{port}}

test-sr port:
    python3 simulation/pipelined_rdt/selective_repeat.py server localhost {{port}} &
    python3 simulation/pipelined_rdt/selective_repeat.py client localhost {{port}}

