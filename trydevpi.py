from flask import Flask, render_template
from flask.ext.cache import Cache
from mercurial import ui, hg
from mercurial.hgweb.hgwebdir_mod import findrepos

BASE_URL = 'hg+https://hg.tryton.org/'
BASE_MODULE_URL = 'hg+https://hg.tryton.org/modules/'

app = Flask(__name__)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})
app.config.from_envvar('TRYDEVPI_SETTINGS', silent=True)


def get_urls(branch_filter=None):
    urls = {}
    lui = ui.ui()
    lui.readconfig(app.config['HG_CONFIG'], trust=True)
    paths = lui.configitems('paths')
    new_packages = []
    last_series = None
    for name, path in findrepos(paths):
        if (name not in ('trytond', 'proteus', 'tryton')
                and not name.startswith('modules/')):
            continue
        package = get_package(name)
        repo = hg.repository(lui, path)
        last_major = {}
        max_version = (-1, -1)
        for version in repo.tags():
            try:
                major, minor, bug = map(int, version.split('.'))
            except ValueError:
                continue
            key = (major, minor)
            if max_version < key:
                max_version = key
            if last_major.get(key, -1) < bug:
                last_major[key] = bug
        if max_version == (-1, -1):
            new_packages.append(package)
            continue
        last_major[max_version[0], max_version[1] + 1] = -1
        for (major, minor), bug in last_major.iteritems():
            bug += 1
            version = get_version(major, minor, bug)
            last_series = max(last_series, (major, minor, bug))
            branch = get_branch(major, minor)
            if (not repo.branchheads(branch)
                    or (branch_filter and branch != branch_filter)):
                continue
            url = get_url(package, branch, version)
            urls['%s-%s' % (package, version)] = url
    for package in new_packages:
        version = get_version(*last_series)
        branch = get_branch(*last_series[:2])
        url = get_url(package, branch, version)
        urls['%s-%s' % (package, version)] = url
    return urls


def get_package(name):
    if name in ('trytond', 'proteus', 'tryton'):
        return name
    else:
        return 'trytond_%s' % name[len('modules/'):]


def get_version(major, minor, bug):
    template = '%(major)s.%(minor)s.%(bug)s.dev0'
    if minor % 2:
        template = '%(major)s.%(minor)s.dev0'
    return template % {
        'major': major,
        'minor': minor,
        'bug': bug,
        }


def get_branch(major, minor):
    if minor % 2:
        return 'default'
    else:
        return '%s.%s' % (major, minor)


def get_url(name, branch, version):
    if name.startswith('trytond_'):
        url = BASE_MODULE_URL + name[len('trytond_'):]
    else:
        url = BASE_URL + name
    return '%(url)s@%(branch)s#egg=%(name)s-%(version)s' % {
        'url': url,
        'name': name,
        'branch': branch,
        'version': version,
        }


@app.route('/')
@app.route('/<branch>')
@cache.cached(timeout=2 * 60 * 60)
def index(branch=None):
    return render_template('index.html', urls=get_urls(branch))


if __name__ == '__main__':
    app.run(debug=True)
