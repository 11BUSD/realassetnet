from .core import *

KINDS={'OPPORTUNITY','CAPITAL_REQUEST'}
ASSET_CLASSES={'REAL_ESTATE','ART_COLLECTIBLE','OTHER_PRIVATE_ASSET'}
JURISDICTIONS={'CA-ON','GB-ENG','US-FL','OTHER'}
INTENTS={'ACQUISITION','DISPOSITION','FINANCING','REFINANCING','DILIGENCE','ADVISORY'}

def mandate_projection(m, mine=False):
    common={k:m[k] for k in ['id','kind','asset_class','asset_subtype','jurisdiction','market','intent','timeline','state','created_at']}
    if mine:
        return common|{k:m[k] for k in ['property_id','value_min','value_max','currency','requirements','data_classification','rights_attested','consent_to_matching','updated_at']}
    # This is the only matching-pool projection. Identity, address, source,
    # pricing, requirements, and property linkage are intentionally absent.
    return common|{'redacted':True,'value_band':'Withheld until mutual acceptance'}

def create_mandate(c,u,d):
    kind=d.get('kind');require(kind in KINDS,'Choose an opportunity or capital request')
    asset_class=d.get('asset_class');require(asset_class in ASSET_CLASSES,'Unsupported asset class')
    jurisdiction=d.get('jurisdiction');require(jurisdiction in JURISDICTIONS,'Choose a supported market context')
    intent=d.get('intent');require(intent in INTENTS,'Choose a mandate intent')
    classification=d.get('data_classification','DEMO_SYNTHETIC');require(classification in {'DEMO_SYNTHETIC','REAL_PRIVATE'},'Invalid data classification')
    real=classification=='REAL_PRIVATE';require(not real or d.get('rights_attested') is True,'Confirm authority to provide private information')
    prop=d.get('property_id') or None
    if prop: property_access(c,u,prop,True)
    lo=number(d['value_min'],'value_min',0,1e12) if d.get('value_min') not in [None,''] else None
    hi=number(d['value_max'],'value_max',0,1e12) if d.get('value_max') not in [None,''] else None
    require(lo is None or hi is None or lo<=hi,'value_min cannot exceed value_max')
    mid=uid();stamp=now()
    values=(mid,u['organization_id'],u['id'],prop,kind,asset_class,text(d.get('asset_subtype'),'asset_subtype',80),jurisdiction,text(d.get('market'),'market',100),intent,lo,hi,d.get('currency','CAD') if d.get('currency','CAD') in {'CAD','USD','GBP'} else None,text(d.get('timeline'),'timeline',120),text(d.get('requirements'),'requirements',2000),classification,int(real),0,'DRAFT',stamp,stamp)
    require(values[12] is not None,'Unsupported currency')
    c.execute('INSERT INTO mandates VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',values)
    audit(c,u,mid,'MANDATE_CREATED',{'state':'DRAFT','classification':classification,'rights_attestation':'contributor statement, not verification' if real else 'synthetic','property_linked':bool(prop),'execution':'INTRODUCTION_ONLY'})
    return {'mandate':mandate_projection(one(c,'SELECT * FROM mandates WHERE id=?',(mid,)),True)}

def submit_mandate(c,u,mid,d):
    m=one(c,'SELECT * FROM mandates WHERE id=?',(mid,));require(m,'Mandate not found',404)
    require(m['organization_id']==u['organization_id'],'Only the originating organization may submit this mandate',403)
    require(m['state']=='DRAFT','Only a draft mandate may be submitted',409)
    require(d.get('consent_to_matching') is True,'Explicit consent is required before a mandate enters redacted matching')
    c.execute("UPDATE mandates SET state='SUBMITTED',consent_to_matching=1,updated_at=? WHERE id=?",(now(),mid))
    audit(c,u,mid,'MANDATE_SUBMITTED',{'state':'SUBMITTED','matching_projection':'REDACTED','automatic_outreach':False,'consent':'explicit'})
    return {'mandate':mandate_projection(one(c,'SELECT * FROM mandates WHERE id=?',(mid,)),True)}

