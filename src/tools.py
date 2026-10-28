import hashlib
import json
from datetime import date
from pathlib import Path
from .models import normalize


def ok(data):
    return {'ok': True, 'data': data, 'error': None}


def fail(code, message, **details):
    return {'ok': False, 'data': None, 'error': {'code': code, 'message': message, **details}}


class Tools:
    def __init__(self, documents=None, inject_failure=None, failure_mode='always'):
        root = Path(__file__).resolve().parents[1] / 'data'
        self.topics = json.loads((root / 'topics.json').read_text(encoding='utf-8'))
        rows = json.loads(Path(documents or root / 'documents.json').read_text(encoding='utf-8-sig'))
        self.documents = {}
        if not isinstance(rows, list):
            raise ValueError('Document catalog must be a list')
        for row in rows:
            if not isinstance(row.get('id'), str) or not row['id'] or row['id'] in self.documents:
                raise ValueError('Document IDs must be unique nonempty strings')
            date.fromisoformat(row['version_date'])
            if not isinstance(row.get('title'), str) or not isinstance(row.get('fragments'), list):
                raise ValueError('Invalid document metadata')
            ids = set()
            for fragment in row['fragments']:
                if not isinstance(fragment.get('id'), str) or not fragment['id'] or fragment['id'] in ids:
                    raise ValueError('Fragment IDs must be unique within a document')
                if fragment.get('topic') not in self.topics or not isinstance(fragment.get('text'), str) or not fragment['text'].strip():
                    raise ValueError('Invalid topic or empty original text')
                ids.add(fragment['id'])
            self.documents[row['id']] = row
        self.inject_failure, self.failure_mode = inject_failure, failure_mode
        self.failed_once = set()
        self.retrieved, self.reads = set(), {}
        self.searches, self.events, self.errors = [], [], []

    def topics_for(self, query):
        query = normalize(query)
        return {topic for topic, aliases in self.topics.items() if any(normalize(a) in query for a in aliases)}

    def _fault(self, name):
        if self.inject_failure != name:
            return False
        previously = name in self.failed_once
        self.failed_once.add(name)
        return self.failure_mode == 'always' or not previously

    def execute(self, name, arguments):
        schemas = {'search_documents': {'query', 'max_results'}, 'read_fragment': {'document_id', 'fragment_id'}}
        if name not in schemas or not isinstance(arguments, dict) or set(arguments) != schemas[name]:
            return fail('INVALID_ARGUMENT', 'Unknown tool or unexpected arguments')
        if name == 'search_documents':
            if not isinstance(arguments['query'], str) or not arguments['query'].strip() or type(arguments['max_results']) is not int or not 1 <= arguments['max_results'] <= 10:
                return fail('INVALID_ARGUMENT', 'query must be nonempty; max_results must be 1..10')
        elif any(type(v) is not str for v in arguments.values()):
            return fail('INVALID_ARGUMENT', 'Document and fragment IDs must be strings')
        try:
            result = fail('TOOL_UNAVAILABLE', 'Explicit injected failure before reading data') if self._fault(name) else getattr(self, name)(**arguments)
        except Exception as exc:
            result = fail('TOOL_ERROR', str(exc))
        event = {'tool': name, 'arguments': arguments, 'observation': result}
        self.events.append(event)
        if not result['ok']:
            self.errors.append(event)
        return result

    def search_documents(self, query, max_results=3):
        topics = self.topics_for(query)
        matches = []
        for doc in self.documents.values():
            fragments = [f for f in doc['fragments'] if f['topic'] in topics or normalize(doc['id']) == normalize(query)]
            if fragments:
                matches.append({'document_id': doc['id'], 'title': doc['title'], 'version_date': doc['version_date'],
                                'scope': doc.get('scope'), 'priority': doc.get('priority'),
                                'fragments': [{'fragment_id': f['id'], 'topic': f['topic']} for f in fragments]})
        matches.sort(key=lambda x: x['document_id'])
        hits = matches[:max_results]
        self.retrieved.update((h['document_id'], f['fragment_id']) for h in hits for f in h['fragments'])
        data = {'query': query, 'matched_topics': sorted(topics), 'total_matches': len(matches),
                'has_more': len(matches) > len(hits), 'hits': hits}
        self.searches.append(data)
        return ok(data)

    def read_fragment(self, document_id, fragment_id):
        if document_id not in self.documents:
            return fail('NOT_FOUND', 'Unknown document ID')
        doc = self.documents[document_id]
        fragment = next((f for f in doc['fragments'] if f['id'] == fragment_id), None)
        if not fragment:
            return fail('NOT_FOUND', 'Unknown fragment ID')
        if (document_id, fragment_id) not in self.retrieved:
            return fail('SEARCH_REQUIRED', 'Retrieve the fragment metadata before reading it')
        data = {'document_id': document_id, 'fragment_id': fragment_id, 'version_date': doc['version_date'],
                'title': doc['title'], 'scope': doc.get('scope'), 'priority': doc.get('priority'),
                'topic': fragment['topic'], 'text': fragment['text'],
                'content_sha256': hashlib.sha256(fragment['text'].encode()).hexdigest()}
        self.reads[(document_id, fragment_id)] = data
        return ok(data)
