from .policy import Policy


class MockPolicy:
    model = 'deterministic-mock-no-LLM'

    def __init__(self, request, tools):
        self.request, self.tools = request, tools
        self.policy = Policy(request, tools)

    def choose(self, messages):
        tools = self.tools
        searches = [e for e in tools.events if e['tool'] == 'search_documents']
        citations = [{'document_id': d['document_id'], 'fragment_id': d['fragment_id'], 'quote': d['text']}
                     for key, d in tools.reads.items() if key in self.policy.required()]
        def finish(mode, basis):
            return 'finalize_answer', {'mode': mode, 'citations': citations, 'decision_basis': basis}, 'mock'
        # Deterministic mock deliberately remains separate from the live client.
        failures = {}
        for event in tools.errors:
            key = (event['tool'], str(event['arguments']))
            failures[key] = failures.get(key, 0) + 1
        if any(count >= 2 for count in failures.values()):
            return finish('no_answer', 'Repeated tool failure; stop without unsupported answer')
        if not searches or not tools.searches:
            return 'search_documents', {'query': self.request['question'], 'max_results': 3}, 'mock'
        missing = sorted(self.policy.required() - tools.reads.keys())
        if missing:
            unread = next((key for key in missing if key in tools.retrieved), None)
            if unread:
                return 'read_fragment', {'document_id': unread[0], 'fragment_id': unread[1]}, 'mock'
            topic = next(f['topic'] for d in tools.documents.values() for f in d['fragments'] if (d['id'], f['id']) == missing[0])
            return 'search_documents', {'query': tools.topics[topic][0], 'max_results': 10}, 'mock'
        if self.policy.conflicts():
            return finish('clarify', 'Verified related originals disagree; scope/priority clarification required')
        if self.policy.required():
            return finish('answer', 'All relevant original fragments read and cited exactly')
        if len(searches) < 2:
            return 'search_documents', {'query': '企业制度或产品FAQ', 'max_results': 10}, 'mock'
        ambiguous = any(marker in self.request['question'] for marker in ('那', '这个', '它'))
        return finish('clarify' if ambiguous else 'no_answer', 'No verified evidence for this question')
