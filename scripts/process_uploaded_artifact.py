"""Explicit operator job for a stored upload; no HTTP Docker access and no claim approval."""
import argparse,json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.core import connect,one,migrate,uid,now,audit,Problem
from app.document_processing import process_file
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('artifact_id');p.add_argument('--database',default=str(ROOT/'runtime/app.sqlite'));a=p.parse_args()
    migrate(a.database);c=connect(a.database)
    try:
        row=one(c,'SELECT a.*,b.raw_bytes FROM artifacts a JOIN artifact_blobs b ON b.artifact_id=a.id WHERE a.id=?',(a.artifact_id,))
        if not row:raise Problem('Binary artifact not found',404)
        with tempfile.TemporaryDirectory(prefix='ran-private-scan-') as tmp:
            source=Path(tmp)/('document'+Path(row['filename']).suffix);source.write_bytes(row['raw_bytes'])
            report=process_file(source)
        if report['source_sha256']!=row['sha256']:raise Problem('Original upload hash mismatch',409)
        c.execute('BEGIN IMMEDIATE')
        c.execute('INSERT INTO artifact_processing_results VALUES(?,?,?,?,?,?,?)',(uid(),row['id'],row['sha256'],report['scan_status'],report.get('extraction_status'),json.dumps(report),now()))
        audit(c,{'id':'operator:document-processing','organization_id':None},row['property_id'],'DOCUMENT_PROCESSING_RECEIPT',{'artifact_id':row['id'],'scan_status':report['scan_status'],'source_unchanged':True,'human_confirmation_required':True})
        c.commit();print(json.dumps({'scan_status':report['scan_status'],'extraction_status':report.get('extraction_status'),'automatic_approval':False}))
    except Problem as e:c.rollback();print(e.message,file=sys.stderr);raise SystemExit(1)
    finally:c.close()
