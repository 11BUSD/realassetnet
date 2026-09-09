"""Local operator provisioning. Never derives authorization from Clerk email or metadata."""
import argparse, getpass, json, os, secrets, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core import connect, one, require, audit, now, uid, password_hash, Problem, ROOT
from app.identity import validate_config


def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    cfg=sub.add_parser('configure');cfg.add_argument('--path',required=True);cfg.add_argument('--issuer',required=True);cfg.add_argument('--origin',action='append',required=True);cfg.add_argument('--publishable-key',required=True)
    for name in ['map','revoke','provision-user']:
        cmd=sub.add_parser(name);cmd.add_argument('--db',required=True);cmd.add_argument('--actor-id',required=True)
        if name=='provision-user':
            cmd.add_argument('--organization-id',required=True);cmd.add_argument('--name',required=True);cmd.add_argument('--email',required=True);cmd.add_argument('--role',choices=['broker','owner','investor','admin'],required=True)
        else:
            cmd.add_argument('--issuer',required=True);cmd.add_argument('--subject',required=True)
            if name=='map':cmd.add_argument('--user-id',required=True);cmd.add_argument('--external-organization-id',default='')
    a=p.parse_args()
    if a.command=='configure':
        path=Path(a.path).resolve()
        require(not path.is_relative_to(ROOT.resolve()),'Store identity secrets outside the application directory')
        data={'mode':'clerk','issuer':a.issuer,'authorized_parties':a.origin,'publishable_key':a.publishable_key,'secret_key':getpass.getpass('Clerk secret key (hidden): ')}
        validate_config(data);path.parent.mkdir(parents=True,exist_ok=True)
        # Exclusive create avoids silently replacing another environment's credentials.
        fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as out:json.dump(data,out)
        print('Configuration written. Restrict the file ACL to the service identity and operator. Set RAN_IDENTITY_CONFIG to this file; no live verification was performed.')
        return
    c=connect(a.db)
    try:
        c.execute('BEGIN IMMEDIATE');actor=one(c,'SELECT * FROM users WHERE id=?',(a.actor_id,));require(actor and actor['role']=='admin','Existing application administrator required',403)
        if a.command=='provision-user':
            require(one(c,'SELECT id FROM organizations WHERE id=?',(a.organization_id,)),'Organization must already exist')
            require(a.name.strip() and '@' in a.email and len(a.email)<201,'Valid professional identity fields required')
            ident=uid();c.execute('INSERT INTO users VALUES(?,?,?,?,?,?,?)',(ident,a.organization_id,a.name,a.email.lower(),password_hash(secrets.token_urlsafe(64)),a.role,now()))
            audit(c,actor,ident,'IDENTITY_USER_PROVISIONED',{'role':a.role,'organization_id':a.organization_id,'password_login_not_distributed':True});c.commit();print('Application user created:',ident);return
        require(a.subject.startswith('user_'),'Exact Clerk user subject required')
        if a.command=='map':
            u=one(c,'SELECT * FROM users WHERE id=?',(a.user_id,));require(u,'Application user must be explicitly provisioned first')
            require(not a.external_organization_id or a.external_organization_id.startswith('org_'),'Exact Clerk organization ID required')
            require(not one(c,"SELECT subject FROM external_identities WHERE provider='clerk' AND issuer=? AND subject=?",(a.issuer,a.subject)),'Mapping exists; do not overwrite membership silently',409)
            c.execute('INSERT INTO external_identities(provider,issuer,subject,user_id,organization_id,external_organization_id,state,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)',('clerk',a.issuer,a.subject,u['id'],u['organization_id'],a.external_organization_id,'ACTIVE',actor['id'],now(),now()))
            event='IDENTITY_MEMBERSHIP_MAPPED'
        else:
            require(one(c,"SELECT subject FROM external_identities WHERE provider='clerk' AND issuer=? AND subject=?",(a.issuer,a.subject)),'Mapping not found',404)
            c.execute("UPDATE external_identities SET state='REVOKED',updated_at=? WHERE provider='clerk' AND issuer=? AND subject=?",(now(),a.issuer,a.subject));event='IDENTITY_MEMBERSHIP_REVOKED'
        audit(c,actor,a.subject,event,{'issuer':a.issuer,'operator_provisioned':True});c.commit();print('Identity membership operation recorded.')
    finally:c.close()

if __name__=='__main__':
    try:main()
    except (Problem,OSError) as e:print(e.message if isinstance(e,Problem) else 'Configuration operation failed; check file access and existing paths.',file=sys.stderr);sys.exit(1)