def list_mandates(c,u):
    mine=rows(c,'SELECT * FROM mandates WHERE organization_id=? ORDER BY created_at DESC',(u['organization_id'],))
    available=rows(c,"SELECT * FROM mandates WHERE state='SUBMITTED' AND consent_to_matching=1 AND organization_id<>? ORDER BY created_at DESC",(u['organization_id'],))
    matches=rows(c,"SELECT mm.*,l.organization_id left_org,r.organization_id right_org,l.id left_id,r.id right_id,l.asset_class asset_class,l.jurisdiction jurisdiction FROM mandate_matches mm JOIN mandates l ON l.id=mm.left_mandate_id JOIN mandates r ON r.id=mm.right_mandate_id WHERE l.organization_id=? OR r.organization_id=? ORDER BY mm.created_at DESC",(u['organization_id'],u['organization_id']))
    for x in matches:
        x['my_side']='LEFT' if x['left_org']==u['organization_id'] else 'RIGHT'
        x['counterparty_mandate']=x['right_id'] if x['my_side']=='LEFT' else x['left_id']
        x['can_respond']=x['state'] in {'PROPOSED','LEFT_ACCEPTED','RIGHT_ACCEPTED'} and not (x['state']=='LEFT_ACCEPTED' and x['my_side']=='LEFT') and not (x['state']=='RIGHT_ACCEPTED' and x['my_side']=='RIGHT')
    invites=rows(c,"SELECT i.*,l.asset_class,l.jurisdiction,p.address FROM mandate_room_invitations i JOIN mandate_matches mm ON mm.id=i.match_id JOIN mandates l ON l.id=mm.left_mandate_id JOIN properties p ON p.id=i.property_id WHERE i.invited_user_id=? ORDER BY i.created_at DESC",(u['id'],))
    return {'mine':[mandate_projection(m,True) for m in mine],'available':[mandate_projection(m) for m in available],'matches':matches,'invitations':invites,'notice':'Matching is reviewer-proposed. No outreach or evidence disclosure occurs automatically.'}

def propose_match(c,u,mid,d):
    require(u['role']=='admin','Independent reviewer required',403)
    left=one(c,'SELECT * FROM mandates WHERE id=?',(mid,));right=one(c,'SELECT * FROM mandates WHERE id=?',(d.get('counterparty_mandate_id'),))
    require(left and right,'Both mandates must exist',404)
    require(left['id']!=right['id'] and left['organization_id']!=right['organization_id'],'A match requires separate organizations')
    require(left['state']=='SUBMITTED' and right['state']=='SUBMITTED' and left['consent_to_matching'] and right['consent_to_matching'],'Both mandates require explicit matching consent',409)
    require(left['asset_class']==right['asset_class'] and left['jurisdiction']==right['jurisdiction'],'Asset class and jurisdiction context must align for reviewer proposal')
    a,b=sorted([left['id'],right['id']]);match=uid();reason=text(d.get('rationale'),'rationale',1000)
    c.execute('INSERT INTO mandate_matches VALUES(?,?,?,?,?,?,?,?,?)',(match,a,b,u['id'],reason,'PROPOSED',None,None,now()))
    audit(c,u,match,'MANDATE_MATCH_PROPOSED',{'left_mandate_id':a,'right_mandate_id':b,'identity_disclosure':'NOT_AUTHORIZED','automatic_outreach':False})
    return {'match_id':match,'state':'PROPOSED'}

