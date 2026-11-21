"""Assemble the approved Chinese report sections without rewriting research prose.

Run with the bundled Python runtime. Temporary parser/math dependencies are
provided through PYTHONPATH; rendering and page inspection are separate.
"""
from pathlib import Path
from copy import deepcopy
import argparse, hashlib, json, re, sys
from zipfile import ZipFile
from urllib.parse import unquote

from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from markdown_it import MarkdownIt
from latex2mathml.converter import convert as to_mathml
import mathml2omml
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
TEMP=Path('/tmp/data3001_word_build')
TEMP.mkdir(parents=True,exist_ok=True)
# Use this task-local Fontconfig file for the bundled headless renderer.
(TEMP/'fonts.conf').write_text('''<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
<dir>/System/Library/Fonts</dir>
<dir>/System/Library/Fonts/Supplemental</dir>
<dir>/Library/Fonts</dir>
<dir>/Users/moonedgethug/Library/Fonts</dir>
<cachedir>/tmp/data3001_word_build/font-cache</cachedir>
</fontconfig>
''')
OUTPUT=ROOT/'DATA3001_Final_Report_CN.docx'
LATIN='Times New Roman'
CJK='Songti SC'
HEADING_CJK='Heiti SC'
BODY_SIZE=11
WIDTH=7.2
NS_M='http://schemas.openxmlformats.org/officeDocument/2006/math'
NS_W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
md=MarkdownIt('commonmark').enable('table')
files={p.name[:3]:p for p in (ROOT/'drafts').glob('W*.md')}
manifest={'sources':{},'modules':{},'figures':[],'equations':[],'paragraph_checks':0,
          'removed_authoring_links':[],'cross_reference_changes':[]}
expected_paragraphs=[]
math_map={}
headings=[]
doc=Document()
section=doc.sections[0]
section.page_width=Inches(8.5);section.page_height=Inches(11)
section.top_margin=Inches(.65);section.bottom_margin=Inches(.65)
section.left_margin=Inches(.65);section.right_margin=Inches(.65)
section.footer_distance=Inches(.30);section.header_distance=Inches(.28)
doc.core_properties.title='历史漂流器轨迹与七天去向预测研究'
doc.core_properties.subject='Gulf Stream南段 DATA3001'
doc.core_properties.author='DATA3001'
doc.core_properties.keywords='drifter; Gulf Stream; probabilistic prediction'
doc.core_properties.comments=''
doc.core_properties.last_modified_by='DATA3001'

def font_props(rpr, size=BODY_SIZE, bold=False, cjk=CJK, latin=LATIN):
    rf=OxmlElement('w:rFonts')
    for k,v in [('ascii',latin),('hAnsi',latin),('eastAsia',cjk),('cs',latin)]:
        rf.set(qn('w:'+k),v)
    rpr.append(rf)
    sz=OxmlElement('w:sz');sz.set(qn('w:val'),str(round(size*2)));rpr.append(sz)
    if bold:
        el=OxmlElement('w:b');rpr.append(el)
    lang=OxmlElement('w:lang');lang.set(qn('w:val'),'en-AU')
    lang.set(qn('w:eastAsia'),'zh-CN');rpr.append(lang)

def format_run(run,size=None,bold=None,italic=None):
    run.font.name=LATIN
    run.font.size=Pt(size or BODY_SIZE)
    run._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),CJK)
    if bold is not None:run.bold=bold
    if italic is not None:run.italic=italic
    return run

for name,size in [('Normal',BODY_SIZE),('Title',22),('Subtitle',13),
                  ('Heading 1',16),('Heading 2',13),('Heading 3',11.5),
                  ('Caption',10),('List Paragraph',BODY_SIZE)]:
    st=doc.styles[name]
    st.font.name=LATIN;st.font.size=Pt(size);st.font.color.rgb=RGBColor(0,0,0)
    st._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),HEADING_CJK if name.startswith('Heading') else CJK)
    st.paragraph_format.space_after=Pt(4)
    st.paragraph_format.line_spacing=Pt({'Title':28,'Subtitle':18,'Heading 1':21,'Heading 2':18,'Heading 3':16,'Caption':13}.get(name,14))
    if name.startswith('Heading'):
        level=int(name[-1])
        st.font.bold=True
        st.paragraph_format.space_before=Pt({1:12,2:9,3:7}[level])
        st.paragraph_format.space_after=Pt({1:8,2:6,3:4}[level])
        st.paragraph_format.keep_with_next=True
        st.paragraph_format.keep_together=True
