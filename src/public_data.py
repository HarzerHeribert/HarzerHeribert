"""Anonymous, fixed-host, closed-route GitHub collector. Standard library only."""
import datetime as dt
import hashlib
import http.client
import json
import re
import ssl
from urllib.parse import urlencode

USER = 'HarzerHeribert'
WEB = f'https://github.com/{USER}'
API = 'https://api.github.com'
VERSION = '1.0.0'
NAME = r'[A-Za-z0-9_.-]+'
SECRET = re.compile(r'(?i)(?:github_pat_|gh[pousr]_|bearer\s|authorization\s*:|-----BEGIN .*PRIVATE KEY)')

class PolicyError(ValueError):
    pass

class SourceError(RuntimeError):
    pass

def require(condition, message):
    if not condition:
        raise PolicyError(message)

def clean(value, limit=500):
    require(isinstance(value, str) and len(value) <= limit, 'Invalid public text')
    require(not SECRET.search(value), 'Credential-shaped material rejected')
    require(all(ord(c) >= 32 or c in '\n\t' for c in value), 'Control character rejected')
    return value

def stamp(value):
    require(isinstance(value, str), 'Missing timestamp')
    return dt.datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=dt.timezone.utc)

def provenance(kind, url):
    return dict(sourceVisibility='public', sourceType=kind, sourceUrl=url)

def route(path):
    """No arbitrary URLs, query parameters, headers, redirects, or credentials."""
    roots = [f'/users/{USER}', f'/users/{USER}/repos?type=owner&per_page=100&page=[1-9][0-9]*',
             f'/users/{USER}/events/public?per_page=100&page=[1-3]']
    roots += [f'/repos/{USER}/{NAME}', f'/repos/{USER}/{NAME}/languages',
              f'/repos/{USER}/{NAME}/releases?per_page=100&page=[1-9][0-9]*']
    # Query marks are literals; all callers construct routes, never consume API URLs.
    require(any(re.fullmatch(p.replace('?', r'\?'), path) for p in roots), 'Endpoint outside public allowlist')
    require('..' not in path and '%' not in path, 'Ambiguous path')
    return path

class AnonymousGitHub:
    def __init__(self):
        self.calls = 0
        self.audit = []

    def get(self, path):
        route(path)
        self.calls += 1
        if self.calls > 50:
            raise SourceError('Anonymous request budget exhausted; previous artifacts remain unchanged')
        # http.client does not read netrc, proxy, Git, gh, cookie, or credential configuration.
        connection = http.client.HTTPSConnection('api.github.com', timeout=30,
                                                 context=ssl.create_default_context())
        try:
            connection.request('GET', path, headers={
                'Accept': 'application/vnd.github+json',
                'User-Agent': 'HarzerHeribert-public-control-plane/1.0',
                'X-GitHub-Api-Version': '2022-11-28',
            })
            response = connection.getresponse()
            body = response.read(4_000_001)
            if response.status in (403, 429):
                raise SourceError('Anonymous API rate limited; retry a later scheduled build')
            if response.status != 200:
                raise SourceError(f'Anonymous source unavailable: HTTP {response.status}; no fallback')
            if len(body) > 4_000_000:
                raise SourceError('Response exceeds public collector limit')
            result = json.loads(body)
            self.audit.append(dict(url=API + path, status=200,
                                   sha256=hashlib.sha256(body).hexdigest(), authentication='none'))
            return result
        except (OSError, json.JSONDecodeError) as error:
            raise SourceError('Anonymous API transport/JSON failure') from error
        finally:
            connection.close()

    def pages(self, base, maximum=10):
        result = []
        for page in range(1, maximum + 1):
            rows = self.get(f'{base}&page={page}')
            require(isinstance(rows, list), 'Expected a public collection')
            result.extend(rows)
            if len(rows) < 100:
                return result
        raise SourceError('Collection exceeds page limit; refusing incomplete totals')

