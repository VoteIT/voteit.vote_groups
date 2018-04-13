# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from pyramid.decorator import reify
from pyramid.httpexceptions import HTTPNotFound

from voteit.vote_groups.interfaces import IVoteGroups


class VoteGroupMixin(object):

    @reify
    def vote_groups(self):
        return self.request.registry.getMultiAdapter((self.request.meeting, self.request), IVoteGroups)


class VoteGroupEditMixin(VoteGroupMixin):

    @reify
    def group_name(self):
        try:
            return self.request.GET['vote_group']
        except KeyError:
            raise HTTPNotFound()

    @reify
    def group(self):
        try:
            return self.vote_groups[self.group_name]
        except KeyError:
            raise HTTPNotFound()
