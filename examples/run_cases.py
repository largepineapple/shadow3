"""Produce actual CLI outputs and traces; never upgrades mock evidence to live."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

CASES = ['clear','conflict','out_of_scope','paraphrase','follow_up','tool_failure',
         'single_document','changed_document','product','ambiguous','transient_failure']


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['mock','live'],required=True)
    parser.add_argument('--prefix')
    parser.add_argument('--cases',nargs='+',choices=CASES,default=CASES)
    args=parser.parse_args()
    prefix=args.prefix or args.mode
    if not prefix.replace('_','').replace('-','').isalnum(): parser.error('Invalid filename prefix')
    summary={'mode':args.mode,'cases':[]}
    started=time.perf_counter()
    for name in args.cases:
        source='clear' if name=='transient_failure' else name
        stem=prefix+'_'+name
        document_file='examples/fixtures/single.json' if name=='single_document' else 'examples/fixtures/changed.json' if name=='changed_document' else 'data/documents.json'
        command=[sys.executable,'-m','src.main','--mode',args.mode,'--input',f'examples/inputs/{source}.json',
                 '--documents',document_file,'--trace',f'examples/traces/{stem}.json','--output',f'examples/outputs/{stem}.json']
        if name in ('tool_failure','transient_failure'):
            command+=['--inject-failure','read_fragment','--failure-mode','once' if name=='transient_failure' else 'always']
        before=time.perf_counter()
        execution=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=600)
        if not execution.stdout: raise RuntimeError(execution.stderr)
        result=json.loads(execution.stdout)
        trace=json.loads(Path(f'examples/traces/{stem}.json').read_text(encoding='utf-8'))
        catalog=json.loads(Path(document_file).read_text(encoding='utf-8'))
        originals={(d['id'],f['id']):(d['version_date'],f['text']) for d in catalog for f in d['fragments']}
        expected={'clear':'answered','conflict':'conflict','out_of_scope':'not_found','paraphrase':'answered',
                  'follow_up':'answered','tool_failure':'tool_failed','single_document':'answered',
                  'changed_document':'answered','product':'answered','ambiguous':'needs_clarification','transient_failure':'answered'}[name]
        checks={'status':result['status']==expected,'not_published':result['published'] is False,
                'exit_code':execution.returncode==(1 if expected=='tool_failed' else 0),
                'source_quotes':all(originals.get((c['document_id'],c['fragment_id']))==(c['version_date'],c['quote']) for c in result['citations']),
                'result_matches_trace':trace['result']==result,
                'loop_observed':any(s['action'] not in ('model_error','finalize_answer') and s['next_action'] is not None for s in trace['steps'])}
        if expected in ('answered','conflict'): checks['has_citations']=bool(result['citations'])
        if name=='conflict':
            checks['both_sides']={c['document_id'] for c in result['citations']}=={'D01','D02'}
            checks['asks_scope']=bool(result['clarifying_question']) and bool(result['conflicts'])
        if name in ('clear','paraphrase','follow_up','transient_failure'):
            checks['right_source']=bool(result['citations']) and result['citations'][0]['document_id']=='D03'
            checks['right_value']='5天' in result['answer']
        if name in ('out_of_scope','tool_failure','ambiguous'): checks['no_unverified_citations']=not result['citations']
        if name in ('tool_failure','transient_failure'): checks['error_observed']=bool(result['tool_errors'])
        if name in ('single_document','changed_document'): checks['document_value']=('30天' if name=='single_document' else '45天') in result['answer']
        entry={'name':name,'input':f'examples/inputs/{source}.json','documents':document_file,
               'status':result['status'],'model':trace['model'],'actions':[s['action'] for s in trace['steps']],
               'checks':checks,'passed':all(checks.values()),'elapsed_seconds':round(time.perf_counter()-before,3)}
        summary['cases'].append(entry)
        summary['elapsed_seconds']=round(time.perf_counter()-started,3)
        Path(f'examples/{prefix}_results.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(entry,ensure_ascii=False),flush=True)
        if trace['steps'] and all(s['action']=='model_error' for s in trace['steps']):
            print('Stopping after actual model connection/response failure',flush=True)
            break
    return 0 if len(summary['cases'])==len(args.cases) and all(c['passed'] for c in summary['cases']) else 1


if __name__=='__main__': raise SystemExit(main())
