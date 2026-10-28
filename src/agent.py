import json
from .llm_client import SYSTEM, TOOL_PARAMETERS
from .policy import Policy


class Agent:
    def __init__(self, request, tools, client, trace, max_steps=12, max_tool_calls=10):
        self.request, self.tools, self.client, self.trace = request, tools, client, trace
        self.policy = Policy(request, tools)
        self.max_steps, self.max_calls = max_steps, max_tool_calls

    def run(self):
        messages = [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': json.dumps(self.request, ensure_ascii=False)}]
        calls, errors = 0, 0
        for _ in range(self.max_steps):
            try:
                name, arguments, call_id = self.client.choose(messages)
                if name not in TOOL_PARAMETERS or not isinstance(arguments, dict) or set(arguments) != set(TOOL_PARAMETERS[name]):
                    raise ValueError('Unexpected model action or fields')
            except Exception as exc:
                errors += 1
                self.trace.add('model_error', {}, {'error': str(exc)})
                if errors >= 2:
                    return self.policy.incomplete('Model request/response failed: ' + str(exc))
                messages.append({'role': 'user', 'content': 'Previous action invalid or unavailable: ' + str(exc) + ' Return a tool_calls array with EXACTLY ONE element. Do not batch or parallelize calls.'})
                continue
            if calls >= self.max_calls:
                return self.policy.incomplete('max_tool_calls limit reached')
            observation = self.policy.finalize(arguments) if name == 'finalize_answer' else self.tools.execute(name, arguments)
            calls += 1
            self.trace.add(name, arguments, observation, arguments.get('decision_basis', '') if name == 'finalize_answer' else '')
            if name == 'finalize_answer' and observation['ok']:
                return observation['data']
            messages.append({'role': 'assistant', 'content': None, 'tool_calls': [
                {'id': call_id, 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(arguments, ensure_ascii=False)}}]})
            messages.append({'role': 'tool', 'tool_call_id': call_id, 'name': name, 'content': json.dumps(observation, ensure_ascii=False)})
        return self.policy.incomplete('max_steps limit reached')
