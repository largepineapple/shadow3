import unicodedata


def normalize(text):
    return ''.join(unicodedata.normalize('NFKC', text).lower().split())


def validate_request(value):
    if not isinstance(value, dict) or set(value) - {'request_id', 'question', 'history'}:
        raise ValueError('Unexpected request fields')
    for field in ('request_id', 'question'):
        if not isinstance(value.get(field), str) or not value[field].strip():
            raise ValueError(field + ' must be a nonempty string')
    history = value.get('history', [])
    if not isinstance(history, list) or len(history) > 20:
        raise ValueError('history must contain at most 20 turns')
    for item in history:
        if not isinstance(item, dict) or set(item) != {'role', 'content'}:
            raise ValueError('Invalid history message')
        if item['role'] not in ('user', 'assistant') or not isinstance(item['content'], str):
            raise ValueError('History roles must be user/assistant; content must be text')
    return {**value, 'history': history}
