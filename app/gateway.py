"""Sensitive actions: explicit allowlist, permission, evidence, human decision, mutation, audit."""
from .core import *

ACTIONS={'RECONCILE_CLAIM','PUBLISH_PROPERTY','DISCLOSE_INFORMATION','INVITE_COUNTERPARTY','OPEN_DATA_ROOM','REQUEST_FINANCING','CREATE_OFFERING','APPROVE_ELIGIBILITY','SUBMIT_INDICATION','ACCEPT_SUBSCRIPTION','CREATE_ALLOCATION','ISSUE_INSTRUMENT','TRANSFER_INSTRUMENT','MOVE_FUNDS','PAY_DISTRIBUTION','PAY_REFERRAL_FEE'}
DISABLED={'INVITE_COUNTERPARTY','REQUEST_FINANCING','SUBMIT_INDICATION','CREATE_ALLOCATION','ISSUE_INSTRUMENT','TRANSFER_INSTRUMENT','MOVE_FUNDS','PAY_REFERRAL_FEE'}

def gateway(c,u,d):
    require(u,'Sign in',401)
    action=text(d.get('action'),'action');pid=text(d.get('resource_id'),'resource_id');payload=d.get('payload',{})
    require(isinstance(payload,dict),'payload must be an object')
    reason=text(d.get('reason','Requested through application'),'reason',1000)
    proposal=uid();policy={'version':POLICY_VERSION,'mode':'SIMULATION_ONLY','human_actor':u['id'],'financial_live':False}
    c.execute('SAVEPOINT action_mutation')
    try:
        require(action in ACTIONS,'Unknown action',403)
        require(action not in DISABLED,'Action disabled in V0. No live financial, signing, referral or outreach executor exists.',403)
        p=property_access(c,u,pid)
        if action=='DISCLOSE_INFORMATION': result=room(c,u,pid)
        elif action=='ACCEPT_SUBSCRIPTION':
            require(u['role']=='investor','Investor role required',403)
            eligible=one(c,'SELECT * FROM eligibility WHERE user_id=?',(u['id'],))
            require(eligible and eligible['state']=='APPROVED_SIMULATION','Reviewer must approve simulated eligibility',403)
            o=one(c,"SELECT o.* FROM offerings o JOIN deals d ON d.id=o.deal_id WHERE d.property_id=? AND o.state='OPEN_SIMULATION' ORDER BY o.created_at DESC LIMIT 1",(pid,))
            require(o,'No open simulated offering',409)
            require(payload.get('acknowledge_simulation') is True and payload.get('fee_bps')==o['fee_bps'],'Acknowledge simulation and the displayed fee before subscribing',409)
            key=text(payload.get('idempotency_key'),'idempotency_key',100)
            amount=cents(payload.get('amount')); require(amount>=o['min_cents'],'Below minimum simulated subscription')
            prior=one(c,'SELECT * FROM transactions WHERE idempotency_key=?',(u['id']+':subscribe:'+key,))
            if prior:
                require(prior['offering_id']==o['id'] and prior['amount_cents']==amount,'Idempotency key reused with different request',409)
                result={'transaction':prior,'replayed':True}
            else:
                allocated=c.execute('SELECT coalesce(sum(principal_cents),0) FROM holdings WHERE offering_id=?',(o['id'],)).fetchone()[0]
                require(allocated+amount<=o['target_cents'],'Subscription exceeds remaining simulated capacity',409)
                fee=(amount*o['fee_bps']+5000)//10000;tid=uid();hid=uid()
                c.execute('INSERT INTO transactions VALUES(?,?,?,?,?,?,?,?)',(tid,u['id'],o['id'],'SUBSCRIPTION',amount,'SETTLED_SIMULATION',u['id']+':subscribe:'+key,now()))
                c.execute('INSERT INTO holdings VALUES(?,?,?,?,?,?,?)',(hid,u['id'],o['id'],amount,fee,'ACTIVE_SIMULATION',now()))
                c.execute('UPDATE room_grants SET level=4 WHERE user_id=? AND property_id=?',(u['id'],pid))
                audit(c,u,pid,'PARTICIPATION_TRANSITION',{'previous_state':'NONE','new_state':'ACTIVE_SIMULATION','settlement':'SETTLED_SIMULATION','holding_id':hid,'amount_cents':amount,'fee_cents':fee,'policy':policy,'authorization':'approved eligibility and room grant','reason':reason})
                result={'holding_id':hid,'transaction_id':tid,'amount_cents':amount,'fee_cents':fee,'simulation':True}
        else:
            require(u['role']=='admin','Independent reviewer required',403)
            require(u['id']!=p['created_by'],'Originator cannot approve their own material release',403)
            if action=='RECONCILE_CLAIM':
                require(p['state']!='PUBLISHED','Published records require a new reviewed revision',409)
                selected=one(c,'SELECT * FROM claims WHERE id=? AND property_id=?',(payload.get('claim_id'),pid));require(selected,'Select a claim from this property')
                require(one(c,'SELECT id FROM claim_confirmations WHERE claim_id=?',(selected['id'],)),'Originator must confirm selected source claim first',409)
                require(selected['field'] in TORONTO_MARKET['required_underwriting']+['units'],'Legal and encumbrance priority cannot be reconciled by this executor',403)
                group=rows(c,'SELECT id FROM claims WHERE property_id=? AND field=?',(pid,selected['field']))
                rid=uid();c.execute('INSERT INTO claim_reconciliations VALUES(?,?,?,?,?,?,?,?)',(rid,pid,selected['field'],selected['id'],js([r['id'] for r in group]),reason,u['id'],now()))
                result={'reconciliation_id':rid,'selected_claim_id':selected['id'],'source_claims_preserved':True,'new_underwriting_required':True}
            elif action=='PUBLISH_PROPERTY':
                require(p['synthetic']==1,'Real-property information remains private until publication rights and operational review are implemented',403)
                require(p['state']=='IN_REVIEW','Submit property for review first',409)
                risks=risk_state(c,pid)
                require(not risks['missing_fields'] and not risks['contradictions'] and not risks['quarantined_artifacts'],'Resolve required evidence, contradictions and quarantined documents before publication',409)
                snapshot=one(c,'SELECT * FROM underwriting_snapshots WHERE property_id=? ORDER BY created_at DESC LIMIT 1',(pid,));require(snapshot,'Underwriting snapshot required',409)
                current=evidence_state(c,pid)[2];require(json.loads(snapshot['evidence_refs'])==current,'Evidence changed since underwriting; create a new snapshot',409)
                units=json.loads(snapshot['input_values']).get('units')
                require(units is not None and units>=1 and float(units).is_integer(),'Confirmed whole-number unit count required before release',409)
                c.execute("UPDATE properties SET state='PUBLISHED',version=version+1 WHERE id=?",(pid,))
                audit(c,u,pid,'PROPERTY_TRANSITION',{'previous_state':'IN_REVIEW','new_state':'PUBLISHED','snapshot_id':snapshot['id'],'approval_actor':u['id'],'policy':policy,'reason':reason,'authorization':'independent reviewer','unknown_legal_claims':'not cleared; public factual discovery only'})
                result={'state':'PUBLISHED','property':public_property(c,one(c,'SELECT * FROM properties WHERE id=?',(pid,)))}
            elif action in ['OPEN_DATA_ROOM','APPROVE_ELIGIBILITY']:
                target=one(c,'SELECT * FROM users WHERE id=?',(payload.get('user_id'),));require(target and target['role']=='investor','Select an investor')
                require(p['state']=='PUBLISHED','Published property required',409)
                if action=='OPEN_DATA_ROOM':
                    c.execute('INSERT INTO room_grants VALUES(?,?,?,?,?) ON CONFLICT(user_id,property_id) DO UPDATE SET level=max(level,excluded.level),granted_by=excluded.granted_by,created_at=excluded.created_at',(target['id'],pid,3,u['id'],now()))
                    result={'user_id':target['id'],'level':3,'simulation':True}
                else:
                    c.execute('INSERT INTO eligibility VALUES(?,?,?,?,1) ON CONFLICT(user_id) DO UPDATE SET state=excluded.state,reviewed_by=excluded.reviewed_by,reviewed_at=excluded.reviewed_at',(target['id'],'APPROVED_SIMULATION',u['id'],now()))
                    result={'user_id':target['id'],'state':'APPROVED_SIMULATION','kyc_verified':False}
            elif action=='CREATE_OFFERING':
                require(p['synthetic']==1,'Real-property capital formation is not enabled',403)
                require(p['state']=='PUBLISHED','Publish factual passport first',409)
                require(not one(c,'SELECT id FROM deals WHERE property_id=?',(pid,)),'A V0 simulated deal already exists',409)
                target=cents(payload.get('target_amount',1000000));minimum=cents(payload.get('min_subscription',10000));fee=number(payload.get('fee_rate',0.01),'fee_rate',0,0.05)
                require(target>=minimum>0,'Invalid offering size')
                entity,deal,instrument,offering=uid(),uid(),uid(),uid()
                c.execute('INSERT INTO legal_entities VALUES(?,?,?,?,1)',(entity,'DEMO '+p['address']+' SPV','SPV','PROPERTY_ONLY'))
                c.execute('INSERT INTO deals VALUES(?,?,?,?,?,?)',(deal,pid,entity,'OPEN_SIMULATION','PROPERTY_EQUITY',now()))
                c.execute('INSERT INTO capital_requirements VALUES(?,?,?,?,?)',(uid(),deal,target,'CAD','SIMULATED_PROPERTY_EQUITY'))
                c.execute('INSERT INTO instruments VALUES(?,?,?,?,?)',(instrument,entity,'SIMULATED_PARTICIPATION','PROPERTY_ONLY','TRANSFER_DISABLED'))
                c.execute('INSERT INTO offerings VALUES(?,?,?,?,?,?,?,?)',(offering,deal,instrument,'OPEN_SIMULATION',target,minimum,round(fee*10000),now()))
                result={'offering_id':offering,'deal_id':deal,'state':'OPEN_SIMULATION','simulation':True,'legal_clearance':'NOT_ASSESSED','startup_rights':False}
            elif action=='PAY_DISTRIBUTION':
                o=one(c,'SELECT o.* FROM offerings o JOIN deals d ON d.id=o.deal_id WHERE d.property_id=?',(pid,));require(o,'No offering',409)
                key=text(payload.get('idempotency_key'),'idempotency_key',100);amount=cents(payload.get('amount'));require(amount>0,'Distribution must be positive')
                prior=one(c,'SELECT * FROM transactions WHERE idempotency_key=?',(u['id']+':distribution:'+key,))
                if prior:
                    require(prior['offering_id']==o['id'] and prior['amount_cents']==amount,'Idempotency conflict',409);result={'transaction':prior,'replayed':True}
                else:
                    holds=rows(c,'SELECT * FROM holdings WHERE offering_id=? ORDER BY id',(o['id'],));require(holds,'No simulated participants',409)
                    total=sum(h['principal_cents'] for h in holds);tid=uid()
                    c.execute('INSERT INTO transactions VALUES(?,?,?,?,?,?,?,?)',(tid,u['id'],o['id'],'DISTRIBUTION',amount,'SETTLED_SIMULATION',u['id']+':distribution:'+key,now()))
                    allocations=[amount*h['principal_cents']//total for h in holds]
                    remainder=amount-sum(allocations)
                    order=sorted(range(len(holds)),key=lambda i: (-(amount*holds[i]['principal_cents']%total),holds[i]['id']))
                    for i in order[:remainder]: allocations[i]+=1
                    for h,n in zip(holds,allocations): c.execute('INSERT INTO distributions VALUES(?,?,?,?,?)',(uid(),tid,h['id'],n,now()))
                    result={'transaction_id':tid,'amount_cents':amount,'allocations':len(holds),'simulation':True}
            else: raise Problem('No executor for action',403)
        c.execute('RELEASE action_mutation')
        decision='ALLOW_SIMULATION' if action not in ['PUBLISH_PROPERTY','DISCLOSE_INFORMATION','OPEN_DATA_ROOM'] else 'ALLOW'
        c.execute('INSERT INTO action_proposals VALUES(?,?,?,?,?,?,?,?,?)',(proposal,u['id'],action,pid,js(payload),decision,js(policy),reason,now()))
        audit(c,u,pid,'ACTION_GATEWAY',{'proposal_id':proposal,'action':action,'decision':decision,'policy':policy,'reason':reason,'result':result if action!='DISCLOSE_INFORMATION' else {'projection':'private room'}})
        return result|{'proposal_id':proposal}
    except Problem as e:
        c.execute('ROLLBACK TO action_mutation');c.execute('RELEASE action_mutation')
        c.execute('INSERT INTO action_proposals VALUES(?,?,?,?,?,?,?,?,?)',(proposal,u['id'],action,pid,js(payload),'DENY',js(policy),e.message,now()))
        audit(c,u,pid,'ACTION_DENIED',{'action':action,'reason':e.message,'policy':policy})
        raise
