# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from pyramid.decorator import reify
from pyramid.httpexceptions import HTTPNotFound
from pyramid.httpexceptions import HTTPForbidden

from voteit.vote_groups.interfaces import IVoteGroups
from voteit.vote_groups import _


class VoteGroupMixin(object):

    @reify
    def vote_groups(self):
        return self.request.registry.getMultiAdapter((self.request.meeting, self.request), IVoteGroups)

    def _block_during_ongoing_poll(self):
        if self.vote_groups.ongoing_poll:
            raise HTTPForbidden(_("access_during_ongoing_not_allowed",
                                  default="During ongoing polls, this action isn't allowed. "
                                          "Try again when polls have closed."))


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
