import argparse
import json
import sys
from pathlib import Path
from .models import validate_request
from .tools import Tools
from .llm_client import LiveClient
from .mock_policy import MockPolicy
from .agent import Agent
from .trace import Trace


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='Enterprise knowledge QA; verified source excerpts only')
    parser.add_argument('--mode', choices=['mock', 'live'], required=True)
    parser.add_argument('--input', required=True)
    parser.add_argument('--documents', help='Explicit synthetic catalog JSON override for replacement tests')
    parser.add_argument('--trace', required=True)
    parser.add_argument('--output')
    parser.add_argument('--inject-failure', choices=['search_documents', 'read_fragment'])
    parser.add_argument('--failure-mode', choices=['once', 'always'], default='always')
    parser.add_argument('--max-steps', type=int, default=12)
    parser.add_argument('--max-tool-calls', type=int, default=10)
    args = parser.parse_args()
    trace = Trace(args.mode, 'not_called', 'invalid-request')
    try:
        request = validate_request(json.loads(Path(args.input).read_text(encoding='utf-8-sig')))
        trace.value['case_id'] = request['request_id']
        tools = Tools(args.documents, args.inject_failure, args.failure_mode)
        client = MockPolicy(request, tools) if args.mode == 'mock' else LiveClient()
        trace.value['model'] = client.model
        trace.value['catalog'] = Path(args.documents).name if args.documents else 'documents.json'
        result = Agent(request, tools, client, trace, args.max_steps, args.max_tool_calls).run()
    except Exception as exc:
        result = {'status': 'incomplete', 'answer': '暂时无法提供有依据的答案。', 'citations': [],
                  'knowledge_gaps': [str(exc)], 'tool_errors': [], 'published': False}
    trace.save(args.trace, result)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(rendered, encoding='utf-8')
    return 0 if result['status'] in ('answered', 'conflict', 'not_found', 'needs_clarification') else 1


if __name__ == '__main__':
    raise SystemExit(main())
