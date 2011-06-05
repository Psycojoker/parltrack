#!/usr/bin/env python
# -*- coding: utf-8 -*-
#    This file is part of parltrack.

#    parltrack is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

#    parltrack is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.

#    You should have received a copy of the GNU Affero General Public License
#    along with parltrack.  If not, see <http://www.gnu.org/licenses/>.

# (C) 2011 by Stefan Marsiske, <stefan.marsiske@gmail.com>

from lxml import etree
from lxml.html.soupparser import parse
from lxml.etree import tostring
from cStringIO import StringIO
from urlparse import urljoin
from tempfile import mkstemp
from time import mktime, strptime
from datetime import datetime
import urllib2, sys, subprocess, re, os, json

datere=re.compile(r'^([0-9]{1,2} \w+ [0-9]{4}, [0-9]{2}\.[0-9]{2})(?: . [0-9]{2}\.[0-9]{2})?.*')
block_start=re.compile(r'^([0-9]+)\. {,10}(.*)')
fields=[(re.compile(r'^ {,10}Rapporteur: {3,}(.*)'),"Rapporteur"),
        (re.compile(r'^ {,10}Co-rapporteur\(s\): {3,}(.*)'),"Rapporteur"),
        (re.compile(r'^ {,10}Rapporteur for(?: the)? (.*)'),"Shadow Rapporteur"),
        (re.compile(r'^ {,10}Responsible: {3,}(.*)'),'Responsible'),
        (re.compile(r'^ {,10}Opinions: {3,}(.*)'),"Opinions"),
        ]
#misc_block=re.compile(r'^ {,10}\xef\x82\xb7 {3,}(.*)')
misc_block=re.compile(u'^ {,10}\uf0b7 {3,}(.*)')
opinon_junk=re.compile(r'^ {,10}opinion: {3,}(.*)')
comref_re=re.compile(r' {3,}(COM\([0-9]{4}\)[0-9]{4})')
mepre=re.compile(r'(.*) \((.*)\)$')
COMMITTEE_MAP={'AFET': "Foreign Affairs",
               'DROI': "Human Rights",
               'SEDE': "Security and Defence",
               'DEVE': "Development",
               'INTA': "International Trade",
               'BUDG': "Budgets",
               'CONT': "Budgetary Control",
               'ECON': "Economic and Monetary Affairs",
               'EMPL': "Employment and Social Affairs",
               'ENVI': "Environment, Public Health and Food Safety",
               'ITRE': "Industry, Research and Energy",
               'IMCO': "Internal Market and Consumer Protection",
               'TRAN': "Transport and Tourism",
               'REGI': "Regional Development",
               'AGRI': "Agriculture and Rural Development",
               'PECH': "Fisheries",
               'CULT': "Culture and Education",
               'JURI': "Legal Affairs",
               'LIBE': "Civil Liberties, Justice and Home Affairs",
               'AFCO': "Constitutional Affairs",
               'FEMM': "Women's Rights and Gender Equality",
               'PETI': "Petitions",
               'CRIS': "Financial, Economic and Social Crisis",
               'SURE': "Policy Challenges Committee",
               'Foreign Affairs': 'AFET',
               'Human Rights': 'DROI',
               'Security and Defence': 'SEDE',
               'Development': 'DEVE',
               'International Trade': 'INTA',
               'Budgets': 'BUDG',
               'Budgetary Control': 'CONT',
               'Economic and Monetary Affairs': 'ECON',
               'Employment and Social Affairs': 'EMPL',
               'Environment, Public Health and Food Safety': 'ENVI',
               'Industry, Research and Energy': 'ITRE',
               'Internal Market and Consumer Protection': 'IMCO',
               'Transport and Tourism': 'TRAN',
               'Regional Development': 'REGI',
               'Agriculture and Rural Development': 'AGRI',
               'Fisheries': 'PECH',
               'Culture and Education': 'CULT',
               'Legal Affairs': 'JURI',
               'Civil Liberties, Justice and Home Affairs': 'LIBE',
               'Constitutional Affairs': 'AFCO',
               "Women's Rights and Gender Equality": 'FEMM',
               'Petitions': 'PETI',
               'Financial, Economic and Social Crisis': 'CRIS',
               'Policy Challenges Committee': 'SURE'}

