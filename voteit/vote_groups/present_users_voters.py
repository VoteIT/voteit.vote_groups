# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from pyramid.threadlocal import get_current_request

from voteit.irl.models.elegible_voters_method import ElegibleVotersMethod
from voteit.irl.models.interfaces import IMeetingPresence

from voteit.vote_groups.interfaces import IMeetingVoteGroups
from voteit.vote_groups import _


class MakePresentUsersVoters(ElegibleVotersMethod):
    name = 'present_with_vote_groups'
    title = _("Present with group voter rights.")
    description = _("present_with_vote_groups_description",
                    default="Will set voter rights for present user according to vote groups settings.")

    def get_voters(self, request=None, **kw):
        if request is None:
            request = get_current_request()
        meeting_presence = request.registry.getAdapter(self.context, IMeetingPresence)
        groups = IMeetingVoteGroups(request.meeting)
        group_voter_rights = set()
        for grp in groups.values():
            group_voter_rights.update(list(grp.assignments.values()) +
                                      filter(lambda uid: uid not in grp.assignments, grp.primaries))
        return frozenset(group_voter_rights.intersection(meeting_presence.present_userids))


def includeme(config):
    config.registry.registerAdapter(MakePresentUsersVoters, name=MakePresentUsersVoters.name)
