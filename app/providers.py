"""Provider evidence receipts and an explicitly authorized, demo-only KYB transport.

Provider evidence never grants eligibility, room access, ownership or settlement.
"""
import hashlib
import hmac
import json
import os
import re
import sqlite3
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from .core import ROOT, Problem, require, uid

CONFIG_PATH=ROOT/'runtime'/'providers.json'
TRULIOO_ENDPOINT='https://api.trulioo.com/v3/business/verify'
MAX_EVENT_BYTES=65536
MAX_SIGNATURE_AGE=300
REGISTRY={
    'signed_review_bridge':{'capability':'SIGNED_PROVIDER_EVIDENCE_RECEIPTS','implementation':'HMAC_BRIDGE_CONTRACT','native_vendor_webhook':False},
    'trulioo_business':{'capability':'BUSINESS_VERIFICATION','implementation':'DEMO_REQUEST_AND_AUTHORIZED_TRANSPORT','native_vendor_webhook':False},
    'title_registry':{'capability':'TITLE_EVIDENCE','implementation':'NOT_IMPLEMENTED'},
    'custody_settlement':{'capability':'CUSTODY_SETTLEMENT','implementation':'NOT_IMPLEMENTED'},
    'appraisal':{'capability':'PROFESSIONAL_VALUATION','implementation':'NOT_IMPLEMENTED'},
}
STATUS_MAP={'pending':'PENDING','match':'MATCH','nomatch':'NO_MATCH','no_match':'NO_MATCH','review_required':'REVIEW_REQUIRED','error':'ERROR','unknown':'UNKNOWN'}

def load_provider_config(path=CONFIG_PATH):
    path=Path(path)
    if not path.exists(): return {}
    try:
        require(path.stat().st_size<=16384,'Provider configuration is invalid',503)
        config=json.loads(path.read_text(encoding='utf-8'))
        require(isinstance(config,dict) and set(config).issubset(REGISTRY) and all(isinstance(value,dict) for value in config.values()),'Provider configuration is invalid',503)
        return config
    except (OSError,ValueError): raise Problem('Provider configuration is unavailable',503)

def env_value(config,field,default):
    name=config.get(field,default)
    require(isinstance(name,str) and re.fullmatch(r'RAN_[A-Z0-9_]{1,100}',name),'Provider environment reference is invalid',503)
    return os.environ.get(name,'')

def provider_status(config=None):
    configuration=load_provider_config() if config is None else config
    require(isinstance(configuration,dict),'Provider configuration is invalid',503)
    providers=[]
    for provider,definition in REGISTRY.items():
        settings=configuration.get(provider,{})
        require(isinstance(settings,dict),'Provider configuration is invalid',503)
        enabled=settings.get('enabled') is True
        credentials=False
        if provider=='signed_review_bridge': credentials=len(env_value(settings,'webhook_secret_env','RAN_REVIEW_BRIDGE_WEBHOOK_SECRET'))>=32
        if provider=='trulioo_business': credentials=bool(env_value(settings,'bearer_token_env','RAN_TRULIOO_BEARER_TOKEN') and env_value(settings,'package_id_env','RAN_TRULIOO_PACKAGE_ID'))
        state='NOT_IMPLEMENTED' if definition['implementation']=='NOT_IMPLEMENTED' else 'DISABLED' if not enabled else 'UNCONFIGURED' if not credentials else 'CONFIGURED_NOT_VALIDATED'
        providers.append({'id':provider,**definition,'state':state,'enabled':enabled and definition['implementation']!='NOT_IMPLEMENTED','credentials_configured':credentials,'outbound_enabled':provider=='trulioo_business' and enabled and credentials and settings.get('outbound_enabled') is True,'account_connection_verified':False,'automatic_eligibility':False,'automatic_financial_mutation':False})
    return {'providers':providers,'external_accounts_verified':False,'live_financial_execution':False}

def identifier(value,name,maximum=128):
    require(isinstance(value,str) and len(value)<=maximum and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]*',value),name+' must be an opaque reference',400)
    return value

def unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise ValueError('Duplicate JSON key')
        result[key]=value
    return result