def fetch(url):
    # url to etree
    #print >> sys.stderr, url
    f=urllib2.urlopen(url)
    raw=parse(f)
    f.close()
    return raw

def scrape(comid, url):
    f=urllib2.urlopen(url)
    tmp=mkstemp()
    fd=os.fdopen(tmp[0],'w')
    fd.write(f.read())
    fd.close()
    f.close()
    lines=subprocess.Popen(['pdftotext', '-x', '0', '-y', '20', '-W', '1000', '-H', '740', '-nopgbrk', '-layout', tmp[1], '-'],
                     stdout=subprocess.PIPE).communicate()[0].split('\n')

    os.unlink(tmp[1])
    inblock=False
    res=[]
    state=None
    issue=None
    ax=['','']
    meeting_date=None
    for (i,line) in enumerate(lines):
        if not len(line): continue
        line=line.decode('utf8')
        # start a new meeting agenda
        m=datere.match(line)
        if m and not inblock:
            meeting_date=datetime.fromtimestamp(mktime(strptime(m.group(1),"%d %B %Y, %H.%M")))
            continue
        # start of a new agenda item
        m=block_start.match(line)
        if m:
            inblock=True
            if ax[0] in ['Opinions', 'Responsible']:
                issue[ax[0]]=scrapOp(ax[1])
            elif ax[0] in ['Rapporteur', 'Shadow Rapporteur']:
                issue[ax[0]]=scrapRap(ax[1])
            elif ax[0]:
                issue[ax[0]]=ax[1]
            if issue:
                if meeting_date:
                    issue['meeting_date']=meeting_date
                res.append(issue)
            issue={'committee': comid,'seq_no': int(m.group(1)), 'src': url}
            ax=['title', m.group(2)]
            continue
        # ignore all lines not in agenda items
        if not line[0]==' ':
            inblock=False
            continue
        # check for common fields
        newfield=False
        for field in fields:
            m=field[0].match(line)
            if m:
                if ax[0] in ['Opinions', 'Responsible']:
                    issue[ax[0]]=scrapOp(ax[1])
                elif ax[0] in ['Rapporteur', 'Shadow Rapporteur']:
                    issue[ax[0]]=scrapRap(ax[1])
                elif ax[0]:
                    issue[ax[0]]=ax[1]
                ax=[field[1], m.group(1)]
                newfield=True
                break
        if newfield:
            continue
        # parse misc agenda items
        m=misc_block.match(line)
        if m:
            issue['Misc']=issue.get('Misc',[])
            issue['Misc'].append(m.group(1))
            if m.group(1).startswith('Deadline for tabling amendments:'):
                issue['tabling_deadline']=datetime.fromtimestamp(mktime(strptime(m.group(1).split(':')[1].strip(),"%d %B %Y, %H.%M")))
            continue

        if inblock and len(line.strip()):
            if ax[0]=='Rapporteur (opinion)':
                m=opinon_junk.match(line)
                if m or line=='opinion:':
                    ax[1]="%s\n%s" % (ax[1],m.group(1))
            elif ax[0]=='title':
                m=comref_re.search(line)
                if m:
                    issue['comdoc']=m.group(1)
            ax[1]="%s\n%s" % (ax[1],line)

    print >>sys.stderr, '\n'.join(["%s %s %s" % (i['tabling_deadline'].isoformat(),
                                    comid.strip(),
                                    i.get('comref',i['title'].split('\n')[-2].strip()),
                                    )
                      for i in res
                      if 'tabling_deadline' in i]).encode('utf8') or "no deadlines"
    sys.stderr.flush()
    return res

def dateJSONhandler(obj):
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    elif type(obj)==ObjectId:
        return str(obj)
    else:
        raise TypeError, 'Object of type %s with value of %s is not JSON serializable' % (type(obj), repr(obj))

