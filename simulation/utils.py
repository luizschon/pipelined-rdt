import sys
from constants import DEBUG
from textwrap import wrap

def getChunks(chunk_size: int, data: str) -> list:
    chunks = []

    while len(data) > 0:
        chunks.append(data[:chunk_size])
        data = data[chunk_size:]

    return chunks

def debug_log(message):
    if DEBUG:
        sys.stderr.write('\n'.join(wrap(message, width=64)) + '\n')
