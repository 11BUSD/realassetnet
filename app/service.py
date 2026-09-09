from .core import *
from .gateway import gateway

def dispatch(c,u,method,path,d=None):
    d=d or {};parts=path.strip('/').split('/')
    if method=='GET' and path=='/api/properties':
        audit(c,u or {'id':'anonymous','organization_id':None},'public-discovery','DISCLOSE_INFORMATION',{'level':0,'policy':POLICY_VERSION,'projection':'published factual fields only','decision':'ALLOW'})
        return {'properties':[public_property(c,p) for p in rows(c,"SELECT * FROM properties WHERE state='PUBLISHED' ORDER BY created_at DESC")]}
    if method=='GET' and len(parts)==3 and parts[:2]==['api','properties']:
        p=one(c,"SELECT * FROM properties WHERE id=? AND state='PUBLISHED'",(parts[2],));require(p,'Published property not found',404)
        # Anonymous factual projection is deliberately allowlisted; access itself is audit logged.
        audit(c,u or {'id':'anonymous','organization_id':None},p['id'],'DISCLOSE_INFORMATION',{'level':0,'decision':'ALLOW','policy':POLICY_VERSION,'fields':['address','city','property_type','units','asking_price','description','originator']})
        return {'property':public_property(c,p)}
    require(u,'Sign in to continue',401)
    if path=='/api/workspace' and method=='GET':
        return {'properties':rows(c,'SELECT * FROM properties WHERE organization_id=? ORDER BY created_at DESC',(u['organization_id'],))}
    if path=='/api/properties' and method=='POST': return create_property(c,u,d)
    if path=='/api/actions' and method=='POST': return gateway(c,u,d)
    if parts[:2]==['api','properties'] and len(parts)>=4:
        pid,operation=parts[2:4]
        if method=='GET' and operation=='room': return gateway(c,u,{'action':'DISCLOSE_INFORMATION','resource_id':pid,'reason':'User opened controlled room'})
        if method=='POST':
            if operation=='upload': return upload(c,u,pid,d)
            if operation=='upload-binary': return upload_binary(c,u,pid,d)
            if operation=='claims' and len(parts)==6 and parts[5]=='confirm': return confirm_claim(c,u,pid,parts[4])
            if operation=='underwrite': return underwrite(c,u,pid,d)
            if operation=='submit-review':
                p=property_access(c,u,pid,True);require(p['state']=='DRAFT','Only a draft can enter review',409)
                c.execute("UPDATE properties SET state='IN_REVIEW' WHERE id=?",(pid,))
                risk=risk_state(c,pid)
                for field in risk['missing_fields']:
                    c.execute('INSERT INTO evidence_requests VALUES(?,?,?,?,?,?)',(uid(),pid,field,'Confirm source-supported value before publication',u['id'],now()))
                agent_run(c,u,pid,'evidence',risk,[],risk['missing_fields'],risk['contradictions'])
                agent_run(c,u,pid,'contradiction',{'overlapping_claims':risk['asset_claim_overlap'],'legal_priority':'NOT_DETERMINED'},[],[],risk['contradictions'])
                audit(c,u,pid,'PROPERTY_TRANSITION',{'previous_state':'DRAFT','new_state':'IN_REVIEW','authorization':'originating organization','policy':POLICY_VERSION,'reason':'Originator submitted for independent human review'})
                return {'state':'IN_REVIEW','risks':risk}
            if operation=='request-evidence':
                property_access(c,u,pid);require(u['role']=='admin','Reviewer required',403)
                field=text(d.get('field'),'field');reason=text(d.get('reason'),'reason',1000)
                c.execute('INSERT INTO evidence_requests VALUES(?,?,?,?,?,?)',(uid(),pid,field,reason,u['id'],now()));audit(c,u,pid,'EVIDENCE_REQUESTED',{'field':field,'reason':reason})
                return {'requested':field}
            if operation=='asset-claims':
                p=property_access(c,u,pid,True);require(p['state']!='PUBLISHED','Published claim graph requires reviewed revision',409)
                kind=d.get('kind');require(kind in ['OwnershipClaim','Lien','Mortgage','DebtPosition','SecurityInterest','Encumbrance','PendingCapitalAction','LegalRestriction'],'Unknown asset claim kind')
                amount=number(d['amount'],'amount') if d.get('amount') not in [None,''] else None
                cid=uid();label=text(d.get('label'),'label',1000)
                source=add_claim(c,u,pid,kind,{'label':label,'amount':amount},None,'Contributor encumbrance disclosure')
                c.execute('INSERT INTO asset_claims VALUES(?,?,?,?,?,?,?,?,?)',(cid,pid,kind,label,amount,'UNVERIFIED',source,u['id'],now()))
                audit(c,u,pid,'ASSET_CLAIM_ADDED',{'claim_id':cid,'kind':kind,'legal_priority':'NOT_DETERMINED','overlap_escalation':True})
                return {'asset_claim_id':cid,'risks':risk_state(c,pid)}
    if path=='/api/portfolio' and method=='GET':
        return {'holdings':rows(c,'SELECT h.*,p.address FROM holdings h JOIN offerings o ON h.offering_id=o.id JOIN deals d ON o.deal_id=d.id JOIN properties p ON d.property_id=p.id WHERE h.user_id=?',(u['id'],)), 'transactions':rows(c,'SELECT * FROM transactions WHERE user_id=?',(u['id'],)), 'distributions':rows(c,'SELECT x.* FROM distributions x JOIN holdings h ON x.holding_id=h.id WHERE h.user_id=?',(u['id'],))}
    if path=='/api/audit' and method=='GET':
        events=rows(c,'SELECT * FROM audit_events ORDER BY seq DESC LIMIT 500') if u['role']=='admin' else rows(c,'SELECT * FROM audit_events WHERE actor_id=? OR (organization_id=? AND event NOT IN (\'LOGIN\',\'SIGNUP\')) ORDER BY seq DESC LIMIT 500',(u['id'],u['organization_id']))
        return {'events':events,'integrity':integrity(c),'integrity_scope':'Full local hash chain; no externally anchored tamper proof claim'}
    if path=='/api/admin' and method=='GET':
        require(u['role']=='admin','Reviewer required',403)
        props=rows(c,'SELECT * FROM properties ORDER BY created_at DESC')
        for p in props: p['risks']=risk_state(c,p['id'])
        return {'properties':props,'users':[safe_user(r) for r in rows(c,'SELECT * FROM users')],'metrics':{'submitted_property_value':sum(p['asking_price'] or 0 for p in props),'published_properties':sum(p['state']=='PUBLISHED' for p in props),'outstanding_reviews':sum(p['state']=='IN_REVIEW' for p in props),'evidence_completeness':round(sum(p['risks']['evidence_completeness'] for p in props)/len(props),1) if props else 0,'capital_sought':c.execute('SELECT coalesce(sum(target_cents),0)/100.0 FROM offerings').fetchone()[0],'simulated_subscriptions':c.execute('SELECT coalesce(sum(principal_cents),0)/100.0 FROM holdings').fetchone()[0],'simulated_fees':c.execute('SELECT coalesce(sum(fee_cents),0)/100.0 FROM holdings').fetchone()[0],'counterparties':c.execute('SELECT count(*) FROM organizations').fetchone()[0],'geographic_concentration':rows(c,'SELECT city,count(*) properties,sum(asking_price) asking_value FROM properties GROUP BY city'),'investor_funnel':{'registered':c.execute("SELECT count(*) FROM users WHERE role='investor'").fetchone()[0],'qualified_simulation':c.execute('SELECT count(*) FROM eligibility').fetchone()[0],'participants':c.execute('SELECT count(DISTINCT user_id) FROM holdings').fetchone()[0]}},'audit':rows(c,'SELECT * FROM audit_events ORDER BY seq DESC LIMIT 40'),'proposals':rows(c,'SELECT * FROM action_proposals ORDER BY created_at DESC LIMIT 40')}
    if path=='/api/factory' and method=='GET':
        require(u['role']=='admin','Reviewer required',403)
        return {'agents':[{'id':a,'name':b,'purpose':x,'status':s,'authority':'PROPOSE_ONLY'} for a,b,x,s in AGENTS],'runs':rows(c,'SELECT * FROM agent_runs ORDER BY created_at DESC LIMIT 100'),'capabilities':{'live_money':False,'external_model':False,'code_execution_from_uploads':False,'network_egress_from_workers':False,'pdf_office_scanner':'NOT_CONNECTED; original binary files may be privately quarantined','factory_release':'scripts/release_check.py','private_core':'Operator-gated read-only connector; separate configuration required; no sending'}}
    raise Problem('Endpoint not found',404)

