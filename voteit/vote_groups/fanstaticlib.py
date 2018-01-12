# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from arche.fanstatic_lib import common_js
from arche.interfaces import IBaseView
from arche.interfaces import IViewInitializedEvent
from fanstatic import Library
from fanstatic import Resource
from voteit.core.fanstaticlib import voteit_main_css


vote_groups_lib = Library('vote_groups_lib', 'static')


def includeme(config):
    pass
