# -*- coding: utf-8 -*-
from __future__ import unicode_literals


from zope.interface import implementer

from voteit.vote_groups import interfaces


@implementer(interfaces.IAssignmentChanged)
class AssignmentChanged(object):
    def __init__(self, group):
        self.group = group
