import base64, binascii, hashlib, hmac, json, math, re, secrets, sqlite3, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from .packs import TORONTO_MARKET, POLICY_VERSION, AGENTS

ROOT = Path(__file__).resolve().parents[1]
def now(): return datetime.now(timezone.utc).isoformat()
def uid(): return secrets.token_hex(12)
def js(x): return json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False)
def rows(c, sql, args=()): return [dict(r) for r in c.execute(sql, args)]
def one(c, sql, args=()):
    r = c.execute(sql, args).fetchone()
    return dict(r) if r else None
class Problem(Exception):
    def __init__(self, message, status=400): self.message, self.status = message, status
def require(ok, message, status=400):
    if not ok: raise Problem(message, status)
def number(value, name, low=0, high=1e12):
    require(not isinstance(value, bool), f'{name} must be numeric')
    try: value = float(value)
    except (TypeError, ValueError): raise Problem(f'{name} must be numeric')
    require(math.isfinite(value) and low <= value <= high, f'{name} must be between {low} and {high}')
    return value
def cents(v): return int((Decimal(str(number(v,'amount',0,1e10))) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
def text(v, name, maximum=200):
    require(isinstance(v,str) and 0 < len(v.strip()) <= maximum, f'{name} is required (maximum {maximum} characters)')
    return v.strip()
def connect(path):
    c = sqlite3.connect(path, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    c.execute('PRAGMA journal_mode=WAL')
    return c
def migrate(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    c=connect(path)
    exists=c.execute("SELECT name FROM sqlite_master WHERE name='schema_versions'").fetchone()
    if not exists:
        c.executescript((ROOT/'migrations/001_core.sql').read_text())
        c.execute('INSERT INTO schema_versions VALUES(1,?)',(now(),));c.commit()
    if not one(c,'SELECT version FROM schema_versions WHERE version=2'):
        c.executescript((ROOT/'migrations/002_reconciliation.sql').read_text())
        c.execute('INSERT INTO schema_versions VALUES(2,?)',(now(),));c.commit()
    if not one(c,'SELECT version FROM schema_versions WHERE version=3'):
        c.executescript((ROOT/'migrations/003_private_intake.sql').read_text())
        c.execute('INSERT INTO schema_versions VALUES(3,?)',(now(),));c.commit()
    if not one(c,'SELECT version FROM schema_versions WHERE version=4'):
        c.executescript((ROOT/'migrations/004_integrations.sql').read_text())
        c.execute('INSERT INTO schema_versions VALUES(4,?)',(now(),));c.commit()
    c.close()
def password_hash(password, salt=None):
    salt=salt or secrets.token_hex(16)
    return salt+':'+hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),310000).hex()
def check_password(password, encoded): return hmac.compare_digest(password_hash(password,encoded.split(':')[0]),encoded)
def audit(c, actor, resource, event, details):
    previous=one(c,'SELECT event_hash FROM audit_events ORDER BY seq DESC LIMIT 1')
    record={'id':uid(),'actor_id':actor['id'],'organization_id':actor.get('organization_id'),'resource_id':resource,'event':event,'details':js(details),'previous_hash':previous['event_hash'] if previous else 'GENESIS','created_at':now()}
    digest=hashlib.sha256(js(record).encode()).hexdigest()
    c.execute('INSERT INTO audit_events(id,actor_id,organization_id,resource_id,event,details,previous_hash,event_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?)',tuple(record[k] for k in ['id','actor_id','organization_id','resource_id','event','details','previous_hash'])+(digest,record['created_at']))
def integrity(c):
    prev='GENESIS'
    for r in rows(c,'SELECT * FROM audit_events ORDER BY seq'):
        digest=r.pop('event_hash'); r.pop('seq')
        if r['previous_hash']!=prev or hashlib.sha256(js(r).encode()).hexdigest()!=digest: return False
        prev=digest
    return True
def safe_user(u): return {k:u[k] for k in ['id','organization_id','name','email','role']}
def signup(c,d):
    name=text(d.get('name'),'name');email=text(d.get('email'),'email').lower()
    require(re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email),'Invalid email')
    password=text(d.get('password'),'password',200);require(len(password)>=12,'Use at least 12 password characters')
    role=d.get('role','broker');require(role in ['broker','owner','investor'],'Role cannot be self-provisioned',403)
    require(not one(c,'SELECT id FROM users WHERE email=?',(email,)),'Account already exists',409)
    org=uid();user=uid()
    c.execute('INSERT INTO organizations VALUES(?,?,1)',(org,text(d.get('organization') or name+' demo organization','organization')))
    c.execute('INSERT INTO users VALUES(?,?,?,?,?,?,?)',(user,org,name,email,password_hash(password),role,now()))
    u=one(c,'SELECT * FROM users WHERE id=?',(user,));audit(c,u,user,'SIGNUP',{'role':role,'mode':'DEMO'})
    return safe_user(u)
def login(c,d):
    u=one(c,'SELECT * FROM users WHERE email=?',(str(d.get('email','')).lower(),))
    require(u and check_password(str(d.get('password','')),u['password_hash']),'Email or password is incorrect',401)
    token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
    c.execute('INSERT INTO sessions VALUES(?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),u['id'],csrf,time.time()+8*3600))
    audit(c,u,u['id'],'LOGIN',{'mode':'DEMO'})
    return {'user':safe_user(u),'csrf':csrf},token
def session(c,token):
    s=one(c,'SELECT * FROM sessions WHERE token_hash=? AND expires_at>?',(hashlib.sha256(token.encode()).hexdigest(),time.time()))
    return (safe_user(one(c,'SELECT * FROM users WHERE id=?',(s['user_id'],))),s['csrf']) if s else (None,None)
def property_access(c,u,pid,write=False):
    require(u,'Sign in to continue',401)
    p=one(c,'SELECT * FROM properties WHERE id=?',(pid,));require(p,'Property not found',404)
    own=p['organization_id']==u['organization_id']
    if write: require(own and u['role'] in ['broker','owner'],'Only the originating organization may edit this property',403)
    else:
        grant=one(c,'SELECT * FROM room_grants WHERE user_id=? AND property_id=?',(u['id'],pid))
        require(u['role']=='admin' or own or (grant and grant['level']>=3),'Approved data-room access required',403)
    return p
def add_claim(c,u,pid,field,value,artifact=None,source='Structured intake'):
    cid=uid();version=c.execute('SELECT count(*)+1 FROM claims WHERE property_id=? AND field=?',(pid,field)).fetchone()[0]
    c.execute('INSERT INTO claims VALUES(?,?,?,?,?,?,?,?,?,?)',(cid,pid,artifact,field,js(value),'SOURCE_PROVIDED',u['id'],source,version,now()))
    return cid
def confirm_claim(c,u,pid,cid):
    p=property_access(c,u,pid,True);require(p['state'] not in ['PUBLISHED'],'Published evidence is frozen; create a new reviewed revision',409)
    claim=one(c,'SELECT * FROM claims WHERE id=? AND property_id=?',(cid,pid));require(claim,'Claim not found',404)
    if claim['artifact_id']:
        a=one(c,'SELECT * FROM artifacts WHERE id=?',(claim['artifact_id'],));require(a['state']=='PARSED','Quarantined evidence cannot be confirmed',409)
    c.execute('INSERT OR IGNORE INTO claim_confirmations VALUES(?,?,?,?)',(uid(),cid,u['id'],now()))
    audit(c,u,pid,'CLAIM_CONFIRMED',{'claim_id':cid,'source_unchanged':True});return {'confirmed':cid}
def create_property(c,u,d):
    require(u and u['role'] in ['broker','owner'],'Broker or owner role required',403)
    city=text(d.get('city','Toronto'),'city');require(city in TORONTO_MARKET['cities'],'City outside Toronto Market Pack')
    typ=d.get('property_type','MULTIFAMILY');require(typ in TORONTO_MARKET['property_types'],'Unsupported V0 property type')
    classification=d.get('data_classification','DEMO_SYNTHETIC')
    require(classification in ['DEMO_SYNTHETIC','REAL_PRIVATE'],'Invalid data classification')
    real=classification=='REAL_PRIVATE'
    require(not real or d.get('rights_attested') is True,'Confirm your authority to provide this information for private review')
    source=text(d.get('source_reference'),'source_reference',1000) if real else 'Synthetic contributor intake'
    units=number(d.get('units'), 'units',1,10000);require(units.is_integer(),'Units must be an integer')
    price=number(d.get('asking_price'),'asking_price',1,1e10);pid=uid()
    c.execute('INSERT INTO properties VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(pid,u['organization_id'],u['id'],text(d.get('address'),'address'),city,typ,int(units),price,text(d.get('description') or ('Private real-property submission; unverified' if real else 'Synthetic Toronto property'),'description',3000),'DRAFT',0 if real else 1,1,now()))
    c.execute('INSERT INTO property_intake_records VALUES(?,?,?,?,?,?)',(pid,classification,source,int(real),u['id'],now()))
    add_claim(c,u,pid,'asking_price',price,source=source);add_claim(c,u,pid,'units',units,source=source)
    audit(c,u,pid,'PROPERTY_CREATED',{'previous_state':None,'new_state':'DRAFT','authorization':'originating organization','synthetic':not real,'source_reference':source,'rights_attestation':'contributor statement, not verification' if real else 'synthetic'})
    agent_run(c,u,pid,'intake',{'property_id':pid},[],['Ownership and encumbrances UNKNOWN'])
    return {'property':one(c,'SELECT * FROM properties WHERE id=?',(pid,))}
def agent_run(c,u,pid,agent,output,refs,missing=None,contradictions=None):
    property_record=one(c,'SELECT synthetic FROM properties WHERE id=?',(pid,))
    classification='DEMO/SYNTHETIC' if property_record and property_record['synthetic'] else 'PRIVATE CONTRIBUTOR DATA; NOT VERIFIED'
    envelope={'agent_identity':agent,'model_version':'deterministic-rules/0.1.0','input_references':refs,'source_references':refs,'structured_output':output,'confidence':{'type':'rule_execution','value':1,'meaning':'Execution confidence, not factual accuracy'},'assumptions':[classification,'No external model or network call'],'missing_information':missing or [],'contradictions':contradictions or [],'proposed_actions':[],'timestamp':now()}
    c.execute('INSERT INTO agent_runs VALUES(?,?,?,?,?)',(uid(),pid,agent,js(envelope),now()))
    audit(c,u,pid,'AGENT_PROPOSAL',{'agent':agent,'model':'deterministic-rules/0.1.0','source_references':refs})
def upload(c,u,pid,d):
    p=property_access(c,u,pid,True);require(p['state']!='PUBLISHED','Published property requires new revision',409)
    filename=text(d.get('filename'),'filename',120);content=d.get('content')
    text(content,'content',200000) # Validate without normalizing the accepted evidence payload.
    require(Path(filename).name==filename and not any(x in filename for x in ['\\','/',':','\x00']),'Invalid filename')
    require(Path(filename).suffix.lower() in ['.txt','.csv'],'Only UTF-8 text and CSV are enabled. PDF/Office/image scanning adapters are not connected.',415)
    require(not any(ord(ch)<32 and ch not in '\n\r\t' for ch in content),'Binary/control characters rejected',415)
    findings=[]
    if re.search(r'ignore.{0,40}(instructions|previous)|system\s*prompt|<script|javascript:|powershell|cmd\.exe|BEGIN.*PRIVATE KEY|X5O!P%@AP',content,re.I|re.S): findings.append('SUSPICIOUS_ACTIVE_CONTENT_OR_INSTRUCTION')
    aid=uid();state='QUARANTINED' if findings else 'PARSED'
    c.execute('INSERT INTO artifacts VALUES(?,?,?,?,?,?,?,?,?,?)',(aid,pid,u['id'],filename,hashlib.sha256(content.encode()).hexdigest(),content,state,js(findings),1,now()))
    ids=[]
    if not findings:
        for lineno,line in enumerate(content.splitlines(),1):
            match=re.fullmatch(r'\s*(annual_gross_rent|annual_expenses|vacancy_rate|asking_price|units)\s*[:,=]\s*([0-9]+(?:\.[0-9]+)?)\s*',line)
            if match:
                field,value=match.group(1),float(match.group(2))
                number(value,field,0,1 if field=='vacancy_rate' else 1e10)
                ids.append(add_claim(c,u,pid,field,value,aid,f'{filename}:line {lineno}'))
    audit(c,u,pid,'EVIDENCE_UPLOADED',{'artifact_id':aid,'sha256':hashlib.sha256(content.encode()).hexdigest(),'state':state,'previous_state':'RECEIVED','authorization':'tenant write','reason':'allowlist parser; no code execution'})
    agent_run(c,u,pid,'document-parser',{'claim_ids':ids,'security_findings':findings},[aid],['User confirmation required'] if ids else ['No supported fields extracted'])
    return {'artifact':one(c,'SELECT id,filename,sha256,state,security_findings FROM artifacts WHERE id=?',(aid,)),'claims':rows(c,'SELECT * FROM claims WHERE artifact_id=?',(aid,))}
def upload_binary(c,u,pid,d):
    p=property_access(c,u,pid,True);require(p['state']!='PUBLISHED','Published records are frozen',409)
    filename=text(d.get('filename'),'filename',120)
    require(Path(filename).name==filename and not any(ch in filename for ch in ['\\','/',':','\x00']),'Invalid filename')
    suffix=Path(filename).suffix.lower()
    types={'.pdf':('application/pdf',b'%PDF-'),'.docx':('application/vnd.openxmlformats-officedocument.wordprocessingml.document',b'PK'),'.xlsx':('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',b'PK'),'.png':('image/png',b'\x89PNG\r\n\x1a\n'),'.jpg':('image/jpeg',b'\xff\xd8'),'.jpeg':('image/jpeg',b'\xff\xd8')}
    require(suffix in types,'Only PDF, DOCX, XLSX, PNG and JPEG may enter quarantine',415)
    encoded=d.get('content_base64');require(isinstance(encoded,str) and len(encoded)<=7000000,'Binary payload exceeds 5 MB limit',413)
    try:raw=base64.b64decode(encoded,validate=True)
    except (ValueError,binascii.Error):raise Problem('Invalid base64 encoding')
    require(0<len(raw)<=5*1024*1024,'Binary payload exceeds 5 MB limit',413)
    mime,magic=types[suffix];require(raw.startswith(magic),'File signature does not match selected type',415)
    aid=uid();digest=hashlib.sha256(raw).hexdigest();findings=['SCANNER_NOT_CONFIGURED','NO_PARSING_OR_PREVIEW_PERFORMED']
    c.execute('INSERT INTO artifacts VALUES(?,?,?,?,?,?,?,?,?,?)',(aid,pid,u['id'],filename,digest,'','QUARANTINED',js(findings),1,now()))
    c.execute('INSERT INTO artifact_blobs VALUES(?,?,?,?)',(aid,sqlite3.Binary(raw),len(raw),mime))
    audit(c,u,pid,'EVIDENCE_QUARANTINED',{'artifact_id':aid,'sha256':digest,'byte_length':len(raw),'previous_state':'RECEIVED','new_state':'QUARANTINED','reason':'Scanner unavailable; fail closed','policy':POLICY_VERSION})
    return {'artifact':{'id':aid,'filename':filename,'sha256':digest,'state':'QUARANTINED','security_findings':findings,'byte_length':len(raw)},'claims':[],'message':'Original file retained privately. No parser or preview ran. Scanner integration is required before release.'}
def evidence_state(c,pid):
    claims=rows(c,'SELECT c.*,EXISTS(SELECT 1 FROM claim_confirmations f WHERE f.claim_id=c.id) AS confirmed FROM claims c WHERE property_id=? ORDER BY created_at',(pid,))
    values={};refs={};conflicts=[];stale=[]
    cutoff=datetime.now(timezone.utc)-timedelta(days=TORONTO_MARKET['evidence_max_age_days'])
    for r in claims:
        r['value']=json.loads(r['value_json']);r['verification']='USER_CONFIRMED' if r['confirmed'] else 'UNVERIFIED'
        if datetime.fromisoformat(r['created_at'])<cutoff: stale.append(r['id']);r['verification']='STALE'
    for field in {r['field'] for r in claims}:
        group=[r for r in claims if r['field']==field]
        if len({r['value_json'] for r in group})>1:
            decision=one(c,'SELECT * FROM claim_reconciliations WHERE property_id=? AND field=? ORDER BY created_at DESC LIMIT 1',(pid,field))
            if decision and set(json.loads(decision['considered_claim_ids']))=={r['id'] for r in group}:
                group=[r for r in group if r['id']==decision['selected_claim_id']]
                group[0]['reconciliation_id']=decision['id']
            else:
                conflicts.append({'field':field,'claim_ids':[r['id'] for r in group],'state':'CONFLICTING'})
                continue
        confirmed=[r for r in group if r['confirmed'] and r['id'] not in stale]
        if confirmed: values[field]=confirmed[-1]['value'];refs[field]=[r['id'] for r in confirmed]
    missing=[f for f in TORONTO_MARKET['required_underwriting'] if f not in values]
    return claims,values,refs,conflicts,missing,stale
def risk_state(c,pid):
    claims,values,refs,conflicts,missing,stale=evidence_state(c,pid)
    asset=rows(c,'SELECT * FROM asset_claims WHERE property_id=?',(pid,))
    return {'missing_fields':missing,'contradictions':conflicts,'stale_claims':stale,'ownership':'UNKNOWN','encumbrance_clearance':'UNKNOWN','legal_priority':'NOT_DETERMINED','asset_claim_overlap':len(asset)>1,'asset_claims_require_legal_review':bool(asset),'evidence_completeness':round(100*(4-len(missing))/4),'quarantined_artifacts':c.execute("SELECT count(*) FROM artifacts WHERE property_id=? AND state='QUARANTINED'",(pid,)).fetchone()[0]}
def underwrite(c,u,pid,d):
    p=property_access(c,u,pid,True)
    require(p['state']!='PUBLISHED','Published underwriting is frozen; a reviewed revision is required',409)
    require(p['property_type'] not in ['LAND','DEVELOPMENT'],'Land and development need a separate feasibility model; income-property underwriting is unavailable',409)
    claims,values,refs,conflicts,missing,stale=evidence_state(c,pid)
    require(not conflicts,'Conflicting claims require human reconciliation; originals are preserved',409)
    require(not missing,'Confirm required evidence: '+', '.join(missing),409)
    a=TORONTO_MARKET['defaults']|d
    for k,lo,hi in [('rate',0,0.3),('amortization_years',1,40),('ltv',0,0.95),('cap_rate',0.001,0.3),('reserves',0,1e8)]: a[k]=number(a[k],k,lo,hi)
    require(a['amortization_years'].is_integer(),'Amortization must be whole years')
    price=number(values['asking_price'],'asking_price',1);loan=price*a['ltv'];monthly=a['rate']/12;n=a['amortization_years']*12
    debt=(loan/n if monthly==0 else loan*monthly/(-math.expm1(-n*math.log1p(monthly))))*12
    definitions={'downside':{'rent_multiplier':0.9,'expense_multiplier':1.1,'vacancy_delta':0.05,'cap_delta':0.01},'base':{'rent_multiplier':1,'expense_multiplier':1,'vacancy_delta':0,'cap_delta':0},'upside':{'rent_multiplier':1.05,'expense_multiplier':1,'vacancy_delta':-0.01,'cap_delta':-0.0025}}
    results={}
    for name,s in definitions.items():
        vacancy=max(0,min(1,values['vacancy_rate']+s['vacancy_delta']))
        effective=values['annual_gross_rent']*s['rent_multiplier']*(1-vacancy)
        noi=effective-values['annual_expenses']*s['expense_multiplier'];cash=noi-debt-a['reserves'];equity=price-loan
        results[name]={'effective_gross_income':round(effective,2),'noi':round(noi,2),'annual_debt_service':round(debt,2),'loan_amount':round(loan,2),'ltv':a['ltv'],'dscr':round(noi/debt,4) if debt else None,'cash_flow_after_reserves':round(cash,2),'cash_yield':round(cash/equity,4) if equity else None,'model_estimate':round(noi/max(0.001,a['cap_rate']+s['cap_delta']),2),'reserves':a['reserves'],'category':'REALASSETNET_CALCULATED'}
    sid=uid();c.execute('INSERT INTO underwriting_snapshots VALUES(?,?,?,?,?,?,?,?,?,?,?)',(sid,pid,u['id'],js(values),js(refs),'noi-amortization/1.0.0',js(a),js(definitions),js(results),'UNREVIEWED',now()))
    for name,val in results['base'].items(): c.execute('INSERT INTO derived_metrics VALUES(?,?,?,?,?)',(uid(),sid,name,js(val),'noi-amortization/1.0.0'))
    c.execute('INSERT INTO model_estimates VALUES(?,?,?,?,?,?)',(uid(),pid,'capitalization/1.0.0',js(refs),js({'value':results['base']['model_estimate'],'category':'REALASSETNET_ESTIMATE','not_appraisal':True}),now()))
    audit(c,u,pid,'UNDERWRITING_SNAPSHOT_CREATED',{'snapshot_id':sid,'formula_version':'noi-amortization/1.0.0','input_references':refs})
    agent_run(c,u,pid,'underwriting',{'snapshot_id':sid},[r for rr in refs.values() for r in rr])
    return {'snapshot':snapshot_view(one(c,'SELECT * FROM underwriting_snapshots WHERE id=?',(sid,)))}
def snapshot_view(s):
    for k in ['input_values','evidence_refs','assumptions','scenarios','results']: s[k]=json.loads(s[k])
    return s
def public_property(c,p):
    u=one(c,'SELECT name FROM users WHERE id=?',(p['created_by'],))
    # Published financial labels are pinned to the reviewed snapshot; intake is not authoritative.
    if p['state']=='PUBLISHED':
        s=one(c,'SELECT input_values FROM underwriting_snapshots WHERE property_id=? ORDER BY created_at DESC LIMIT 1',(p['id'],))
        if s:
            approved=json.loads(s['input_values']);p=p|{'asking_price':approved.get('asking_price'),'units':approved.get('units')}
    return {k:p[k] for k in ['id','address','city','property_type','units','asking_price','description','synthetic','state']}|{'originator':u['name'],'asking_price_label':'Contributor asking price; not appraisal or NAV','offering_access':'SEPARATE_APPROVAL_REQUIRED'}
def room(c,u,pid):
    p=property_access(c,u,pid);audit(c,u,pid,'DISCLOSE_INFORMATION',{'level':3,'policy':POLICY_VERSION,'fields':'authorized room projection','decision':'ALLOW'})
    deal=one(c,'SELECT * FROM deals WHERE property_id=? ORDER BY created_at DESC LIMIT 1',(pid,))
    return {'property':p,'claims':evidence_state(c,pid)[0],'artifacts':rows(c,'SELECT id,filename,sha256,state,security_findings,version,created_at FROM artifacts WHERE property_id=?',(pid,)),'snapshots':[snapshot_view(s) for s in rows(c,'SELECT * FROM underwriting_snapshots WHERE property_id=? ORDER BY created_at DESC',(pid,))],'risks':risk_state(c,pid),'requests':rows(c,'SELECT * FROM evidence_requests WHERE property_id=?',(pid,)),'deal':deal,'offering':one(c,'SELECT * FROM offerings WHERE deal_id=?',(deal['id'],)) if deal else None,'grants':rows(c,'SELECT user_id,level FROM room_grants WHERE property_id=?',(pid,)) if u['role']=='admin' else [],'asset_claims':rows(c,'SELECT * FROM asset_claims WHERE property_id=?',(pid,)),'opinions':rows(c,'SELECT * FROM professional_opinions WHERE property_id=?',(pid,)),'estimates':rows(c,'SELECT * FROM model_estimates WHERE property_id=?',(pid,))}