for name in ['Reference','TOC Entry','Pending Subtitle']:
    if name not in doc.styles:doc.styles.add_style(name,1)
    st=doc.styles[name];st.base_style=doc.styles['Normal']
    st.font.name=LATIN;st.font.color.rgb=RGBColor(0,0,0)
    st._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),CJK)
refst=doc.styles['Reference'];refst.font.size=Pt(10.5)
refst.paragraph_format.left_indent=Inches(.22)
refst.paragraph_format.first_line_indent=Inches(-.22)
refst.paragraph_format.space_after=Pt(8)
refst.paragraph_format.line_spacing=Pt(13.5)
refst.paragraph_format.keep_together=True
tocst=doc.styles['TOC Entry'];tocst.font.size=Pt(11)
tocst.paragraph_format.space_after=Pt(8)
tocst.paragraph_format.line_spacing=Pt(16.5)
tocst.paragraph_format.tab_stops.add_tab_stop(Inches(WIDTH),2,1)
doc.styles['Pending Subtitle'].font.size=Pt(11)
doc.styles['Pending Subtitle'].font.italic=True
doc.styles['Normal'].paragraph_format.widow_control=True
for st in doc.styles:
    if st.type==1:
        grid=OxmlElement('w:snapToGrid');grid.set(qn('w:val'),'0')
        st._element.get_or_add_pPr().append(grid)
for st in doc.styles:
    for rf in st._element.findall('.//'+qn('w:rFonts')):
        for attr in list(rf.attrib):
            if attr.endswith('Theme'):del rf.attrib[attr]
    for border in st._element.findall('.//'+qn('w:pBdr')):
        border.getparent().remove(border)

# Native multilevel heading numbering.
numbering=doc.part.numbering_part.element
ab=OxmlElement('w:abstractNum');ab.set(qn('w:abstractNumId'),'42')
multi=OxmlElement('w:multiLevelType');multi.set(qn('w:val'),'multilevel');ab.append(multi)
for level in range(3):
    lvl=OxmlElement('w:lvl');lvl.set(qn('w:ilvl'),str(level))
    for tag,value in [('start','1'),('numFmt','decimal'),
                      ('lvlText','.'.join('%'+str(i+1) for i in range(level+1))),
                      ('suff','space'),('pStyle',f'Heading{level+1}')]:
        el=OxmlElement('w:'+tag);el.set(qn('w:val'),value);lvl.append(el)
    pp=OxmlElement('w:pPr');ind=OxmlElement('w:ind')
    ind.set(qn('w:left'),'0');ind.set(qn('w:hanging'),'0');pp.append(ind);lvl.append(pp)
    ab.append(lvl)
numbering.append(ab)
num=OxmlElement('w:num');num.set(qn('w:numId'),'42')
aid=OxmlElement('w:abstractNumId');aid.set(qn('w:val'),'42');num.append(aid);numbering.append(num)

def heading(text,level=1,bookmark=None,numbered=True):
    # Typography normalization only; numbering is a native Word property.
    text=re.sub(r'^\d+(?:\.\d+)*[.．]?\s*','',text)
    text=re.sub(r'[：:（）()]',' ',text)
    text=re.sub(r'\s+',' ',text).strip()
    p=doc.add_paragraph(text,style=f'Heading {level}')
    if numbered:
        np=OxmlElement('w:numPr');il=OxmlElement('w:ilvl');il.set(qn('w:val'),str(level-1))
        ni=OxmlElement('w:numId');ni.set(qn('w:val'),'42');np.extend([il,ni]);p._p.get_or_add_pPr().append(np)
    if bookmark:
        bid=str(100+len(headings))
        start=OxmlElement('w:bookmarkStart');start.set(qn('w:id'),bid);start.set(qn('w:name'),bookmark)
        end=OxmlElement('w:bookmarkEnd');end.set(qn('w:id'),bid)
        p._p.insert(0,start);p._p.append(end)
        headings.append({'title':text,'bookmark':bookmark})
    return p

def add_link(p,label,target,size=BODY_SIZE,anchor=False):
    h=OxmlElement('w:hyperlink')
    if anchor:h.set(qn('w:anchor'),target)
    else:h.set(qn('r:id'),p.part.relate_to(target,RT.HYPERLINK,is_external=True))
    run=OxmlElement('w:r');pr=OxmlElement('w:rPr');font_props(pr,size)
    color=OxmlElement('w:color');color.set(qn('w:val'),'173C54');pr.append(color)
    run.append(pr);t=OxmlElement('w:t');t.set(qn('xml:space'),'preserve');t.text=label;run.append(t);h.append(run);p._p.append(h)

