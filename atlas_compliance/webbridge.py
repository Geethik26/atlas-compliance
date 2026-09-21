"""Browser adapter: executes the same Python rules and workflow in Pyodide.

The caller persists exported files in a private demo session. No LLM or JS
arithmetic participates in compliance decisions. This is a synthetic-data demo,
not a trusted server-side payroll boundary.
"""
import json
import shutil
import hashlib
from dataclasses import asdict
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from collections import Counter

from .engine import evaluate_employee
from .models import Employee
from .rules import load_rules
from .monitoring import TRUSTED_SOURCES, FetchResponse, monitor_source
from .workflow import (discover_snapshot, approve_proposal, reject_proposal,
                       load_proposals, reevaluate_affected_employees, append_audit)

BOOT = {}

def configure(boot):
    global BOOT
    BOOT = boot

def employees():
    numeric = {'hourly_rate_ast', 'annual_salary_ast', 'scheduled_hours_per_week'}
    return [Employee(**{k: Decimal(v) if k in numeric and v is not None else v
                        for k, v in item.items()}) for item in BOOT['employees']]

def paths(mode):
    if mode not in {'live', 'replay'}:
        raise ValueError('Unknown workspace')
    root = Path(mode)
    root.mkdir(exist_ok=True)
    return root, root/'approved_rules.json', root/'proposed_rules.json', root/'audit.jsonl'

def ingest(mode, source_id, html, fetched_at=None):
    root, registry, proposals, audit = paths(mode)
    source = next(s for s in TRUSTED_SOURCES if s.source_id == source_id)
    clock = datetime.fromisoformat(fetched_at) if fetched_at else datetime.now(timezone.utc)
    result = monitor_source(source, root, fetcher=lambda *_: FetchResponse(html.encode(), 200), now=lambda: clock)
    append_audit(audit, 'SOURCE_CHECKED', source_id=source_id, state=result.state.value,
                 source_hash=result.metadata.sha256, timestamp=clock)
    discovered = discover_snapshot(source, root/result.metadata.snapshot_path, proposals, audit, now=clock)
    status_path = root/'source_status.json'
    statuses = json.loads(status_path.read_text()) if status_path.exists() else {}
    statuses[source_id] = {'state':result.state.value, 'fetched_at':clock.isoformat(),
        'source_url':source.url, 'sha256':result.metadata.sha256,
        'new_proposals':len(discovered), 'error':None}
    status_path.write_text(json.dumps(statuses))

def evaluate(mode, evaluation_date, record=True):
    root, registry, proposals, audit = paths(mode)
    rules = load_rules(registry)
    now = datetime.now(timezone.utc)
    results = [evaluate_employee(e, rules, date.fromisoformat(evaluation_date), evaluated_at=now).to_dict() for e in employees()]
    report = {'record_count':len(results), 'decision_summary':dict(Counter(r['decision_state'] for r in results)), 'results':results}
    if record:
        signature = hashlib.sha256(json.dumps([evaluation_date, json.loads(registry.read_text()), BOOT['employees']], sort_keys=True).encode()).hexdigest()
        report_path=root/'evaluations'/f'{signature}.json'
        if not report_path.exists():
            report_path.parent.mkdir(exist_ok=True)
            report_path.write_text(json.dumps(report))
            append_audit(audit, 'EVALUATION_COMPLETED', evaluation_date=evaluation_date,
                         report_path=str(report_path), decision_summary=report['decision_summary'])
    return report

def view(mode, evaluation_date):
    root, registry, proposals, audit = paths(mode)
    report=evaluate(mode,evaluation_date,False)
    records = [p.to_dict() for p in load_proposals(proposals)]
    approved=json.loads(registry.read_text())
    for p in records:
        p['can_approve'] = p['classification']=='FINAL_RULE' and p['status']=='REVIEW_REQUIRED' and all(p.get(k) is not None for k in ('source_notice_id','jurisdiction','amount','currency','unit','effective_date','coverage'))
        p['revises']=[r['rule_id'] for r in approved if r.get('source_notice_id',r['rule_id'])==p['source_notice_id'] and r['effective_date']==p['effective_date']]
    status_path=root/'source_status.json'
    changes=[json.loads(p.read_text()) for p in sorted((root/'changes').rglob('*.json'))] if (root/'changes').exists() else []
    return {**report,'mode':mode,'evaluation_date':evaluation_date,'proposals':records,'rules':approved,
            'audit':[json.loads(l) for l in audit.read_text().splitlines()] if audit.exists() else [],
            'sources':json.loads(status_path.read_text()) if status_path.exists() else {},'changes':changes}

def dispatch(request_json):
    req=json.loads(request_json)
    mode=req.get('mode','live'); action=req.get('action','view')
    evaluation_date=req.get('evaluation_date',date.today().isoformat())
    date.fromisoformat(evaluation_date)
    root, registry, proposals, audit=paths(mode)
    if action=='restore':
        files=req.get('files',{})
        for workspace in ('live','replay'):
            if Path(workspace).exists(): shutil.rmtree(workspace)
        for name,content in files.items():
            p=Path(name)
            if p.is_absolute() or '..' in p.parts or p.parts[0] not in {'live','replay'}:
                raise ValueError('Invalid saved evidence path')
            p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
        for workspace in ('live','replay'):
            _,r,_,_=paths(workspace)
            if not r.exists():
                r.write_text(json.dumps(BOOT['demo_rules'] if workspace=='replay' else []))
        if not files:
            for source in BOOT['sources']:
                ingest('live',source['source_id'],source['html'],source['fetched_at'])
    elif action=='stage_demo':
        if mode!='replay': raise ValueError('Replay is isolated from live sources')
        ingest(mode,'asteria_federal',BOOT['before'])
        ingest(mode,'asteria_federal',BOOT['after'])
    elif action=='monitor':
        if mode!='live': raise ValueError('Live checks belong to live workspace')
        for item in req['sources']:
            if item.get('error'):
                status_path=root/'source_status.json'
                statuses=json.loads(status_path.read_text()) if status_path.exists() else {}
                old=statuses.get(item['source_id'],{})
                statuses[item['source_id']]={**old,'state':'FETCH_FAILED','error':item['error']}
                status_path.write_text(json.dumps(statuses))
                append_audit(audit,'SOURCE_FETCH_FAILED',source_id=item['source_id'],error=item['error'])
            else:
                ingest(mode,item['source_id'],item['html'],item['fetched_at'])
    elif action in {'approve','reject'}:
        note=req.get('note','').strip()
        if not note: raise ValueError('Enter a review note before deciding')
        if action=='approve':
            approve_proposal(proposals,registry,audit,req['proposal_id'],reviewer_note=note)
            changes=reevaluate_affected_employees(employees(),registry,audit,req['proposal_id'],date.fromisoformat(evaluation_date))
            (root/'latest_reevaluation.json').write_text(json.dumps(changes))
        else: reject_proposal(proposals,audit,req['proposal_id'],reviewer_note=note)
    elif action not in {'view','evaluate'}:
        raise ValueError('Unknown action')
    if action!='view': evaluate(mode,evaluation_date)
    files={str(p):p.read_text() for workspace in ('live','replay') for p in Path(workspace).rglob('*') if p.is_file()}
    return json.dumps({'view':view(mode,evaluation_date),'files':files})
