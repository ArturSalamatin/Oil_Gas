"""Minimal read-only XLSX table reader using only the Python standard library."""
from pathlib import Path
import zipfile, xml.etree.ElementTree as ET, re

NS_MAIN='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
NS_REL='{http://schemas.openxmlformats.org/package/2006/relationships}'
NS_DOC_REL='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'

def _col_index(ref):
    m=re.match(r'([A-Z]+)',ref)
    n=0
    for ch in m.group(1): n=n*26+ord(ch)-64
    return n-1

def read_workbook_tables(path):
    path=Path(path)
    with zipfile.ZipFile(path) as z:
        shared=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            root=ET.fromstring(z.read('xl/sharedStrings.xml'))
            for si in root.findall(NS_MAIN+'si'):
                shared.append(''.join(t.text or '' for t in si.iter(NS_MAIN+'t')))
        wb=ET.fromstring(z.read('xl/workbook.xml'))
        relroot=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        relmap={r.attrib['Id']:r.attrib['Target'] for r in relroot.findall(NS_REL+'Relationship')}
        out={}
        for sh in wb.find(NS_MAIN+'sheets'):
            name=sh.attrib['name']; rid=sh.attrib[NS_DOC_REL+'id']; target=relmap[rid]
            if target.startswith('/'): member=target.lstrip('/')
            elif target.startswith('xl/'): member=target
            else: member='xl/'+target
            root=ET.fromstring(z.read(member))
            rows=[]
            sheetdata=root.find(NS_MAIN+'sheetData')
            if sheetdata is None: out[name]=rows; continue
            for r in sheetdata.findall(NS_MAIN+'row'):
                vals={}; maxc=-1
                for c in r.findall(NS_MAIN+'c'):
                    j=_col_index(c.attrib['r']); maxc=max(maxc,j); typ=c.attrib.get('t')
                    v=c.find(NS_MAIN+'v'); isel=c.find(NS_MAIN+'is')
                    if typ=='s' and v is not None: val=shared[int(v.text)]
                    elif typ=='inlineStr' and isel is not None: val=''.join(t.text or '' for t in isel.iter(NS_MAIN+'t'))
                    elif typ=='str' and v is not None: val=v.text or ''
                    elif v is None: val=None
                    else:
                        txt=v.text or ''
                        try: val=float(txt)
                        except: val=txt
                    vals[j]=val
                if maxc>=0:
                    row=[None]*(maxc+1)
                    for j,vv in vals.items(): row[j]=vv
                    rows.append(row)
            out[name]=rows
        return out