def strict_json(raw):
    try: return json.loads(raw.decode('utf-8'),object_pairs_hook=unique_object,parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    except (ValueError,UnicodeError,RecursionError): raise Problem('Invalid provider JSON',400)

def normalized_status(value):
    require(isinstance(value,str) and 0<len(value)<=64 and re.fullmatch(r'[A-Za-z0-9_-]+',value),'Provider status is invalid',400)
    return STATUS_MAP.get(value.lower(),'UNKNOWN')

def ingest_event(c,provider,rawbody,headers,config=None,now_epoch=None):
    """Accept our normalized bridge format, not any vendor's undocumented native signature."""
    require(provider=='signed_review_bridge','Native provider webhook contract is not implemented',404)
    settings=load_provider_config().get(provider,{}) if config is None else config
    require(isinstance(settings,dict) and settings.get('enabled') is True,'Provider receipts are disabled',503)
    secret=env_value(settings,'webhook_secret_env','RAN_REVIEW_BRIDGE_WEBHOOK_SECRET')
    require(len(secret)>=32,'Provider receipt signing key is not configured',503)
    require(isinstance(rawbody,bytes) and 0<len(rawbody)<=MAX_EVENT_BYTES,'Provider body exceeds limit or is empty',413)
    require(hasattr(headers,'items'),'Provider signature headers are required',401)
    signed_headers={}
    for name,value in headers.items():
        lower=name.lower()
        if lower in {'x-ran-event-timestamp','x-ran-event-signature'}:
            require(lower not in signed_headers,'Duplicate provider signature header',401);signed_headers[lower]=value
    timestamp=signed_headers.get('x-ran-event-timestamp','');signature=signed_headers.get('x-ran-event-signature','')
    require(isinstance(timestamp,str) and re.fullmatch(r'[1-9][0-9]{8,11}',timestamp),'Invalid provider signature timestamp',401)
    require(isinstance(signature,str) and re.fullmatch(r'sha256=[0-9a-f]{64}',signature),'Invalid provider signature format',401)
    epoch=time.time() if now_epoch is None else now_epoch
    require(abs(epoch-int(timestamp))<=MAX_SIGNATURE_AGE,'Provider signature timestamp is stale or in the future',401)
    expected=hmac.new(secret.encode('utf-8'),timestamp.encode('ascii')+b'.'+rawbody,hashlib.sha256).hexdigest()
    require(hmac.compare_digest(expected,signature[7:]),'Invalid provider signature',401)
    body=strict_json(rawbody)
    fields={'event_id','subject_reference','event_type','occurred_at','result'}
    require(isinstance(body,dict) and set(body)==fields,'Provider event fields are invalid',400)
    event_id=identifier(body['event_id'],'event_id');subject=identifier(body['subject_reference'],'subject_reference')
    require(isinstance(body['event_type'],str) and body['event_type'] in {'BUSINESS_VERIFICATION_RESULT','IDENTITY_VERIFICATION_RESULT','DOCUMENT_CHECK_RESULT'},'Provider event type is unsupported',400)
    result=body['result'];require(isinstance(result,dict) and set(result)=={'status','reference'},'Provider result fields are invalid',400)
    reference=identifier(result['reference'],'result reference');status=normalized_status(result['status'])
    try:
        require(isinstance(body['occurred_at'],str) and len(body['occurred_at'])<=40,'Invalid provider event time',400)
        occurred=datetime.fromisoformat(body['occurred_at'].replace('Z','+00:00'))
        require(occurred.tzinfo is not None and occurred.timestamp()<=epoch+MAX_SIGNATURE_AGE,'Invalid provider event time',400)
    except ValueError: raise Problem('Invalid provider event time',400)
    digest=hashlib.sha256(rawbody).hexdigest()
    prior=c.execute('SELECT id,payload_sha256,normalized_json FROM provider_events WHERE provider=? AND event_id=?',(provider,event_id)).fetchone()
    if prior:
        require(hmac.compare_digest(prior[1],digest),'Provider event identifier reused with different payload',409)
        return {'receipt_id':prior[0],'replayed':True,'event':json.loads(prior[2]),'eligibility_changed':False,'financial_mutation':False}
    normalized={'provider':provider,'event_id':event_id,'subject_reference':subject,'event_type':body['event_type'],'provider_status':result['status'],'normalized_status':status,'provider_reference':reference,'occurred_at':occurred.astimezone(timezone.utc).isoformat(),'signature_verified':True,'source_kind':'CONFIGURED_REVIEW_BRIDGE','human_review_required':True,'eligibility_decision':'NOT_MADE','financial_execution':'DISABLED'}
    receipt=uid();received=datetime.fromtimestamp(epoch,timezone.utc).isoformat()
    inserted=c.execute('INSERT INTO provider_events(id,provider,event_id,subject_reference,event_type,provider_status,normalized_status,occurred_at,received_at,payload_sha256,provider_timestamp,normalized_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(provider,event_id) DO NOTHING',(receipt,provider,event_id,subject,body['event_type'],result['status'],status,normalized['occurred_at'],received,digest,int(timestamp),json.dumps(normalized,sort_keys=True,separators=(',',':'))))
    if inserted.rowcount==0:
        prior=c.execute('SELECT id,payload_sha256,normalized_json FROM provider_events WHERE provider=? AND event_id=?',(provider,event_id)).fetchone()
        require(prior and hmac.compare_digest(prior[1],digest),'Provider event identifier reused with different payload',409)
        return {'receipt_id':prior[0],'replayed':True,'event':json.loads(prior[2]),'eligibility_changed':False,'financial_mutation':False}
    return {'receipt_id':receipt,'replayed':False,'event':normalized,'eligibility_changed':False,'financial_mutation':False}

def prepare_trulioo_business(data,config=None):
    settings=load_provider_config().get('trulioo_business',{}) if config is None else config
    require(isinstance(settings,dict),'Provider configuration is invalid',503)
    require(isinstance(data,dict) and set(data)=={'business_name','business_registration_number','jurisdiction_of_incorporation','customer_reference','synthetic'},'Business verification request fields are invalid',400)
    require(data['synthetic'] is True,'Only explicitly synthetic Demo requests are supported',403)
    def business_text(field,maximum):
        value=data[field]
        require(isinstance(value,str) and 0<len(value.strip())<=maximum and not any(ord(ch)<32 for ch in value),field+' is invalid',400)
        return value.strip()
    package=env_value(settings,'package_id_env','RAN_TRULIOO_PACKAGE_ID')
    require(bool(re.fullmatch(r'[A-Za-z0-9_-]{1,36}',package)),'Trulioo package ID is not configured',503)
    request={'VerificationType':'Demo','PackageId':package,'CountryCode':'CA','CustomerReferenceID':identifier(data['customer_reference'],'customer_reference'),'ConsentForDataSources':[],'BusinessDataFields':{'BusinessName':business_text('business_name',200),'BusinessRegistrationNumber':business_text('business_registration_number',100),'JurisdictionOfIncorporation':business_text('jurisdiction_of_incorporation',30),'EnhancedProfile':False,'Entities':False},'VerboseMode':False}
    raw=json.dumps(request,sort_keys=True,separators=(',',':')).encode('utf-8')
    return {'provider':'trulioo_business','method':'POST','url':TRULIOO_ENDPOINT,'body':request,'request_sha256':hashlib.sha256(raw).hexdigest(),'mode':'DEMO_ONLY','requires_domain_authorization':True,'transmitted':False}

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,file,code,message,headers,newurl): raise urllib.error.HTTPError(request.full_url,code,'Provider redirects are refused',headers,None)

