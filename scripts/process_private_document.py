"""Explicit local private-file scan and read. Never publish, promote contacts or approve a claim."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.document_processing import process_file
from app.core import Problem
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('--output',required=True);a=p.parse_args()
    output=Path(a.output).resolve()
    if output.is_relative_to(ROOT) and not output.is_relative_to(ROOT/'runtime'):raise SystemExit('Private output must be outside public source or in excluded runtime')
    try:
        report=process_file(a.source);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps({'scan_status':report['scan_status'],'extraction_status':report.get('extraction_status'),'private_report_saved':True}))
    except Problem as e:print(e.message,file=sys.stderr);raise SystemExit(1)
