import sys
from constants import DEBUG

def getChunks(chunk_size: int, data: str) -> list:
    chunks = []

    while len(data) > 0:
        chunks.append(data[:chunk_size])
        data = data[chunk_size:]

    return chunks

def debug_log(message):
    if DEBUG:
        sys.stderr.write(f'{message}\n')
