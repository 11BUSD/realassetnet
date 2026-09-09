"""Clerk verifies identity; explicit local mappings grant application membership."""
import json, os, re
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit
from .core import Problem, require, one, safe_user, ROOT


def load_config():
    path=os.environ.get('RAN_IDENTITY_CONFIG')
    data={}
    if path:
        try: data=json.loads(Path(path).read_text(encoding='utf-8'))
        except (OSError,ValueError): raise Problem('Identity configuration unavailable',503)
    require(isinstance(data,dict),'Invalid identity configuration',503)
    return {
        'mode':os.environ.get('RAN_IDENTITY_MODE',data.get('mode','demo')),
        'issuer':os.environ.get('CLERK_ISSUER',data.get('issuer','')),
        'authorized_parties':os.environ.get('CLERK_AUTHORIZED_PARTIES',','.join(data.get('authorized_parties',[]))).split(','),
        'publishable_key':os.environ.get('CLERK_PUBLISHABLE_KEY',data.get('publishable_key','')),
        'secret_key':os.environ.get('CLERK_SECRET_KEY',data.get('secret_key','')),
    }


def validate_config(config):
    require(config.get('mode') in ['demo','clerk'],'Unsupported identity mode',503)
    if config['mode']=='demo': return config
    raw_issuer=config.get('issuer','')
    # This value can become a CSP source; reject whitespace, Unicode, userinfo,
    # wildcards and arbitrary ports rather than relying only on URL parsing.
    require(isinstance(raw_issuer,str) and re.fullmatch(r'https://(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}(?::443)?',raw_issuer),'Clerk issuer must be an ASCII HTTPS hostname (optional port 443)',503)
    issuer=urlsplit(raw_issuer)
    parties=config.get('authorized_parties')
    require(isinstance(parties,list) and bool(parties),'Explicit authorized parties required',503)
    for origin in parties:
        p=urlsplit(origin)
        require('*' not in origin and p.netloc and not p.username and not p.password and p.path=='' and not p.query and not p.fragment and (p.scheme=='https' or (p.scheme=='http' and p.hostname in ['localhost','127.0.0.1'])),'Authorized parties must be exact HTTPS origins (HTTP loopback allowed)',503)
    require(re.fullmatch(r'pk_(test|live)_[A-Za-z0-9_-]+',config.get('publishable_key','')),'Clerk publishable key required',503)
    require(re.fullmatch(r'sk_(test|live)_[A-Za-z0-9_-]+',config.get('secret_key','')),'Clerk secret key required',503)
    require(config['publishable_key'].split('_')[1]==config['secret_key'].split('_')[1],'Clerk key environments differ',503)
    return config


def public_config(config=None):
    config=validate_config(config or load_config())
    enabled=config['mode']=='clerk'
    return {'mode':config['mode'],'publishable_key':config.get('publishable_key') if enabled else None,'issuer':config.get('issuer') if enabled else None,'authorized_parties':list(config.get('authorized_parties',[])) if enabled else [],'configured':enabled,'live_verified':False}


def _sdk_authenticate(request, config):
    # Lazy imports keep the offline demonstration usable without optional packages.
    try:
        from clerk_backend_api.security.authenticaterequest import authenticate_request
        from clerk_backend_api.security.types import AuthenticateRequestOptions
    except ImportError: raise Problem('Clerk SDK unavailable; authentication disabled',503)
    options=AuthenticateRequestOptions(secret_key=config['secret_key'],authorized_parties=config['authorized_parties'],accepts_token=['session_token'],clock_skew_in_ms=5000)
    return authenticate_request(request,options)


def authenticate(headers,url,config=None):
    """Verify a bearer session through Clerk SDK. Missing bearer returns None; invalid denies."""
    config=validate_config(config or load_config())
    require(config['mode']=='clerk','Clerk identity mode is not enabled',503)
    normalized={str(k).lower():v for k,v in headers.items()}
    authorization=normalized.get('authorization')
    if authorization is None: return None
    require(isinstance(authorization,str) and re.fullmatch(r'Bearer [^\s]+',authorization) and len(authorization)<=20000,'Invalid bearer credential',401)
    # Deliberately exclude cookies so cross-site ambient credentials are never accepted.
    request=SimpleNamespace(headers={'Authorization':authorization},url=url)
    try: state=_sdk_authenticate(request,config)
    except Problem: raise
    except Exception: raise Problem('Identity verification unavailable; request denied',503) from None
    require(state.is_signed_in and isinstance(state.payload,dict),'Clerk session invalid or expired',401)
    p=state.payload
    require(p.get('iss')==config['issuer'],'Unexpected identity issuer',401)
    require(p.get('azp') in config['authorized_parties'],'Unauthorized identity origin',401)
    require(isinstance(p.get('sub'),str) and p['sub'].startswith('user_') and isinstance(p.get('sid'),str) and p['sid'].startswith('sess_'),'User session required',401)
    org=organization_context(p)
    return {k:p[k] for k in ['iss','sub','sid','azp'] }|{'org_id':org}


def organization_context(payload):
    """Support verified legacy/v2 organization claims without guessing personal context."""
    legacy=payload.get('org_id')
    modern=payload.get('o')
    ids=[]
    if 'org_id' in payload:
        require(isinstance(legacy,str) and bool(re.fullmatch(r'org_[A-Za-z0-9_-]+',legacy)),'Invalid legacy organization context',401)
        ids.append(legacy)
    if 'o' in payload:
        require(isinstance(modern,dict) and isinstance(modern.get('id'),str) and bool(re.fullmatch(r'org_[A-Za-z0-9_-]+',modern['id'])),'Invalid v2 organization context',401)
        ids.append(modern['id'])
    require(len(set(ids))<=1,'Conflicting organization claims',401)
    return ids[0] if ids else ''


def resolve_user(c,claims):
    if claims is None: return None
    mapping=one(c,"SELECT * FROM external_identities WHERE provider='clerk' AND issuer=? AND subject=?",(claims['iss'],claims['sub']))
    require(mapping and mapping['state']=='ACTIVE','Identity has no active application membership',403)
    u=one(c,'SELECT * FROM users WHERE id=?',(mapping['user_id'],))
    require(u and u['organization_id']==mapping['organization_id'],'Application membership mismatch',403)
    require(mapping['external_organization_id']==claims.get('org_id',''),'Select the explicitly provisioned organization',403)
    require(u['role'] in ['owner','broker','investor','admin'],'Unsupported application role',403)
    return safe_user(u)

