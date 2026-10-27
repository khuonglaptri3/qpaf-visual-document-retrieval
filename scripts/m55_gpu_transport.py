"""Return full resource evidence without granting a restricted worker blob access."""
import base64
import gzip
import hashlib
import json
import re

PREFIX = 'QPAF-M55-RESULT:'


def encode_result(result):
    raw = json.dumps(result, sort_keys=True, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    encoded = base64.b64encode(gzip.compress(raw, mtime=0)).decode('ascii')
    parts = [encoded[i:i+3000] for i in range(0, len(encoded), 3000)]
    metadata = {'status': 'LOGGED_RESULT', 'codec': 'gzip-base64-json-v1',
                'sha256': hashlib.sha256(raw).hexdigest(), 'uncompressed_bytes': len(raw),
                'chunk_count': len(parts)}
    return metadata, [f'{PREFIX}{i:06d}:{part}' for i, part in enumerate(parts)]


def decode_result(metadata, messages):
    if (metadata.get('status') != 'LOGGED_RESULT' or metadata.get('codec') != 'gzip-base64-json-v1'
            or type(metadata.get('chunk_count')) is not int or not 1 <= metadata['chunk_count'] <= 100000
            or type(metadata.get('uncompressed_bytes')) is not int
            or not 1 <= metadata['uncompressed_bytes'] <= 64*1024*1024):
        raise ValueError('invalid result transport metadata')
    parts = {}
    # A log message is a stream fragment, not necessarily one complete line.
    for segment in ''.join(messages).split(PREFIX)[1:]:
        try:
            number, remainder = segment.split(':', 1)
            part = remainder.splitlines()[0]
            if not re.fullmatch(r'[0-9]{6}', number) or not re.fullmatch(r'[A-Za-z0-9+/=]+', part):
                raise ValueError('invalid chunk framing')
            index = int(number)
        except (ValueError, TypeError, IndexError) as exc:
            raise ValueError('malformed result chunk') from exc
        if index in parts and parts[index] != part:
            raise ValueError('conflicting result chunks')
        parts[index] = part
    if set(parts) != set(range(metadata['chunk_count'])):
        raise ValueError('result chunks are incomplete or out of range')
    try:
        raw = gzip.decompress(base64.b64decode(''.join(parts[i] for i in range(len(parts))), validate=True))
    except Exception as exc:
        raise ValueError('corrupt encoded result') from exc
    if len(raw) != metadata['uncompressed_bytes'] or hashlib.sha256(raw).hexdigest() != metadata['sha256']:
        raise ValueError('result byte count or SHA256 differs')
    return json.loads(raw)