def execute_trulioo_business(data,authorization_reference,authorized_payload_sha256,config=None):
    """Trusted server-only call; caller must first record explicit Action Gateway authorization.

    No HTTP route invokes this function automatically. It neither creates an approval nor retries.
    """
    settings=load_provider_config().get('trulioo_business',{}) if config is None else config
    require(isinstance(settings,dict) and settings.get('enabled') is True and settings.get('outbound_enabled') is True,'Provider outbound execution is disabled',503)
    identifier(authorization_reference,'authorization_reference')
    prepared=prepare_trulioo_business(data,settings)
    require(isinstance(authorized_payload_sha256,str) and hmac.compare_digest(prepared['request_sha256'],authorized_payload_sha256),'Approved provider request digest does not match',403)
    token=env_value(settings,'bearer_token_env','RAN_TRULIOO_BEARER_TOKEN')
    require(bool(token) and len(token)<=16384 and not any(ord(ch)<33 or ord(ch)>126 for ch in token),'Trulioo bearer token is not configured or invalid',503)
    raw=json.dumps(prepared['body'],sort_keys=True,separators=(',',':')).encode('utf-8')
    request=urllib.request.Request(TRULIOO_ENDPOINT,data=raw,method='POST',headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','Accept':'application/json'})
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect(),urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    try:
        with opener.open(request,timeout=20) as response:
            require(response.status==200,'Provider returned an unsupported status',502)
            response_raw=response.read(1048577);require(len(response_raw)<=1048576,'Provider response exceeds limit',502)
    except urllib.error.HTTPError as error: raise Problem('Provider request failed with HTTP '+str(error.code)+'; no automatic retry performed',502)
    except (urllib.error.URLError,TimeoutError,OSError): raise Problem('Provider request outcome is unknown; no automatic retry performed',502)
    try: result=strict_json(response_raw)
    except Problem: raise Problem('Provider response was not valid JSON',502)
    require(isinstance(result,dict),'Provider response was not an object',502)
    record=result.get('Record');record=record if isinstance(record,dict) else {}
    raw_status=record.get('RecordStatus','unknown')
    try: status=normalized_status(raw_status)
    except Problem: status='UNKNOWN'
    reference=record.get('TransactionRecordID') or result.get('TransactionID')
    reference=reference if isinstance(reference,str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}',reference) else None
    return {'provider':'trulioo_business','mode':'DEMO_ONLY','authorization_reference':authorization_reference,'request_sha256':prepared['request_sha256'],'response_sha256':hashlib.sha256(response_raw).hexdigest(),'provider_reference':reference,'normalized_status':status,'human_review_required':True,'eligibility_changed':False,'financial_mutation':False,'raw_response_stored':False}