def repository(raw):
    require(isinstance(raw, dict), 'Invalid repository')
    require(raw.get('private') is False and raw.get('visibility') == 'public', 'Repository is not explicitly public')
    name = clean(raw.get('name'), 100)
    require(re.fullmatch(NAME, name) and '..' not in name, 'Invalid repository name')
    require(raw.get('full_name') == f'{USER}/{name}', 'Foreign repository')
    url = WEB + '/' + name
    require(raw.get('html_url') == url, 'Unexpected repository link')
    topics = raw.get('topics', [])
    require(isinstance(topics, list) and all(isinstance(t, str) and re.fullmatch(r'[a-z0-9-]{1,50}', t) for t in topics), 'Malformed topics')
    language = raw.get('language')
    require(language is None or isinstance(language, str), 'Malformed primary language')
    if language is not None:
        clean(language, 80)
    pushed = raw.get('pushed_at')
    if pushed:
        stamp(pushed)
    return dict(name=name, description=clean(raw.get('description') or ''), topics=sorted(set(topics)),
                primaryLanguage=language, pushedAt=pushed, languages={},
                **provenance('repository', url))

def collect(client, now, revision):
    profile = client.get(f'/users/{USER}')
    require(profile.get('login') == USER and profile.get('html_url') == WEB, 'Unexpected profile')
    user = dict(login=USER, name=clean(profile.get('name') or USER, 100), **provenance('user', WEB))
    listed = client.pages(f'/users/{USER}/repos?type=owner&per_page=100')
    repos, releases = [], []
    for raw in listed:
        candidate = repository(raw)
        # Every included repository must independently resolve anonymously THIS build.
        repo = repository(client.get(f'/repos/{USER}/{candidate["name"]}'))
        require(repo['name'] == candidate['name'], 'Repository identity changed')
        languages = client.get(f'/repos/{USER}/{repo["name"]}/languages')
        require(isinstance(languages, dict), 'Malformed languages')
        for key, value in languages.items():
            clean(key, 80)
            require(type(value) is int and value > 0, 'Malformed language bytes')
        repo['languages'] = dict(sorted(languages.items()))
        repos.append(repo)
        for release in client.pages(f'/repos/{USER}/{repo["name"]}/releases?per_page=100'):
            require(release.get('draft') is False, 'Nonpublic release')
            require(type(release.get('id')) is int, 'Invalid release ID')
            stamp(release.get('published_at'))
            tag = clean(release.get('tag_name'), 200)
            url = release.get('html_url')
            require(isinstance(url, str) and url.startswith(repo['sourceUrl'] + '/releases/tag/'), 'Invalid release URL')
            releases.append(dict(id=str(release['id']), repo=repo['name'], tag=tag,
                                 at=release['published_at'], **provenance('release', url)))
    repo_names = {r['name'] for r in repos}
    events = []
    # GitHub's event stream is a bounded sample, never a complete activity ledger.
    for page in range(1, 4):
        rows = client.get(f'/users/{USER}/events/public?per_page=100&page={page}')
        require(isinstance(rows, list), 'Malformed events')
        for event in rows:
            require(event.get('public') is True, 'Nonpublic event')
            full_name = event.get('repo', {}).get('name', '')
            if not full_name.startswith(USER + '/') or full_name.split('/', 1)[1] not in repo_names:
                continue  # No foreign or no-longer-public repository enters the model.
            require(event.get('actor', {}).get('login') == USER, 'Unexpected actor')
            kind = event.get('type')
            kinds = {'PushEvent':'push', 'PullRequestEvent':'pull_request', 'IssuesEvent':'issue',
                     'ReleaseEvent':'release', 'WatchEvent':'star', 'CreateEvent':'create',
                     'DeleteEvent':'delete', 'ForkEvent':'fork', 'IssueCommentEvent':'comment',
                     'PullRequestReviewEvent':'review', 'PullRequestReviewCommentEvent':'review'}
            if kind not in kinds:
                continue
            stamp(event.get('created_at'))
            require(isinstance(event.get('id'), str) and event['id'].isdigit(), 'Invalid event ID')
            name = full_name.split('/', 1)[1]
            # Payload text, author emails, commit messages and bodies are deliberately not retained.
            events.append(dict(id=event['id'], repo=name, kind=kinds[kind], at=event['created_at'],
                               **provenance('event', WEB + '/' + name)))
        if len(rows) < 100:
            break
    model = dict(schema=1, renderer=VERSION, generated=now, revision=revision, user=user,
                 repositories=sorted(repos, key=lambda r:r['name'].lower()),
                 releases=sorted(releases, key=lambda r:r['id']),
                 events=sorted({e['id']:e for e in events}.values(), key=lambda e:(e['at'],e['id'])),
                 sources=client.audit)
    validate(model)
    return model

