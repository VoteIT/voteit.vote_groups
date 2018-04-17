# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from zope.interface import implementer

from voteit.vote_groups.interfaces import IAssignmentChanged


@implementer(IAssignmentChanged)
class AssignmentChanged(object):
    """ Event fires when a user was assigned as active, got a new role, added etc."""

    def __init__(self, group, request):
        self.group = group
        self.request = request