def insert_math(p,latex,display=False):
    try: xml=mathml2omml.convert(to_mathml(latex))
    except Exception as e:raise RuntimeError(f'Math conversion failed: {latex}') from e
    # Repair the converter's malformed tilde property close tag, then use
    # native accents for wide hats and tildes rather than limit constructions.
    xml=xml.replace('<m:pos m:val="top"/></m:groupChr>', '<m:pos m:val="top"/></m:groupChrPr>')
    wrap=parse_xml(f'<root xmlns:m="{NS_M}" xmlns:w="{NS_W}">{xml}</root>')
    for node in list(wrap.iter()):
        accent=None
        if node.tag==qn('m:groupChr'):
            ch=node.find('.//'+qn('m:chr'))
            if ch is not None and ch.get(qn('m:val'))=='~': accent='̃'
        elif node.tag==qn('m:limUpp'):
            lim=node.find(qn('m:lim'))
            if lim is not None and ''.join(lim.itertext())=='^': accent='̂'
        if accent:
            acc=OxmlElement('m:acc');pr=OxmlElement('m:accPr')
            ch=OxmlElement('m:chr');ch.set(qn('m:val'),accent);pr.append(ch);acc.append(pr)
            acc.append(deepcopy(node.find(qn('m:e'))))
            node.getparent().replace(node,acc)
    el=wrap[0]
    for nary in el.findall('.//'+qn('m:nary')):
        pr=nary.find(qn('m:naryPr'))
        for limit in ['sub','sup']:
            part=nary.find(qn('m:'+limit))
            if part is None or not ''.join(part.itertext()).strip():
                hide=OxmlElement('m:'+limit+'Hide');hide.set(qn('m:val'),'1');pr.append(hide)
    # A real Word math font and sizes are supplied as control properties.
    for mr in el.findall('.//'+qn('m:r')):
        pr=mr.find(qn('w:rPr'))
        if pr is None:pr=OxmlElement('w:rPr');mr.insert(0,pr)
        font_props(pr,11 if display else BODY_SIZE,latin='Cambria Math')
    if display:
        op=OxmlElement('m:oMathPara');props=OxmlElement('m:oMathParaPr')
        jc=OxmlElement('m:jc');jc.set(qn('m:val'),'center');props.append(jc)
        op.append(props);op.append(el);p._p.append(op)
    else:p._p.append(el)
    manifest['equations'].append({'latex':latex,'display':display})

def text_with_math(p,text,size,bold=False,italic=False):
    expected=''
    for bit in re.split(r'(FORMULATOKEN\d+END)',text):
        if bit in math_map:
            insert_math(p,math_map[bit])
            if '\\frac' in math_map[bit] or '\\sum' in math_map[bit]:
                p.paragraph_format.line_spacing=Pt(15)
                p.paragraph_format.line_spacing_rule=WD_LINE_SPACING.AT_LEAST
        elif bit:
            format_run(p.add_run(bit),size,bold,italic);expected+=bit
    return expected

def inline(p,tokens,size=BODY_SIZE):
    bold=italic=False;url=None;label='';expected=''
    for t in tokens:
        if t.type=='strong_open':bold=True
        elif t.type=='strong_close':bold=False
        elif t.type=='em_open':italic=True
        elif t.type=='em_close':italic=False
        elif t.type=='link_open':url=t.attrGet('href');label=''
        elif t.type=='link_close':
            if url.startswith(('https://','http://')):
                add_link(p,label,url,size)
            else:format_run(p.add_run(label),size,bold,italic)
            expected+=label;url=None
        elif t.type in ['text','code_inline']:
            if url is not None:label+=t.content
            else:expected+=text_with_math(p,t.content,size,bold,italic)
        elif t.type in ['softbreak','hardbreak']:
            if url is not None:label+=' '
            else:p.add_run(' ');expected+=' '
        elif t.type=='html_inline':
            if '<br' in t.content:p.add_run().add_break();expected+='\\n'
            else:raise ValueError('Unexpected inline HTML: '+t.content)
        else:raise ValueError('Unexpected inline token: '+t.type)
    expected_paragraphs.append((p,expected))
    return expected

