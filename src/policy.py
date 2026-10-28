import re
from .models import normalize
from .tools import ok, fail


def resolve_topics(request, tools):
    direct = tools.topics_for(request['question'])
    if direct:
        return direct
    question = normalize(request['question'])
    follow_up = any(marker in question for marker in ('那', '这个', '它', '上述', '上面', '刚才')) or bool(re.fullmatch(r'(每年)?(有)?(多少天|几天|多久)[?？。]*', question))
    if follow_up:
        for message in reversed(request['history']):
            if message['role'] == 'user':
                return tools.topics_for(message['content'])
    return set()


class Policy:
    def __init__(self, request, tools):
        self.request, self.tools = request, tools
        self.topics = resolve_topics(request, tools)

    def required(self):
        return {(d['id'], f['id']) for d in self.tools.documents.values() for f in d['fragments'] if f['topic'] in self.topics}

    def conflicts(self):
        groups = {}
        for key in sorted(self.required()):
            if key in self.tools.reads:
                data = self.tools.reads[key]
                groups.setdefault(data['topic'], []).append(data)
        return [{'topic': topic, 'variants': items} for topic, items in groups.items()
                if len({normalize(i['text']) for i in items}) > 1]

    def citations(self, proposed):
        if not isinstance(proposed, list):
            raise ValueError('citations must be an array')
        citations, seen = [], set()
        for item in proposed:
            if not isinstance(item, dict) or set(item) != {'document_id', 'fragment_id', 'quote'} or any(type(v) is not str for v in item.values()):
                raise ValueError('Invalid citation fields')
            key = (item['document_id'], item['fragment_id'])
            data = self.tools.reads.get(key)
            if not data or key not in self.required() or item['quote'] != data['text']:
                raise ValueError('Citation must exactly match the complete relevant fragment actually read')
            if key in seen:
                raise ValueError('Duplicate citation')
            seen.add(key)
            citations.append({k: data[k] for k in ('document_id', 'fragment_id', 'title', 'version_date', 'scope', 'priority', 'content_sha256')} | {'quote': data['text']})
        return citations

    def finalize(self, arguments):
        if not isinstance(arguments, dict) or set(arguments) != {'mode', 'citations', 'decision_basis'}:
            return fail('INVALID_FINAL', 'Unexpected final action fields')
        if arguments['mode'] not in ('answer', 'clarify', 'no_answer') or not isinstance(arguments['decision_basis'], str):
            return fail('INVALID_FINAL', 'Invalid final action')
        try:
            citations = self.citations(arguments['citations'])
        except ValueError as exc:
            return fail('INVALID_CITATION', str(exc))
        searched = any(e['tool'] == 'search_documents' for e in self.tools.events)
        if not searched:
            return fail('SEARCH_REQUIRED', 'Search before ending the task')
        missing = sorted(self.required() - self.tools.reads.keys())
        if missing:
            failed = bool(self.tools.errors)
            if arguments['mode'] == 'no_answer' and failed:
                return ok(self.result('tool_failed', citations, ['检索或原文读取失败，尚有相关片段未核验。'], missing))
            return fail('INCOMPLETE_EVIDENCE', 'Read all related policy variants before concluding', missing_fragments=missing)
        conflicts = self.conflicts()
        if conflicts:
            conflict_keys = {(v['document_id'], v['fragment_id']) for c in conflicts for v in c['variants']}
            cited = {(c['document_id'], c['fragment_id']) for c in citations}
            if arguments['mode'] != 'clarify' or not conflict_keys <= cited:
                return fail('CONFLICT_REQUIRES_CLARIFICATION', 'Cite every conflicting original and ask for applicable policy; never select newer automatically', conflicts=conflicts)
            return ok(self.result('conflict', citations, ['制度条款不一致，未提供足以确定适用制度或优先级的依据。']))
        if arguments['mode'] == 'answer':
            if not self.required() or {self.tools.reads[(c['document_id'], c['fragment_id'])]['topic'] for c in citations} != self.topics:
                return fail('UNSUPPORTED_ANSWER', 'Answer requires original evidence for every question topic')
            return ok(self.result('answered', citations, []))
        if self.required():
            if arguments['mode'] == 'no_answer':
                return fail('EVIDENCE_AVAILABLE', 'Relevant original evidence is available; answer or request clarification')
            return ok(self.result('needs_clarification', citations, ['需要进一步明确问题或适用范围。']))
        if self.tools.errors and not self.tools.searches:
            return ok(self.result('tool_failed', [], ['检索工具失败，不能据此断言资料不存在。']))
        status = 'needs_clarification' if arguments['mode'] == 'clarify' else 'not_found'
        return ok(self.result(status, [], ['当前合成知识库没有已核验且支持该问题的原文。']))

    def result(self, status, citations, gaps, missing=None):
        sources = '\n'.join(f"[{c['document_id']}@{c['version_date']}] {c['quote']}" for c in citations)
        if status == 'answered':
            answer = '根据已核验原文：\n' + sources
            question = None
        elif status == 'conflict':
            answer = '资料存在冲突，当前不能确定唯一答案：\n' + sources
            question = '请确认适用哪份制度，或提供明确的适用范围和优先级。'
        elif status == 'needs_clarification':
            answer = '需要补充信息后才能可靠回答。'
            question = '请明确需要查询的制度、产品问题或适用范围。'
        else:
            answer = '暂时无法提供有依据的答案。'
            question = None
        return {'request_id': self.request['request_id'], 'status': status, 'question': self.request['question'],
                'answer': answer, 'citations': citations, 'knowledge_gaps': gaps,
                'clarifying_question': question, 'conflicts': self.conflicts(),
                'missing_fragments': missing or [], 'tool_errors': self.tools.errors,
                'answer_style': 'verified_extractive', 'published': False}

    def incomplete(self, reason):
        cited = self.citations([{'document_id': d['document_id'], 'fragment_id': d['fragment_id'], 'quote': d['text']}
                                for key, d in self.tools.reads.items() if key in self.required()])
        return self.result('incomplete', cited, [reason], sorted(self.required() - self.tools.reads.keys()))