def crawl():
    result=[]
    tree=fetch("http://www.europarl.europa.eu/activities/committees/committeesList.do?language=EN")
    select=tree.xpath('//a[@class="commdocmeeting"]')
    for committee_url in select:
        comid=committee_url.xpath('../../td/a')[0].text.strip()
        print >>sys.stderr, 'checking', comid
        cmurl='http://www.europarl.europa.eu'+committee_url.get('href')
        commeets=fetch(cmurl)
        cmtree=commeets.xpath('//td/a')
        murl=urljoin(cmurl,cmtree[0].get('href'))
        mtree=fetch(murl)
        pdflink=mtree.xpath("//td[contains(translate(text(),'abcdefghijklmnopqrstuvwxyz','ABCDEFGHIJKLMNOPQRSTUVWXYZ'),'DRAFT AGENDA') or text() = 'Draft programme']/..//a[text() = 'en']")
        if not pdflink:
            pdflink=mtree.xpath(u"//td[contains(text(),'OJ-réunion')]/..//a[text() = 'en']")
        if not pdflink:
            pdflink=mtree.xpath("//td[contains(translate(text(),'abcdefghijklmnopqrstuvwxyz','ABCDEFGHIJKLMNOPQRSTUVWXYZ'),'AGENDA') or contains(translate(text(),'abcdefghijklmnopqrstuvwxyz','ABCDEFGHIJKLMNOPQRSTUVWXYZ'),'PROGRAMME')]/..//a[text() = 'en']")
        if pdflink:
            url=pdflink[0].get('href')
            try:
                data=scrape(comid,url)
            except:
                print >>sys.stderr, 'url', url
                raise
            result.append(data)
        else:
            print >> sys.stderr, '[!] Warning: no agenda/programme found', comid, murl
    if len(result):
        print json.dumps(result,indent=1,default=dateJSONhandler)

docre=re.compile(u'(.*)([A-Z][A-Z] \u2013 \S+)$')
def scrapRap(text):
    res={'docs':[],
         'rapporteurs':[]}
    tail=''
    for line in text.split('\n'):
        if line.strip().startswith(u"opinion:"):
            line=line.strip()[8:].strip()
        else:
            line=line.strip()
        m=docre.search(line)
        if m:
            res['docs'].append(m.group(2).split(u' \u2013 '))
            line=m.group(1).strip()
        if line:
            if tail:
                line="%s %s" % (tail, line)
            m=getMep(line)
            if not m:
                tail=line
                print >>sys.stderr, "[!] docre oops:", line.encode('utf8')
            else:
                res['rapporteurs'].append(m)
                tail=''
    return res

def getMep(text):
    if not text.strip(): return
    m=mepre.search(text.strip())
    if m:
        group=m.group(2).strip()
        if group==None:
            return None
        else:
            return {'name': m.group(1),
                    'group': m.group(2)}

comre=re.compile(u'([A-Z]{4})(?: \(AL\)|\*? –)(.*)')
comlistre=re.compile(u'[A-Z]{4}(?:(?: \u2013|,) [A-Z]{4})*')
def scrapOp(text):
    res=[]
    c={'docs':[], 'rapporteurs': []}
    tail=''
    for line in text.split('\n'):
        if line.startswith(u"opinion:"):
            line=line[8:].strip()
        m=docre.search(line)
        if m:
            c['docs'].append(m.group(2).split(u' \u2013 '))
            line=m.group(1).strip()

        m=comre.search(line)
        if m:
            if tail:
                c['tail']=tail.strip()
                tail=''
            if 'committee' in c:
                res.append(c)
            c={'committee': m.group(1),
               'docs':[],
               'rapporteurs': []}
            line=m.group(2).strip()
        if not len(line.strip()):
            continue
        if line=='Decision: no opinion':
            c['response']='Decision: no opinion'
            continue
        if line.strip() in ['***']:
            continue
        if comlistre.match(line):
            c['committees']=line.split(', ')
            continue
        if len(tail):
            if line.strip().startswith(u'\u2013'):
                line=line.strip()[1:]
            line=' '.join((tail, line.strip()))
            tail=''
        m=getMep(line)
        if m:
            c['rapporteurs'].append(m)
            line=''
        if line.strip():
            tail=line.strip()
    if 'committee' in c:
        if tail:
            c['tail']=tail.strip()
        res.append(c)
    return res


if __name__ == "__main__":
    crawl()
    #print json.dumps(scrape('LIBE','http://www.europarl.europa.eu/meetdocs/2009_2014/documents/libe/oj/867/867690/867690en.pdf'),indent=1,default=dateJSONhandler)
    # find some tabling dates: db.ep_com_meets.find({'tabling_deadline' : { $exists : true }}).sort({'tabling_deadline': -1})
