
from fanstatic import Library
from fanstatic import Resource
from js.jquery import jquery


vote_groups_lib = Library('vote_groups_lib', 'static')

vote_groups_css = Resource(vote_groups_lib, 'css/vote_groups.css')
vote_groups_js = Resource(vote_groups_lib, 'scripts/vote_groups.js', depends=(vote_groups_css, jquery))


def includeme(config):
    pass
