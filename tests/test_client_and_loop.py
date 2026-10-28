import io
import json
import urllib.error
from unittest.mock import patch
import pytest
from src.llm_client import LiveClient
from src.agent import Agent
from src.tools import Tools
from src.trace import Trace


def test_http_error_redacts_credentials(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','synthetic-test-credential')
    exc=urllib.error.HTTPError('https://example.invalid',400,'bad',{},io.BytesIO(b'{"error":"synthetic-test-credential sk-synthetic-other"}'))
    with patch('urllib.request.urlopen',side_effect=exc):
        with pytest.raises(RuntimeError) as caught: LiveClient().choose([])
    assert 'synthetic-test-credential' not in str(caught.value)
    assert 'sk-synthetic-other' not in str(caught.value)


def test_deepseek_request_and_tool_response(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','synthetic-test-credential')
    monkeypatch.setenv('OPENAI_BASE_URL','https://api.deepseek.com')
    args={'query':'年假','max_results':3}
    payload={'choices':[{'message':{'tool_calls':[{'id':'c','function':{'name':'search_documents','arguments':json.dumps(args)}}]}}]}
    with patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(payload).encode())) as send:
        assert LiveClient().choose([])==('search_documents',args,'c')
    body=json.loads(send.call_args.args[0].data)
    assert body['thinking']=={'type':'disabled'}
    assert body['parallel_tool_calls'] is False


def test_multiple_tool_calls_rejected(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','synthetic-test-credential')
    payload={'choices':[{'message':{'tool_calls':[{},{}]}}]}
    with patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(payload).encode())):
        with pytest.raises(ValueError,match='exactly one'): LiveClient().choose([])


def test_model_repairs_invalid_quote_from_tool_feedback():
    correct={'document_id':'D03','fragment_id':'F01','quote':'正式员工每年享有5天带薪年假。'}
    wrong=correct|{'quote':'正式员工每年享有10天带薪年假。'}
    actions=iter([
        ('search_documents',{'query':'年假','max_results':3}),
        ('read_fragment',{'document_id':'D03','fragment_id':'F01'}),
        ('finalize_answer',{'mode':'answer','citations':[wrong],'decision_basis':'Wrong proposed quote'}),
        ('finalize_answer',{'mode':'answer','citations':[correct],'decision_basis':'Use actual source'}),
    ])
    class Scripted:
        def choose(self,messages):
            self.messages=messages
            name,args=next(actions)
            return name,args,'call'
    client=Scripted();trace=Trace('mock','scripted-test','repair')
    r={'request_id':'repair','question':'年假几天？','history':[]}
    result=Agent(r,Tools(),client,trace).run()
    assert result['status']=='answered' and '10天' not in result['answer']
    assert trace.value['steps'][2]['observation_summary']['error']['code']=='INVALID_CITATION'
    assert trace.value['steps'][2]['next_action']=='finalize_answer'
    assert any(m['role']=='tool' and 'INVALID_CITATION' in m['content'] for m in client.messages)


def test_model_errors_are_bounded():
    class Invalid:
        def choose(self,messages): return 'execute_code',{},'bad'
    trace=Trace('mock','invalid-test','bad')
    result=Agent({'request_id':'bad','question':'年假几天？','history':[]},Tools(),Invalid(),trace).run()
    assert result['status']=='incomplete'
    assert len(trace.value['steps'])==2
    assert result['citations']==[]
