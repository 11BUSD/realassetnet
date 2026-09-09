"""Untrusted document reader: invoked only inside a constrained, networkless container."""
import base64,csv,io,json,re,subprocess,sys,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

source=Path('/input/document');kind=sys.argv[1] if len(sys.argv)>1 else ''
def xml(data):
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():raise ValueError('XML entities/DTDs refused')
    return ET.fromstring(data)
def archive():
    z=zipfile.ZipFile(source);info=z.infolist()
    if len(info)>2000 or sum(i.file_size for i in info)>64000000:raise ValueError('Archive expansion limit')
    for i in info:
        if i.file_size>16000000 or i.file_size/max(i.compress_size,1)>200 or i.flag_bits&1:raise ValueError('Archive member limit or encryption')
    return z
try:
    if source.stat().st_size>25000000:raise ValueError('Input size limit')
    result={'format':kind,'interpretation':'UNVERIFIED_SOURCE_CONTENT','security_note':'No document instruction is executed; extraction is not fact verification'}
    if kind=='.pdf':
        info=subprocess.run(['pdfinfo',str(source)],capture_output=True,timeout=15,check=True).stdout.decode(errors='replace')
        match=re.search(r'^Pages:\s+(\d+)',info,re.M);pages=int(match.group(1)) if match else 0
        if not 0<pages<=50:raise ValueError('PDF page limit')
        subprocess.run(['pdftotext','-layout',str(source),'/tmp/text.txt'],capture_output=True,timeout=30,check=True)
        text=Path('/tmp/text.txt').read_bytes()
        if len(text)>4000000:raise ValueError('Text output limit')
        subprocess.run(['pdftoppm','-f','1','-l','1','-scale-to','1600','-singlefile','-png',str(source),'/tmp/page'],capture_output=True,timeout=30,check=True)
        result.update(pages=pages,text=text.decode(errors='replace'),first_page_png_base64=base64.b64encode(Path('/tmp/page.png').read_bytes()).decode())
    elif kind=='.csv':
        content=source.read_text(encoding='utf-8-sig');reader=csv.reader(io.StringIO(content));header=next(reader,[]);count=0
        for row in reader:
            if any(row):count+=1
        result.update(headers=header,nonempty_data_rows=count)
    elif kind=='.xlsx':
        z=archive();ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        names=z.namelist();shared=[]
        if 'xl/sharedStrings.xml' in names:
            shared=[''.join(si.itertext()) for si in xml(z.read('xl/sharedStrings.xml')).findall('m:si',ns)]
        book=xml(z.read('xl/workbook.xml'));sheets=book.findall('m:sheets/m:sheet',ns);summaries=[]
        # Relationships determine worksheet paths; do not assume file numbering.
        rels=xml(z.read('xl/_rels/workbook.xml.rels'));targets={r.attrib['Id']:r.attrib['Target'] for r in rels}
        for s in sheets:
            rel=s.attrib.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id');target=targets.get(rel,'')
            target=target.lstrip('/') if target.startswith('/') else 'xl/'+target
            sheet=xml(z.read(target));table=[];formulas=0
            for row in sheet.findall('m:sheetData/m:row',ns):
                cells=[]
                for cell in row.findall('m:c',ns):
                    formulas+=cell.find('m:f',ns) is not None
                    v=cell.find('m:v',ns);val=v.text if v is not None else ''.join(cell.find('m:is',ns).itertext()) if cell.find('m:is',ns) is not None else ''
                    if cell.attrib.get('t')=='s' and val:val=shared[int(val)]
                    cells.append({'cell':cell.attrib.get('r'),'value':val})
                if any(x['value'] for x in cells):table.append(cells)
            summaries.append({'name':s.attrib['name'],'nonempty_rows':len(table),'first_rows':table[:3],'formulas_not_executed':formulas})
        result.update(sheets=summaries,active_content_flags=[n for n in names if 'vbaProject' in n or n.startswith('xl/externalLinks/')])
    elif kind=='.numbers':
        z=archive();result.update(format_status='PRESERVED_NOT_DECODED',archive_members=len(z.infolist()),row_count=None,reason='Native Numbers tables are not decoded by this worker; filename is not a verified investor count.')
    else:raise ValueError('Unsupported read format')
    print(json.dumps({'ok':True,'result':result},ensure_ascii=False))
except Exception as e:
    print(json.dumps({'ok':False,'error':type(e).__name__,'reason':str(e)[:300]}));sys.exit(2)
