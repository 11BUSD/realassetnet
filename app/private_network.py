"""Explicitly configured, operator-gated, read-only private research adapter."""
import hashlib
import hmac
import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from .core import ROOT, Problem, audit, require

DEFAULT_CONFIG = ROOT/'runtime'/'private-network.json'
CONTACT_MAX_AGE_DAYS = 30
ORG_MAX_AGE_DAYS = 90
QUEUE_LIMIT = 50
BLOCKED = {'CONTACTED','REPLIED','MEETING','QUALIFIED','ONBOARDING','PARTNER','NOT_NOW','DO_NOT_CONTACT'}
REQUIRED_TABLES = {'organizations','people','sources','mandates','organization_roles','scores','network_factors','outreach_queue','contacts','trigger_events','relationships','interaction_history'}
ORG_FIELDS = ['organization_id','legal_name','brand_name','website','organization_type','country','Canada_presence','UK_presence','description','asset_classes','strategies','fit_score','network_multiplier_score','priority_tier','why_this_counterparty','value_proposition','best_contact_role','relationship_status','legal_operational_status','last_verified','verification_state','confidence','source_urls','network_group_id']

def external_database(path, public_root=ROOT):
    """Resolve links and reject any source inside the public application, including runtime."""
    try: resolved=Path(path).expanduser().resolve(strict=True)
    except (OSError,RuntimeError,TypeError,ValueError): raise Problem('Private research database is unavailable',503)
    require(resolved.is_file() and not resolved.is_relative_to(Path(public_root).resolve()),'Private research database must be outside the public project',400)
    return resolved

