import ast
import copy
import hashlib
import http.client
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from public_data import AnonymousGitHub, PolicyError, SourceError, collect, repository, route, validate, WEB, API, USER
from render import render_all
NOW='2026-09-06T12:00:00Z'
REV='a'*40

class FakeGitHub:
    """Synthetic PUBLIC fixtures; never used for publication."""
    def __init__(self, empty=False):self.audit=[];self.empty=empty
    def pages(self,base,maximum=10):return self.get(base+'&page=1')
    def get(self,path):
        route(path)
        self.audit.append(dict(url=API+path,status=200,sha256='0'*64,authentication='none'))
        repo=dict(name='fixture',full_name=USER+'/fixture',html_url=WEB+'/fixture',private=False,visibility='public',description='A < B & "C"',language='Python',topics=['testing'],pushed_at=None)
        if path.endswith('/languages'):return {'Python':100,'Shell':5}
        if '/releases?' in path:return []
        if '/events/public?' in path:return [] if self.empty else [dict(id='1',public=True,actor={'login':USER},repo={'name':USER+'/fixture'},type='PushEvent',created_at='2026-09-05T11:00:00Z')]
        if '/repos?' in path:return [] if self.empty else [repo]
        if '/repos/' in path:return repo
        return dict(login=USER,html_url=WEB,name=None)

def fixture(empty=False):return collect(FakeGitHub(empty),NOW,REV)

class ModelTests(unittest.TestCase):
    def test_public_provenance_required(self):
        for group in ['repositories','events']:
            for key in ['sourceVisibility','sourceType','sourceUrl']:
                m=fixture();del m[group][0][key]
                with self.subTest(group=group,key=key),self.assertRaises(PolicyError):validate(m)
    def test_private_rejected(self):
        m=fixture();m['repositories'][0]['sourceVisibility']='private'
        with self.assertRaises(PolicyError):validate(m)
    def test_anonymous_resolution_required(self):
        m=fixture();m['sources']=[s for s in m['sources'] if s['url']!=API+'/repos/'+USER+'/fixture']
        with self.assertRaises(PolicyError):render_all(m)
    def test_collector_rechecks_each_repository(self):
        client=FakeGitHub();original=client.get
        def get(path):
            if path==f'/repos/{USER}/fixture':raise SourceError('HTTP 404')
            return original(path)
        client.get=get
        with self.assertRaises(SourceError):collect(client,NOW,REV)
    def test_private_repository_refused_at_ingress(self):
        for private,visibility in [(True,'private'),(False,'private'),(None,'public')]:
            with self.assertRaises(PolicyError):repository(dict(private=private,visibility=visibility))
    def test_private_event_refused(self):
        client=FakeGitHub();original=client.get
        def get(path):
            data=original(path)
            if '/events/public?' in path:data[0]['public']=False
            return data
        client.get=get
        with self.assertRaises(PolicyError):collect(client,NOW,REV)
    def test_unknown_extra_field_rejected(self):
        m=fixture();m['repositories'][0]['privateContributionCount']=123
        with self.assertRaises(PolicyError):validate(m)
    def test_missing_fields(self):
        m=fixture();self.assertEqual(m['user']['name'],USER);self.assertIsNone(m['repositories'][0]['pushedAt'])
        del m['user']['name']
        with self.assertRaises(PolicyError):validate(m)
    def test_malformed_languages_and_topics(self):
        for field, values in [('languages',[[],{'Python':-1},{'Python':True},{'Python':'100'}]),('topics',['python',[None],['<script>']])]:
            for value in values:
                m=fixture();m['repositories'][0][field]=value
                with self.subTest(field=field,value=value),self.assertRaises(PolicyError):validate(m)
    def test_credential_material_rejected(self):
        for value in ['ghp_'+'a'*36,'github_pat_'+'a'*40,'Authorization: secret','Bearer abc']:
            m=fixture();m['repositories'][0]['description']=value
            with self.assertRaises(PolicyError):render_all(m)
    def test_foreign_links_rejected(self):
        for url in ['https://example.com','https://github.com/another/private','javascript:alert(1)',WEB+'/fixture/../../private']:
            m=fixture();m['repositories'][0]['sourceUrl']=url
            with self.assertRaises(PolicyError):render_all(m)
    def test_forged_authenticated_audit_rejected(self):
        m=fixture();m['sources'][0]['authentication']='token'
        with self.assertRaises(PolicyError):validate(m)
    def test_unknown_event_repository_rejected(self):
        m=fixture();m['events'][0]['repo']='private'
        with self.assertRaises(PolicyError):validate(m)
    def test_future_event_rejected(self):
        m=fixture();m['events'][0]['at']='2027-01-01T00:00:00Z'
        with self.assertRaises(PolicyError):validate(m)
    def test_old_events_excluded_from_window(self):
        m=fixture();m['events'][0]['at']='2024-01-01T00:00:00Z'
        self.assertIn('00 OBSERVED EVENTS',render_all(m)['activity-dark.svg'])