def seed_demo(c):
    if one(c,"SELECT id FROM users WHERE email='reviewer@demo.invalid'"): return
    broker=signup(c,{'name':'Alex Morgan · DEMO','email':'broker@demo.invalid','password':'DemoOnly!2026','organization':'DEMO Harbour Originations','role':'broker'})
    investor=signup(c,{'name':'Sam Chen · DEMO','email':'investor@demo.invalid','password':'DemoOnly!2026','organization':'DEMO Investor','role':'investor'})
    reviewer=signup(c,{'name':'Taylor Reed · DEMO','email':'reviewer@demo.invalid','password':'DemoOnly!2026','organization':'DEMO Independent Review','role':'investor'})
    c.execute("UPDATE users SET role='admin' WHERE id=?",(reviewer['id'],));reviewer['role']='admin'
    for address,city,units,price,rent,expenses,desc in [
        ('100 Example Harbour Lane','Toronto',24,6200000,520000,145000,'DEMO/SYNTHETIC. A fictional 24-suite waterfront-inspired rental property. Address and illustration are not a real listing.'),
        ('200 Example Park Avenue','Mississauga',18,4700000,410000,125000,'DEMO/SYNTHETIC. A fictional garden-style residential portfolio. No property is offered for sale.'),
        ('300 Example Junction Road','Toronto',36,8900000,730000,210000,'DEMO/SYNTHETIC. A fictional mixed-use neighbourhood asset used to demonstrate evidence review.')]:
        p=create_property(c,broker,{'address':address,'city':city,'units':units,'asking_price':price,'description':desc})['property']
        upload(c,broker,p['id'],{'filename':'synthetic-operating-statement.csv','content':f'annual_gross_rent,{rent}\nannual_expenses,{expenses}\nvacancy_rate,0.04'})
        for claim in rows(c,'SELECT id FROM claims WHERE property_id=?',(p['id'],)): confirm_claim(c,broker,p['id'],claim['id'])
        underwrite(c,broker,p['id'],{})
        dispatch(c,broker,'POST',f"/api/properties/{p['id']}/submit-review",{})
        gateway(c,reviewer,{'action':'PUBLISH_PROPERTY','resource_id':p['id'],'reason':'Independent approval of synthetic fixture only'})
    # No pre-granted investor access or pre-approved eligibility: demonstrate boundaries.
    audit(c,reviewer,'demo','SEED_COMPLETED',{'synthetic':True,'live_money':False})