def prep_math(text):
    def save(m):
        key=f'FORMULATOKEN{len(math_map):05d}END';math_map[key]=m.group(1);return key
    text=re.sub(r'\\\((.*?)\\\)',save,text)
    fence=chr(96)*3
    text=re.sub(r'\$\$([\s\S]*?)\$\$',lambda m:f'{fence}math\n{m.group(1).strip()}\n{fence}',text)
    return text

section_refs={'W01':'第1.1节','W02':'第1.2节','W03':'第2.1节','W04':'第2.2节',
              'W05':'第3章','W06':'第4章','W07':'第5.1节','W08':'第5.2节',
              'W09':'第5.3节','W10':'第5.4节','W11':'第5.5节','W12':'第6章',
              'W13':'第7章','W14':'第8章','W15':'第9章','W16':'第10章','W17':'参考文献',
              'W18':'摘要'}

def extract(key):
    p=files[key];raw=p.read_text()
    manifest['sources'][key]={'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    if key=='W01':text=raw.split('## 2. 正文草稿',1)[1].split('## 3.',1)[0]
    elif key in ['W02','W17','W18']:text=raw.split('\n## 1.',1)[1].split('\n',1)[1].split('\n## 2.',1)[0]
    else:
        text=raw[raw.index('\n## 1.'):]
        text=re.split(r'\n## .*?(?:编撰|引用与证据|证据与后续接口).*',text,1)[0]
    text=re.sub(r'<!--.*?-->','',text,flags=re.S)
    text=re.sub(r'\*\*W\d+-P\d+\*\*\s*','',text)
    # Authoring-only links are excluded; substantive source labels remain as plain text.
    def local_link(m):
        label,target=m.group(1),m.group(2)
        if target.startswith(('http://','https://')):return m.group(0)
        if label in ['图源与复现说明','数据与复现说明']:
            manifest['removed_authoring_links'].append({'module':key,'label':label,'target':target})
            return ''
        return label
    text=re.sub(r'(?<!!)\[([^\]]+)\]\(([^)]+)\)',local_link,text)
    if key=='W04':
        for old,new in [('次轮S1–S3','次轮Step1–Step3'),('次轮S4','次轮Step4'),('次轮S5最终MDN','次轮Step5最终MDN')]:
            if old in text:
                manifest['cross_reference_changes'].append({'module':key,'from':old,'to':new})
                text=text.replace(old,new)
    for old,new in section_refs.items():
        if re.search(old+r'(?![A-Za-z0-9_])',text):
            manifest['cross_reference_changes'].append({'module':key,'from':old,'to':new})
            text=re.sub(old+r'(?![A-Za-z0-9_])',new,text)
    manifest['modules'][key]={'body_sha256':hashlib.sha256(text.encode()).hexdigest(),
                             'body_characters':len(text),'section':section_refs[key]}
    return text

def draw_flow(source):
    labels=re.findall(r'[A-G]\["([^"]+)"\]',source)
    # Mermaid repeats nodes in edges; keep ordered first declarations.
    labels=list(dict.fromkeys(labels));assert len(labels)==7,labels
    image=Image.new('RGB',(2400,1280),'white');d=ImageDraw.Draw(image)
    fc=ImageFont.truetype('/System/Library/Fonts/STHeiti Medium.ttc',46)
    fe=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',44)
    y=25
    for i,label in enumerate(labels):
        x0,x1=65,2335;h=142
        d.rounded_rectangle((x0,y,x1,y+h),radius=10,fill='#F3F6F9',outline='#8B9BA8',width=3)
        ls=label.split('<br/>')
        for j,line in enumerate(ls):
            f=fc if re.search(r'[\u4e00-\u9fff]',line) else fe
            box=d.textbbox((0,0),line,font=f)
            xx=(2400-(box[2]-box[0]))/2
            yy=y+(h-len(ls)*56)/2+j*56-4
            d.text((xx,yy),line,font=f,fill='#12232E')
        if i<6:
            ym=y+h+28
            d.line((1200,y+h+4,1200,ym),fill='#5A6D7B',width=4)
            d.polygon([(1188,ym-5),(1212,ym-5),(1200,ym+9)],fill='#5A6D7B')
        y+=177
    out=TEMP/'figure03_research_flow.png';image.save(out)
    return out

def add_figure(path,alt,key,max_height=None):
    im=Image.open(path);w,h=im.size
    maxh=max_height or (6.30 if 'four_cases' in path.name else 4.35)
    inches=min(6.9,maxh*w/h)
    p=doc.add_paragraph()
    p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.line_spacing=1.0
    p.paragraph_format.space_before=Pt(6);p.paragraph_format.space_after=Pt(5)
    p.paragraph_format.keep_with_next=True
    p.paragraph_format.keep_together=True
    sh=p.add_run().add_picture(str(path),width=Inches(inches))
    dp=sh._inline.docPr;dp.set('descr',alt)
    manifest['figures'].append({'module':key,'name':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'width_inches':inches})

TABLE_WIDTHS={
1:[2.15,1.10,1.10,1.10,1.45],2:[2.15,1.10,1.10,1.10,1.45],
3:[1.35,5.55],4:[1.35,5.55],
5:[1.10,1.20,2.20,2.40],6:[.50,2.20,1.00,1.60,1.60],
7:[.50,1.50,1.40,1.50,2.00],8:[.45,1.25,1.45,1.25,1.40,1.10],
9:[.50,2.20,1.00,1.60,1.60],10:[.50,2.20,1.00,1.60,1.60],
11:[2.30,1.12,1.74,1.74],12:[2.00,1.15,2.00,1.75],
13:[3.9,3.0],14:[2.55,1.45,1.45,1.45],15:[.70,3.10,3.10]}
table_count=0
def make_table(rows,key):
    global table_count
    table_count+=1
    n=len(rows[0]);widths=TABLE_WIDTHS.get(table_count)
    if widths is None or len(widths)!=n:
        weights=[max(10,min(42,max(len(c.content) for c in col))) for col in zip(*rows)]
        widths=[WIDTH*w/sum(weights) for w in weights]
    else:widths=[WIDTH*w/sum(widths) for w in widths]
    tab=doc.add_table(rows=0,cols=n);tab.alignment=WD_TABLE_ALIGNMENT.CENTER;tab.autofit=False
    pr=tab._tbl.tblPr
    borders=OxmlElement('w:tblBorders')
    for side in ['top','left','bottom','right','insideH','insideV']:
        e=OxmlElement('w:'+side);e.set(qn('w:val'),'single');e.set(qn('w:sz'),'4');e.set(qn('w:color'),'D9D9D9');borders.append(e)
    pr.append(borders)
    for c,w in zip(tab.columns,widths):c.width=Inches(w)
    for ri,row in enumerate(rows):
        cells=tab.add_row().cells
        trpr=tab.rows[-1]._tr.get_or_add_trPr()
        ns=OxmlElement('w:cantSplit');trpr.append(ns)
        if ri==0:
            repeat=OxmlElement('w:tblHeader');trpr.append(repeat)
        for ci,(cell,tok,w) in enumerate(zip(cells,row,widths)):
            cell.width=Inches(w);cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            cp=cell._tc.get_or_add_tcPr();mar=OxmlElement('w:tcMar')
            for side,val in [('top',75),('bottom',75),('left',85),('right',85)]:
                z=OxmlElement('w:'+side);z.set(qn('w:w'),str(val));z.set(qn('w:type'),'dxa');mar.append(z)
            cp.append(mar)
            sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'E9EFF4' if ri==0 else ('F8F9FA' if ri%2==0 else 'FFFFFF'));cp.append(sh)
            p=cell.paragraphs[0]
            p.paragraph_format.line_spacing=Pt(12.5);p.paragraph_format.space_after=Pt(1)
            p.paragraph_format.keep_together=True;p.paragraph_format.widow_control=True
            if table_count in [1,2,6,7,8,9,10,11,12,13,14] and ri<len(rows)-1:
                p.paragraph_format.keep_with_next=True
            p.alignment=WD_ALIGN_PARAGRAPH.LEFT if ci==0 or len(tok.content)>24 else WD_ALIGN_PARAGRAPH.CENTER
            inline(p,tok.children,10)
            if ri==0:
                for r in p.runs:r.bold=True
    spacer=doc.add_paragraph();spacer.paragraph_format.space_after=Pt(1);spacer.paragraph_format.space_before=Pt(0)
    spacer.paragraph_format.line_spacing=Pt(3)
    manifest['modules'][key].setdefault('tables',[]).append({'number':table_count,'rows':len(rows),'columns':n})