class TransportTests(unittest.TestCase):
    def test_closed_routes(self):
        for path in ['/user','/user/repos','/graphql','/users/HarzerHeribert/events','https://api.github.com/user','/users/HarzerHeribert/repos?visibility=private','/repos/HarzerHeribert/fixture?visibility=private','/repos/other/fixture','/repos/HarzerHeribert/../user','/repos/HarzerHeribert/%2e%2e','/users/HarzerHeribert?token=abc']:
            with self.subTest(path=path),self.assertRaises(PolicyError):route(path)
    def response(self,status=200,body=b'{}'):
        from unittest.mock import MagicMock
        conn=MagicMock();conn.getresponse.return_value.status=status;conn.getresponse.return_value.read.return_value=body
        return conn
    def test_transport_cannot_send_authorization(self):
        conn=self.response()
        with patch('public_data.http.client.HTTPSConnection',return_value=conn):AnonymousGitHub().get('/users/'+USER)
        args,kw=conn.request.call_args
        self.assertEqual(args,('GET','/users/'+USER))
        self.assertEqual(set(kw['headers']),{'Accept','User-Agent','X-GitHub-Api-Version'})
        self.assertNotIn('Authorization',kw['headers'])
        with self.assertRaises(TypeError):AnonymousGitHub().get('/users/'+USER,headers={'Authorization':'token'})
    def test_redirects_fail_closed(self):
        for status in [301,302,307,308,401,404,500,503]:
            with self.subTest(status=status),patch('public_data.http.client.HTTPSConnection',return_value=self.response(status)),self.assertRaises(SourceError):AnonymousGitHub().get('/users/'+USER)
    def test_rate_limits(self):
        for status in [403,429]:
            with patch('public_data.http.client.HTTPSConnection',return_value=self.response(status)),self.assertRaisesRegex(SourceError,'rate limited'):AnonymousGitHub().get('/users/'+USER)
    def test_bad_json(self):
        with patch('public_data.http.client.HTTPSConnection',return_value=self.response(body=b'<html>')),self.assertRaises(SourceError):AnonymousGitHub().get('/users/'+USER)
    def test_network_failure(self):
        conn=self.response();conn.request.side_effect=OSError('unavailable')
        with patch('public_data.http.client.HTTPSConnection',return_value=conn),self.assertRaises(SourceError):AnonymousGitHub().get('/users/'+USER)
    def test_request_budget(self):
        client=AnonymousGitHub();client.calls=50
        with self.assertRaisesRegex(SourceError,'budget'):client.get('/users/'+USER)
    def test_pagination_never_silently_truncates_catalog(self):
        client=AnonymousGitHub()
        with patch.object(client,'get',return_value=[{}]*100),self.assertRaisesRegex(SourceError,'page limit'):client.pages('/users/'+USER+'/repos?type=owner&per_page=100',maximum=2)
    def test_no_credentials_or_local_data_imports(self):
        tree=ast.parse((ROOT/'src/public_data.py').read_text())
        modules=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):modules += [a.name for a in node.names]
            if isinstance(node,ast.ImportFrom):modules.append(node.module)
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name):self.assertNotIn(node.func.id,{'open','eval','exec','__import__'})
        self.assertTrue(set(modules)<= {'datetime','hashlib','http.client','json','re','ssl','urllib.parse'})
        source=(ROOT/'src/public_data.py').read_text()
        self.assertNotIn('viewer {',source)
        self.assertNotIn('getenv(',source)
        self.assertNotIn('environ[',source)

class RenderTests(unittest.TestCase):
    def test_deterministic_and_valid_xml(self):
        first=render_all(fixture());self.assertEqual(first,render_all(fixture()))
        self.assertEqual(len(first),6)
        for name,svg in first.items():
            root=ET.fromstring(svg);self.assertEqual(root.tag,'{http://www.w3.org/2000/svg}svg')
            self.assertIn('prefers-reduced-motion',svg)
            self.assertNotIn('<script',svg);self.assertNotIn('<foreignObject',svg)
            self.assertNotIn('href=',svg) # README handles navigation; no hidden remote references.
        self.assertNotEqual(first['hero-dark.svg'],first['hero-light.svg'])
    def test_escaping(self):
        svg=render_all(fixture())['hero-dark.svg']
        self.assertIn('A &lt; B &amp; &quot;C&quot;',svg)
        ET.fromstring(svg)
    def test_zero_repos_empty_activity(self):
        outputs=render_all(fixture(True))
        self.assertIn('No anonymously resolvable',outputs['hero-dark.svg'])
        self.assertIn('No events observed',outputs['hero-light.svg'])
        self.assertIn('00 OBSERVED EVENTS',outputs['activity-dark.svg'])
    def test_snapshot_golden(self):
        actual={name:hashlib.sha256(svg.encode()).hexdigest() for name,svg in render_all(fixture()).items()}
        self.assertEqual(actual,json.loads((ROOT/'tests/golden.json').read_text()))
    def test_workflow_separates_public_collection_and_write_token(self):
        source=(ROOT/'.github/workflows/profile.yml').read_text()
        build,publish=source.split('  publish:')
        self.assertNotIn('github.token',build);self.assertNotIn('secrets.',build)
        self.assertIn('permissions: {}',build);self.assertIn('contents: write',publish)
        self.assertIn('persist-credentials: false',publish)
        self.assertIn('env -i PATH=/usr/bin:/bin python3 -I scripts/generate.py',build)
        self.assertNotIn('scripts/generate.py',publish)
        self.assertIn('git add -- assets/generated/',publish)

if __name__=='__main__':unittest.main()