def respond_match(c,u,match_id,d):
    m=one(c,'SELECT mm.*,l.organization_id left_org,r.organization_id right_org FROM mandate_matches mm JOIN mandates l ON l.id=mm.left_mandate_id JOIN mandates r ON r.id=mm.right_mandate_id WHERE mm.id=?',(match_id,));require(m,'Match not found',404)
    side='left' if m['left_org']==u['organization_id'] else 'right' if m['right_org']==u['organization_id'] else None;require(side,'Only a proposed party may respond',403)
    require(m['state'] in {'PROPOSED','LEFT_ACCEPTED','RIGHT_ACCEPTED'},'Match is no longer awaiting acceptance',409)
    accepted=d.get('accepted') is True
    if not accepted:
        c.execute("UPDATE mandate_matches SET state='DECLINED' WHERE id=?",(match_id,));audit(c,u,match_id,'MANDATE_MATCH_DECLINED',{'side':side.upper(),'identity_disclosure':'NOT_AUTHORIZED'});return {'state':'DECLINED'}
    own=f'{side}_accepted_at';other='right_accepted_at' if side=='left' else 'left_accepted_at';state='MUTUALLY_ACCEPTED' if m[other] else ('LEFT_ACCEPTED' if side=='left' else 'RIGHT_ACCEPTED')
    c.execute(f'UPDATE mandate_matches SET {own}=?,state=? WHERE id=?',(now(),state,match_id))
    audit(c,u,match_id,'MANDATE_MATCH_ACCEPTED',{'side':side.upper(),'state':state,'identity_disclosure':'AUTHORIZED_ONLY_AFTER_BILATERAL_ACCEPTANCE' if state=='MUTUALLY_ACCEPTED' else 'NOT_AUTHORIZED'})
    return {'state':state}

def create_room_invitation(c,u,match_id,d):
    require(u['role']=='admin','Independent reviewer required',403)
    m=one(c,'SELECT * FROM mandate_matches WHERE id=?',(match_id,));require(m and m['state']=='MUTUALLY_ACCEPTED','Mutual acceptance is required before an evidence-room invitation',409)
    pid=text(d.get('property_id'),'property_id',100);p=one(c,'SELECT * FROM properties WHERE id=?',(pid,));require(p,'Property not found',404)
    recipient=one(c,'SELECT * FROM users WHERE id=?',(d.get('invited_user_id'),));require(recipient,'Invitee not found',404)
    left=one(c,'SELECT organization_id FROM mandates WHERE id=?',(m['left_mandate_id'],));right=one(c,'SELECT organization_id FROM mandates WHERE id=?',(m['right_mandate_id'],))
    require(recipient['organization_id'] in {left['organization_id'],right['organization_id']} and recipient['organization_id']!=p['organization_id'],'Invitee must be an accepted counterparty, not the property originator',403)
    iid=uid();c.execute('INSERT INTO mandate_room_invitations VALUES(?,?,?,?,?,?,?,?,?)',(iid,match_id,pid,recipient['id'],u['id'],3,'PENDING',now(),None))
    audit(c,u,iid,'EVIDENCE_ROOM_INVITED',{'match_id':match_id,'property_id':pid,'invitee':recipient['id'],'state':'PENDING','disclosure':'AWAITING_INVITEE_ACCEPTANCE'})
    return {'invitation_id':iid,'state':'PENDING'}

def accept_room_invitation(c,u,iid):
    i=one(c,'SELECT * FROM mandate_room_invitations WHERE id=?',(iid,));require(i,'Invitation not found',404)
    require(i['invited_user_id']==u['id'],'Only the named invitee may accept this invitation',403);require(i['state']=='PENDING','Invitation is no longer pending',409)
    c.execute("UPDATE mandate_room_invitations SET state='ACCEPTED',accepted_at=? WHERE id=?",(now(),iid))
    c.execute('INSERT OR REPLACE INTO room_grants(user_id,property_id,level,granted_by,created_at) VALUES(?,?,?,?,?)',(u['id'],i['property_id'],i['level'],i['invited_by'],now()))
    audit(c,u,iid,'EVIDENCE_ROOM_INVITATION_ACCEPTED',{'property_id':i['property_id'],'match_id':i['match_id'],'level':i['level'],'decision':'INVITEE_ACCEPTED'})
    return {'state':'ACCEPTED','property_id':i['property_id']}