def read_connection(path, public_root=ROOT):
    resolved=external_database(path,public_root)
    connection=None
    try:
        connection=sqlite3.connect(resolved.as_uri()+'?mode=ro',uri=True,timeout=5)
        connection.row_factory=sqlite3.Row
        connection.execute('PRAGMA query_only=ON')
        connection.execute('PRAGMA trusted_schema=OFF')
        tables={r['name'] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND sql NOT LIKE 'CREATE VIRTUAL TABLE%'")}
        if not REQUIRED_TABLES.issubset(tables):
            connection.close();raise Problem('Private research schema is unsupported',503)
        # Defense in depth beyond mode=ro: no attachment, schema changes, PRAGMA or mutation.
        allowed={sqlite3.SQLITE_SELECT,sqlite3.SQLITE_READ,sqlite3.SQLITE_FUNCTION,sqlite3.SQLITE_TRANSACTION}
        connection.set_authorizer(lambda action,arg1,arg2,db,trigger: sqlite3.SQLITE_OK if action in allowed and db in (None,'main') else sqlite3.SQLITE_DENY)
        connection.execute('BEGIN')
        return connection
    except sqlite3.Error:
        if connection: connection.close()
        raise Problem('Private research database could not be opened read-only',503)

def load_config(config_path=DEFAULT_CONFIG):
    path=Path(config_path)
    if not path.exists(): return None
    try:
        require(path.stat().st_size<16384,'Private network configuration is invalid',503)
        config=json.loads(path.read_text(encoding='utf-8'))
        digest=config.get('operator_key_sha256','')
        require(config.get('version')==1 and isinstance(config.get('database'),str) and isinstance(digest,str) and len(digest)==64 and all(ch in '0123456789abcdef' for ch in digest),'Private network configuration is invalid',503)
        return config
    except (OSError,ValueError,AttributeError): raise Problem('Private network configuration is invalid',503)

def age_days(value,as_of):
    if not isinstance(value,str): return None
    try: return (as_of-date.fromisoformat(value[:10])).days
    except ValueError: return None

def current(value,as_of,maximum):
    age=age_days(value,as_of)
    return age is not None and 0<=age<=maximum

def select(connection,sql,args=()): return [dict(row) for row in connection.execute(sql,args)]

def queue_view(connection,as_of):
    candidates=select(connection,"""SELECT q.queue_id,q.organization_id,q.person_id,q.priority,q.angle,q.reason,
      q.value_proposition,q.recommended_ask,q.contact_channel,q.status,q.prepared_at,q.not_before,q.next_action,
      o.brand_name AS organization,o.fit_score,o.network_group_id,o.relationship_status,
      o.last_verified AS organization_verified_at,o.verification_state AS organization_verification,
      p.full_name AS person,p.title,p.role_category AS role,p.location AS city,
      p.verification_state AS person_verification,p.last_verified AS person_verified_at,
      ct.value AS contact_value,ct.channel AS verified_channel,ct.verification_state AS contact_verification,
      ct.last_verified AS contact_verified_at,ct.consent_status,ct.deliverability_status,
      cs.url AS contact_source,s.url AS source,t.trigger,t.event_date AS trigger_date,
      t.verification_state AS trigger_verification,ts.url AS trigger_source
      FROM outreach_queue q JOIN organizations o ON o.organization_id=q.organization_id
      LEFT JOIN people p ON p.person_id=q.person_id AND p.organization_id=q.organization_id
      LEFT JOIN contacts ct ON ct.contact_id=q.contact_id AND ct.organization_id=q.organization_id AND ct.person_id=q.person_id
      LEFT JOIN sources cs ON cs.source_id=ct.source_id LEFT JOIN sources s ON s.source_id=q.source_id
      LEFT JOIN trigger_events t ON t.trigger_id=q.trigger_id LEFT JOIN sources ts ON ts.source_id=t.source_id
      WHERE q.status IN ('READY','RESEARCH') ORDER BY q.priority,o.fit_score DESC,q.queue_id""")
    latest={}
    for item in select(connection,'SELECT organization_id,person_id,status_after FROM interaction_history WHERE status_after IS NOT NULL ORDER BY occurred_at DESC,interaction_id DESC'):
        latest.setdefault((item['organization_id'],item['person_id']),item['status_after'])
    selected=[];seen=set()
    for row in candidates:
        if row['relationship_status'] in BLOCKED or latest.get((row['organization_id'],None)) in BLOCKED or latest.get((row['organization_id'],row['person_id'])) in BLOCKED: continue
        if row['consent_status'] in {'DO_NOT_CONTACT','DECLINED','WITHDRAWN'}: continue
        if row['not_before'] and (age_days(row['not_before'],as_of) is None or age_days(row['not_before'],as_of)<0): continue
        group=row['network_group_id'] or row['organization_id']
        if group in seen: continue
        fresh=(row['contact_verification']=='VERIFIED' and row['person_verification']=='VERIFIED'
            and current(row['contact_verified_at'],as_of,CONTACT_MAX_AGE_DAYS)
            and current(row['person_verified_at'],as_of,CONTACT_MAX_AGE_DAYS)
            and row['organization_verification']=='VERIFIED' and current(row['organization_verified_at'],as_of,ORG_MAX_AGE_DAYS)
            and bool(row['contact_value']) and row['verified_channel']==row['contact_channel'] and bool(row['contact_source']))
        row['stored_status']=row['status'];row['verified_contact']=row.pop('contact_value') if fresh else None
        # Never expose an unverified/stale value under the verified-contact key.
        row.pop('contact_value',None)
        if not fresh:
            row['status']='RESEARCH';row['next_action']='Reverify professional role, contact channel and source freshness before any outreach preparation.'
        row['contact_is_current']=bool(fresh);row['as_of']=as_of.isoformat()
        row['send_authorization']='NOT_SUPPORTED_READ_ONLY';row['outreach_enabled']=False
        if not row['trigger']: row['trigger']='UNKNOWN'
        selected.append(row);seen.add(group)
        if len(selected)>=QUEUE_LIMIT: break
    return selected

def snapshot(connection,as_of):
    organizations=select(connection,'SELECT '+','.join(ORG_FIELDS)+' FROM organizations ORDER BY fit_score DESC,brand_name LIMIT 1000')
    by_id={item['organization_id']:item for item in organizations}
    for item in organizations:
        item['roles']=[];item['score_breakdown']=[];item['network_factors']=[]
        item['current_verification']=item['verification_state'] if current(item['last_verified'],as_of,ORG_MAX_AGE_DAYS) else 'STALE'
        for field in ('asset_classes','strategies','source_urls'):
            try: item[field]=json.loads(item[field]) if item[field] else []
            except (ValueError,TypeError): pass
    for row in select(connection,'SELECT organization_id,role FROM organization_roles ORDER BY role'):
        if row['organization_id'] in by_id: by_id[row['organization_id']]['roles'].append(row['role'])
    for table,field in [('scores','score_breakdown'),('network_factors','network_factors')]:
        for row in select(connection,f'SELECT f.*,s.url AS source_url FROM {table} f LEFT JOIN sources s ON s.source_id=f.source_id'):
            if row['organization_id'] in by_id: by_id[row['organization_id']][field].append(row)
    relationships=select(connection,"""SELECT r.*,a.brand_name AS from_organization,b.brand_name AS to_organization,s.url AS source_url
      FROM relationships r JOIN sources s ON s.source_id=r.source_id
      JOIN organizations a ON a.organization_id=r.from_organization_id JOIN organizations b ON b.organization_id=r.to_organization_id
      WHERE r.verification_state='VERIFIED' AND r.relationship_scope='EXTERNAL_DOCUMENTED' AND length(s.url)>0
      ORDER BY r.relationship_id LIMIT 1000""")
    for item in relationships: item['current_verification']='VERIFIED' if current(item['last_verified'],as_of,ORG_MAX_AGE_DAYS) else 'STALE'
    queue=queue_view(connection,as_of)
    counts={table:connection.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in ('organizations','people','sources','mandates')}
    counts.update(documented_relationships=len(relationships),queue=len(queue))
    return {'mode':'PRIVATE_READ_ONLY','as_of':as_of.isoformat(),'summary':counts,'organizations':organizations,'organizations_truncated':counts['organizations']>len(organizations),'queue':queue,'relationships':relationships,'outreach_enabled':False,'legal_operational_status':'NOT_ASSESSED','limitations':['Research verification is not consent, legal qualification, available capital or a partnership.','No data is copied into the public application database. Contacts and organization roles need renewed verification as they age.','This connector provides research views only; no matching, sending or financial execution is enabled.']}

def handle(c,u,method,path,d,key,config_path=DEFAULT_CONFIG):
    require(u and u.get('role')=='admin','Operator administrator required',403)
    require(method=='GET','Private network connector is read-only',405)
    require(path in {'/api/network','/api/network/status'},'Private network endpoint not found',404)
    config=load_config(config_path)
    if path.endswith('/status'): return {'configured':bool(config),'key_required':True,'mode':'PRIVATE_READ_ONLY','outreach_enabled':False}
    require(config is not None,'Private network connector is not configured',503)
    supplied=key if isinstance(key,str) and len(key)<=1024 else ''
    require(hmac.compare_digest(hashlib.sha256(supplied.encode()).hexdigest(),config['operator_key_sha256']),'Operator key required or invalid',403)
    connection=None
    try:
        connection=read_connection(config['database'])
        result=snapshot(connection,datetime.now(timezone.utc).date())
        if c is not None: audit(c,u,'private-network','PRIVATE_NETWORK_READ',{'mode':'PRIVATE_READ_ONLY','organization_count':result['summary']['organizations'],'contact_values_logged':False})
        return result
    except sqlite3.Error: raise Problem('Private research schema could not be read',503)
    finally:
        if connection: connection.close()
