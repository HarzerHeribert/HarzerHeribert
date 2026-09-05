"""One SVG instrument system. Geometry is deterministic; motion is ornamental."""
import collections
import datetime as dt
import html
import math
from public_data import validate, stamp, VERSION

PALETTES = {
 'dark': dict(bg='#080d12', panel='#0d151d', line='#263844', muted='#91a6b5', ink='#edf5f7', cyan='#64e8ea', orange='#ffad70', dot='#1a2c37'),
 'light': dict(bg='#f3f0e7', panel='#e9e6dc', line='#b9c1bf', muted='#52646b', ink='#182b36', cyan='#006779', orange='#ac480e', dot='#ced3cd'),
}

def esc(value):
    return html.escape(str(value), quote=True)

class Surface:
    def __init__(self, theme, height, title, description):
        self.p = PALETTES[theme]
        self.h = height
        p=self.p
        self.parts=[f'''<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="{height}" viewBox="0 0 1080 {height}" role="img" aria-labelledby="title desc">
<title id="title">{esc(title)}</title><desc id="desc">{esc(description)}</desc>
<defs><pattern id="dots" width="12" height="12" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="0.7" opacity=".5" fill="{p['dot']}"/></pattern></defs>
<style>
text{{font-family:ui-monospace,SFMono-Regular,Consolas,'Liberation Mono',monospace;fill:{p['ink']}}}
.micro{{font-size:11px;letter-spacing:1.5px;fill:{p['muted']}}}.small{{font-size:13px;fill:{p['muted']}}}
.label{{font-size:12px;letter-spacing:1.1px}}.title{{font-family:Arial,Helvetica,sans-serif;font-weight:700;letter-spacing:-3px}}
.packet{{animation:travel 28s linear infinite}}.led{{animation:breathe 24s ease-in-out infinite}}.cursor{{animation:breathe 4s ease-in-out infinite}}
@keyframes travel{{0%{{transform:translateX(0);opacity:0}}8%{{opacity:.8}}90%{{opacity:.8}}100%{{transform:translateX(880px);opacity:0}}}}
@keyframes breathe{{0%,100%{{opacity:.35}}50%{{opacity:1}}}}
@media(prefers-reduced-motion:reduce){{.packet,.led,.cursor{{animation:none}}.packet{{display:none}}}}
</style>
<rect width="1080" height="{height}" rx="12" fill="{p['bg']}"/>
<rect x="1" y="1" width="1078" height="{height-2}" rx="11" fill="url(#dots)" stroke="{p['line']}"/>
<path d="M24 44V24H44 M1036 24H1056V44 M24 {height-44}V{height-24}H44 M1036 {height-24}H1056V{height-44}" fill="none" stroke="{p['cyan']}" stroke-width="1"/>''']
    def add(self,s): self.parts.append(s)
    def text(self,x,y,value,cls='',size=None,color=None,extra=''):
        self.add(f'<text x="{x}" y="{y}" class="{cls}"'+(f' font-size="{size}"' if size else '')+(f' style="fill:{self.p[color]}"' if color else '')+f' {extra}>{esc(value)}</text>')
    def line(self,x1,y1,x2,y2,color='line',extra=''):
        self.add(f'<path d="M{x1} {y1}H{x2}" stroke="{self.p[color]}" {extra}/>' if y1==y2 else f'<path d="M{x1} {y1}L{x2} {y2}" stroke="{self.p[color]}" {extra}/>')
    def rect(self,x,y,w,h,color='panel',extra=''):
        self.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{self.p[color]}" {extra}/>')
    def circle(self,x,y,r,color='cyan',extra=''):
        self.add(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{self.p[color]}" {extra}/>')
    def end(self):return '\n'.join(self.parts)+ '\n</svg>\n'

def recent(m):
    end=stamp(m['generated'])
    start=end.replace(hour=0,minute=0,second=0)-dt.timedelta(days=29)
    return [e for e in m['events'] if start<=stamp(e['at'])<=end]

def shorten(s,n):return s if len(s)<=n else s[:n-1]+'…'

def marker(s,x,y,kind):
    c=s.p['orange'] if kind=='release' else s.p['cyan']
    if kind in ('pull_request','review'):
        s.add(f'<path d="M{x} {y-6}l6 6-6 6-6-6Z" fill="{c}"/>')
    elif kind in ('issue','comment'):
        s.add(f'<rect x="{x-5}" y="{y-5}" width="10" height="10" fill="{s.p["bg"]}" stroke="{c}"/>')
    elif kind=='release':
        s.circle(x,y,7,'orange');s.circle(x,y,3,'bg')
    elif kind=='star':
        s.add(f'<path d="M{x} {y-7}l2 5 5 2-5 2-2 5-2-5-5-2 5-2Z" fill="{c}"/>')
    elif kind=='push':s.circle(x,y,4)
    else:s.circle(x,y,4,'muted',extra='opacity=".8"')

def hero(m,theme):
    validate(m)
    events=recent(m); repos=m['repositories']
    languages=set().union(*(r['languages'] for r in repos)) if repos else set()
    rows=sorted(repos,key=lambda r:(r['pushedAt'] or '',r['name']),reverse=True)[:6]
    h=550+max(len(rows),1)*49
    s=Surface(theme,h,'HarzerHeribert / public systems',f"Anonymous public GitHub snapshot: {len(repos)} repositories, {len(languages)} languages, {len(events)} sampled events over 30 UTC dates. Not a complete activity history.")
    s.text(48,52,'HH / PUBLIC SYSTEMS','micro',color='cyan')
    s.text(44,146,'HarzerHeribert','title',66)
    s.text(48,181,'Public systems.','small')
    s.line(48,215,1032,215)
    for i,(value,label) in enumerate([(len(repos),'REPOSITORIES'),(len(events),'PUBLIC EVENTS / 30D'),(len(languages),'LANGUAGES')]):
        x=48+i*342
        s.text(x,276,f'{value:02}',size=38)
        s.text(x+83,274,label,'micro')
    s.line(48,307,1032,307)
    s.text(48,342,'REPOSITORIES','micro')
    for i,r in enumerate(rows):
        y=383+i*49
        s.text(48,y,r['name'],size=18)
        s.text(760,y,r['primaryLanguage'] or 'No language data','small')
        total=sum(r['languages'].values()); primary=r['languages'].get(r['primaryLanguage'],0)
        s.rect(946,y-8,86,2,'line')
        if total:s.rect(946,y-8,round(86*primary/total,2),2,'cyan')
    if not rows:s.text(48,383,'No public repositories observed.','small')
    y=378+max(len(rows),1)*49
    s.line(48,y,1032,y)
    s.text(48,y+35,'RECENT PUBLIC EVENTS','micro')
    s.line(60,y+69,1020,y+69)
    for i,e in enumerate(events[-12:]):marker(s,72+i*85,y+69,e['kind'])
    if not events:s.text(65,y+94,'No events observed in this window.','small')
    s.rect(60,y+68,10,2,'cyan',extra='class="packet"')
    s.line(48,y+111,1032,y+111)
    s.text(48,y+139,m['generated'].replace('T',' ').replace('Z',' UTC')+'  /  '+m['revision'][:12],'micro')
    return s.end()

def activity(m,theme):
    validate(m)
    events=recent(m);end=stamp(m['generated']).date();start=end-dt.timedelta(days=29)
    counts=collections.Counter(e['at'][:10] for e in events)
    peak=max(counts.values(),default=0)
    s=Surface(theme,336,'Public signal / 30 UTC dates','Daily counts from the current bounded anonymous event feed. Empty cells mean no event in this sample, not proof of inactivity. Today is partial.')
    s.text(42,49,'PUBLIC SIGNAL','label',color='cyan');s.text(1038,49,'30 UTC DATES / TODAY PARTIAL','micro',extra='text-anchor="end"')
    s.line(42,68,1038,68)
    s.text(42,100,f'{len(events):02} OBSERVED EVENTS','label');s.text(1038,100,f'PEAK {peak:02} / DAY','micro',extra='text-anchor="end"')
    for i in range(30):
        date=start+dt.timedelta(days=i); count=counts[date.isoformat()]; x=43+i*33.5
        cells=math.ceil(count/peak*8) if peak else 0
        for j in range(8):s.rect(x,227-j*13,24,8,'cyan' if j<cells else 'dot',extra=f'opacity="{.5+j*.065:.3f}"' if j<cells else '')
        if count:s.text(x+12,118,count,'micro',extra='text-anchor="middle"')
    s.text(42,261,start.isoformat(),'micro');s.text(1038,261,end.isoformat(),'micro',extra='text-anchor="end"')
    s.text(42,296,'Sampled public events. Empty cells indicate no event in this sample.','micro')
    return s.end()

def topology(m,theme):
    validate(m)
    repos=m['repositories']; langs=sorted({r['primaryLanguage'] for r in repos if r['primaryLanguage']})
    height=max(440,180+max(len(repos),len(langs))*74)
    s=Surface(theme,height,'Public repository topology','Edges mean only that GitHub reports this primary language for this public repository. No dependency or semantic relationships are inferred.')
    s.text(42,49,'REPOSITORY / LANGUAGE','label',color='cyan');s.text(1038,49,'PUBLIC METADATA','micro',extra='text-anchor="end"')
    s.line(42,68,1038,68)
    s.text(42,102,'PUBLIC REPOSITORY','micro');s.text(773,102,'LANGUAGE CHANNEL','micro')
    positions={lang:143+i*74 for i,lang in enumerate(langs)}
    for i,r in enumerate(repos):
        y=143+i*74
        lang=r['primaryLanguage']
        s.rect(42,y-22,347,51)
        s.text(58,y,r['name'],size=17)
        s.text(58,y+18,shorten(' / '.join(r['topics']) if r['topics'] else '',42),'micro')
        if lang:
            dest=positions[lang];via=464+i*33
            s.add(f'<path d="M389 {y}H{via}V{dest}H755" fill="none" stroke="{s.p["line"]}"/>')
            s.circle(389,y,3);s.circle(755,dest,4,'cyan',extra='class="led"')
        else:s.text(425,y,'NO LANGUAGE DATA','micro')
    for lang,y in positions.items():
        s.rect(773,y-22,265,51)
        s.text(789,y,lang,size=17,color='cyan')
        count=sum(r['primaryLanguage']==lang for r in repos)
        s.text(789,y+18,f'{count:02} REPOSITORY'+('' if count==1 else ' ENTRIES'),'micro')
    if not repos:s.text(42,165,'No public nodes available.','small')
    s.line(42,height-67,1038,height-67)
    s.text(42,height-38,'Primary language reported by GitHub.','micro')
    return s.end()

def render_all(model):
    validate(model)
    return {f'{name}-{theme}.svg': fn(model,theme) for name,fn in [('hero',hero),('activity',activity),('topology',topology)] for theme in PALETTES}
