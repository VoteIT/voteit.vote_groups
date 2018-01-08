# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from arche.fanstatic_lib import common_js
from arche.interfaces import IBaseView
from arche.interfaces import IViewInitializedEvent
from fanstatic import Library
from fanstatic import Resource
from voteit.core.fanstaticlib import voteit_main_css

vote_groups_lib = Library('vote_groups_lib', 'static')

# sfs_styles = Resource(sfs_ga_lib, 'styles.css', depends = (voteit_main_css,))
# sfs_manage_delegation = Resource(sfs_ga_lib, 'manage_delegation.js', depends = (common_js,))
#
#
# def need_sfs(view, event):
#     """ Load generic sfs resources
#     """
#     if view.request.meeting:
#         sfs_styles.need()

def includeme(config):
    # config.add_subscriber(need_sfs, [IBaseView, IViewInitializedEvent])
    pass