def validate(model):
    require(set(model) == {'schema','renderer','generated','revision','user','repositories','releases','events','sources'}, 'Unexpected model fields')
    require(model['schema'] == 1 and model['renderer'] == VERSION, 'Unsupported schema')
    stamp(model['generated'])
    require(re.fullmatch(r'[0-9a-f]{40}', model['revision']) is not None, 'Build requires a real Git revision')
    require(isinstance(model['sources'], list), 'Missing source audit')
    audited = set()
    for source in model['sources']:
        require(set(source) == {'url','status','sha256','authentication'}, 'Invalid source audit')
        require(source['url'].startswith(API), 'Foreign source')
        route(source['url'][len(API):])
        require(source['authentication'] == 'none' and source['status'] == 200, 'Unauthenticated source required')
        require(re.fullmatch('[0-9a-f]{64}', source['sha256']) is not None, 'Missing source digest')
        audited.add(source['url'])
    def entity(record, kind, fields, url):
        require(set(record) == set(fields) | {'sourceVisibility','sourceType','sourceUrl'}, 'Unexpected entity fields')
        require(record['sourceVisibility'] == 'public' and record['sourceType'] == kind, 'Public provenance required')
        require(record['sourceUrl'] == url, 'Unexpected entity URL')
    entity(model['user'], 'user', ['login','name'], WEB)
    require(model['user']['login'] == USER and API + f'/users/{USER}' in audited, 'Unverified user')
    clean(model['user']['name'],100)
    names = set()
    for repo in model['repositories']:
        name = repo.get('name', '')
        require(isinstance(name,str) and re.fullmatch(NAME,name) and '..' not in name, 'Invalid repository name')
        entity(repo, 'repository', ['name','description','topics','primaryLanguage','pushedAt','languages'], WEB+'/'+name)
        require(name not in names, 'Duplicate repository')
        names.add(name)
        require(API+f'/repos/{USER}/{name}' in audited and API+f'/repos/{USER}/{name}/languages' in audited, 'Repository lacks anonymous resolution')
        clean(repo['description'])
        require(isinstance(repo['topics'],list) and all(isinstance(t,str) and re.fullmatch('[a-z0-9-]{1,50}',t) for t in repo['topics']), 'Malformed topics')
        require(isinstance(repo['languages'],dict), 'Malformed languages')
        for language, size in repo['languages'].items():
            clean(language,80)
            require(type(size) is int and size > 0, 'Malformed language bytes')
        if repo['primaryLanguage'] is not None:
            clean(repo['primaryLanguage'],80)
        if repo['pushedAt']:
            stamp(repo['pushedAt'])
    for group, kind, fields in [('events','event',['id','repo','kind','at']), ('releases','release',['id','repo','tag','at'])]:
        ids=set()
        for record in model[group]:
            require(record.get('repo') in names, 'Unresolved repository in activity')
            require(isinstance(record.get('id'),str) and record['id'].isdigit() and record['id'] not in ids, 'Invalid/duplicate activity ID')
            ids.add(record['id'])
            url=WEB+'/'+record['repo']
            if kind == 'release':
                clean(record['tag'],200)
                url=record['sourceUrl']
                require(url.startswith(WEB+'/'+record['repo']+'/releases/tag/') and not re.search(r'[\s<>"\\]',url), 'Invalid release link')
                require(API+f'/repos/{USER}/{record["repo"]}/releases?per_page=100&page=1' in audited, 'Unverified release')
            else:
                require(record['kind'] in {'push','pull_request','issue','release','star','create','delete','fork','comment','review'}, 'Invalid event kind')
                require(API+f'/users/{USER}/events/public?per_page=100&page=1' in audited, 'Unverified event')
            entity(record,kind,fields,url)
            require(stamp(record['at']) <= stamp(model['generated']), 'Future activity')
    require(not SECRET.search(json.dumps(model)), 'Credential-shaped material rejected')
    return model
