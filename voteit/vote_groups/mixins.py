# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from pyramid.decorator import reify
from pyramid.httpexceptions import HTTPNotFound

from voteit.vote_groups.interfaces import IVoteGroups


class VoteGroupEditMixin(object):
    @reify
    def vote_groups(self):
        return self.request.registry.getAdapter(self.request.meeting, IVoteGroups)

    @reify
    def group_name(self):
        try:
            return self.request.GET.get('vote_group')
        except KeyError:
            raise HTTPNotFound()

    @reify
    def group(self):
        return self.vote_groups[self.group_name]