def render_module(key,heading_level,reference=False):
    text=prep_math(extract(key))
    toks=md.parse(text);i=0;list_prefix=[]
    while i<len(toks):
        t=toks[i]
        if t.type=='heading_open':
            content=toks[i+1].content
            sourcelevel=int(t.tag[1:])
            heading(content,min(3,heading_level+sourcelevel-2))
            i+=3;continue
        if t.type=='table_open':
            rows=[];row=[];i+=1
            while toks[i].type!='table_close':
                if toks[i].type=='tr_open':row=[]
                elif toks[i].type=='inline':row.append(toks[i])
                elif toks[i].type=='tr_close':rows.append(row)
                i+=1
            make_table(rows,key);i+=1;continue
        if t.type=='fence':
            if t.info=='mermaid':
                add_figure(draw_flow(t.content),'图3 两轮研究的目标与方法衔接',key)
            elif t.info=='math':
                eq=t.content.strip()
                # Break long multi-expression equations at existing separators.
                parts=re.split(r',\s*\\qquad\s*',eq) if key=='W11' and ('widehat' in eq or 'mathcal L' in eq) else [eq]
                for j,part in enumerate(parts):
                    if j<len(parts)-1:part+=','
                    p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
                    p.paragraph_format.line_spacing=1.0
                    p.paragraph_format.space_before=Pt(5);p.paragraph_format.space_after=Pt(7)
                    p.paragraph_format.keep_together=True
                    if j<len(parts)-1:p.paragraph_format.keep_with_next=True
                    insert_math(p,part,True)
            else:raise ValueError('Unexpected fence '+t.info)
            i+=1;continue
        if t.type in ['ordered_list_open','bullet_list_open']:
            list_prefix.append({'num':int(t.attrGet('start') or 1),'ordered':t.type=='ordered_list_open'})
        elif t.type in ['ordered_list_close','bullet_list_close']:list_prefix.pop()
        elif t.type=='paragraph_open':
            token=toks[i+1]
            if len(token.children)==1 and token.children[0].type=='image':
                it=token.children[0];path=(files[key].parent/unquote(it.attrGet('src'))).resolve()
                add_figure(path,it.content,key);i+=3;continue
            is_caption=bool(re.match(r'\*\*(?:图|表)\d+',token.content))
            p=doc.add_paragraph(style='Reference' if reference else ('Caption' if is_caption else 'Normal'))
            p.alignment=WD_ALIGN_PARAGRAPH.LEFT if reference or is_caption else WD_ALIGN_PARAGRAPH.JUSTIFY
            if is_caption:
                p.paragraph_format.keep_together=True
                p.paragraph_format.keep_with_next=token.content.startswith('**表')
                p.paragraph_format.space_after=Pt(7)
            if list_prefix:
                lp=list_prefix[-1]
                prefix=(str(lp['num'])+'. ') if lp['ordered'] else '• '
                format_run(p.add_run(prefix))
                p.paragraph_format.left_indent=Inches(.16)
                p.paragraph_format.first_line_indent=Inches(-.16)
                lp['num']+=1
            inline(p,token.children,10.5 if reference else (10 if is_caption else BODY_SIZE))
            # Prefix is structural numbering, outside the source sentence comparison.
            if list_prefix:
                pp,exp=expected_paragraphs[-1];expected_paragraphs[-1]=(pp,prefix+exp)
            i+=3;continue
        elif t.type not in ['list_item_open','list_item_close','html_block']:
            raise ValueError(f'Unexpected block {t.type} in {key}')
        i+=1

chapters=[
 ('研究问题与背景','ch1'),('研究区域与数据处理','ch2'),('实验设计与评价方法','ch3'),
 ('首轮研究建模与迭代','ch4'),('次轮研究五步骤模型比较','ch5'),
 ('七天预测分布与区域去向','ch6'),('综合讨论 局限与未来研究','ch7'),
 ('结论与NOAA建议','ch8'),('数据与代码获取说明','ch9'),
 ('AI使用与协作反思','ch10'),('References','references')]

def build(page_map):
    p=doc.add_paragraph('历史漂流器轨迹与七天去向预测研究',style='Title')
    p.paragraph_format.space_after=Pt(10)
    p=doc.add_paragraph('Gulf Stream 南段',style='Subtitle');p.paragraph_format.space_after=Pt(10)
    p=doc.add_paragraph('DATA3001 Final Report');p.paragraph_format.space_after=Pt(3)
    p=doc.add_paragraph('2026年11月21日');p.paragraph_format.space_after=Pt(25)
    heading('摘要',1,'abstract',False);render_module('W18',2)
    doc.add_page_break()
    p=doc.add_paragraph('目录');format_run(p.runs[0],14,True);p.paragraph_format.space_after=Pt(12)
    p=doc.add_paragraph(style='TOC Entry')
    add_link(p,'摘要','abstract',11,True)
    format_run(p.add_run('\t'+str(page_map.get('abstract','—'))),11)
    for ix,(title,anchor) in enumerate(chapters):
        p=doc.add_paragraph(style='TOC Entry')
        label=(str(ix+1)+'  ' if ix<10 else '')+title
        add_link(p,label,anchor,11,True)
        format_run(p.add_run('\t'+str(page_map.get(anchor,'—'))),11)
    doc.add_page_break()
    heading(chapters[0][0],1,'ch1')
    heading('研究问题与范围',2);render_module('W01',3)
    heading('研究背景与文献',2);render_module('W02',3)
    heading(chapters[1][0],1,'ch2')
    heading('区域选择与R和D的定义',2);render_module('W03',3)
    heading('数据来源与处理',2);render_module('W04',3)
    heading(chapters[2][0],1,'ch3');render_module('W05',2)
    heading(chapters[3][0],1,'ch4');render_module('W06',2)
    heading(chapters[4][0],1,'ch5')
    step_titles=[
       ('W07','Step1 Empirical Transition Matrix 经验转移矩阵'),
       ('W08','Step2 Regularised Transition Matrix 正则化转移矩阵'),
       ('W09','Step3 Spatial Information Sharing 空间信息共享'),
       ('W10','Step4 Conditional Information and Exact Starting Position 条件信息与精确起点'),
       ('W11','Step5 Continuous Transition Distributions 连续转移分布')]
    for key,title in step_titles:heading(title,2);render_module(key,3)
    heading(chapters[5][0],1,'ch6');render_module('W12',2)
    heading(chapters[6][0],1,'ch7');render_module('W13',2)
    heading(chapters[7][0],1,'ch8');render_module('W14',2)
    heading(chapters[8][0],1,'ch9')
    doc.add_paragraph('代码架构整理完成后补充',style='Pending Subtitle')
    p=files['W15'];manifest['sources']['W15']={'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    manifest['modules']['W15']={'section':'第9章','status':'subtitle only; checklist excluded by user instruction'}
    heading(chapters[9][0],1,'ch10');render_module('W16',2)
    p=heading('References',1,'references',False);p.paragraph_format.page_break_before=True
    render_module('W17',2,True)
    foot=section.footer.paragraphs[0];foot.alignment=WD_ALIGN_PARAGRAPH.CENTER
    format_run(foot.add_run('第 '),9)
    for field,after in [('PAGE',' 页 / 共 '),('NUMPAGES',' 页')]:
        r=foot.add_run();f=OxmlElement('w:fldSimple');f.set(qn('w:instr'),field)
        rr=OxmlElement('w:r');rp=OxmlElement('w:rPr');font_props(rp,9);rr.append(rp)
        tt=OxmlElement('w:t');tt.text='1';rr.append(tt);f.append(rr);r._r.addnext(f)
        format_run(foot.add_run(after),9)
    for p,expected in expected_paragraphs:
        actual=''.join(x.text or '' for x in p._p.xpath('.//w:t'))
        assert actual==expected,(actual[:100],expected[:100])
    manifest['paragraph_checks']=len(expected_paragraphs)
    manifest['table_count']=table_count
    manifest['headings']=headings
    manifest['page_map']=page_map
    manifest['layout']={'paper':'Letter portrait','margins_inches':.65,
                        'body_font_size_pt':BODY_SIZE,'body_line_height_pt':14,
                        'chinese_font':CJK,'latin_font':LATIN,
                        'render_fontconfig':str(TEMP/'fonts.conf')}
    manifest['output']=OUTPUT.name
    doc.save(OUTPUT)
    manifest['output_sha256']=hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    (ROOT/'assembly'/'source_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    print(json.dumps({'output':str(OUTPUT),'figures':len(manifest['figures']),'tables':table_count,
                      'math_objects':len(manifest['equations']),'checked_paragraphs':len(expected_paragraphs)},ensure_ascii=False))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--page-map');args=ap.parse_args()
    build(json.loads(Path(args.page_map).read_text()) if args.page_map else {})
