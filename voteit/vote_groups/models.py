# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from persistent import Persistent
from uuid import uuid4

from BTrees.OOBTree import OOBTree
from BTrees.OOBTree import OOSet
from pyramid.threadlocal import get_current_request
from voteit.core.models.interfaces import IMeeting
from voteit.irl.models.elegible_voters_method import ElegibleVotersMethod
from voteit.irl.models.interfaces import IMeetingPresence
from zope.component import adapter
from zope.interface import implementer

from voteit.vote_groups import _
from voteit.vote_groups.interfaces import IVoteGroup
from voteit.vote_groups.interfaces import IVoteGroups


#FIXME: Use IterableUserDict from standardlib + import IDict for ifaces
@implementer(IVoteGroups)
@adapter(IMeeting)
class VoteGroups(object):
    """ See .interfaces.IVoteGroups """

    def __init__(self, context):
        self.context = context
        if not hasattr(self.context, '__vote_groups__'):
            self.context.__vote_groups__ = OOBTree()

    def new(self):
        name = unicode(uuid4())
        self.context.__vote_groups__[name] = MeetingVoteGroup(name)
        return name

    def get_standin_for(self, userid):
        for delegation in self.values():
            if userid in delegation.members:
                return delegation

    def get(self, name, default = None):
        return self.context.__vote_groups__.get(name, default)

    def __getitem__(self, name):
        return self.context.__vote_groups__[name]

    def __delitem__(self, name):
        del self.context.__vote_groups__[name]

    def __len__(self):
        return len(self.context.__vote_groups__)

    def keys(self):
        return self.context.__vote_groups__.keys()

    def __iter__(self):
        return iter(self.keys())

    def values(self):
        return self.context.__vote_groups__.values()

    def items(self):
        return self.context.__vote_groups__.items()

    def __nonzero__(self):
        """ This object should be "true" even if it has no content. """
        return True


@implementer(IVoteGroup)
class VoteGroup(Persistent):
    title = ""
    description = ""

    def __init__(self, name, title="", description="", members=(), assignments=None):
        self.name = name
        self.title = title
        self.description = description
        self.members = OOSet(members)
        self.assignments = OOBTree(assignments or {})

    @property
    def free_standins(self):
        return set(self.standins).difference(self.assignments.values())

    def get_users_with_role(self, role):
        return [m['user'] for m in self.members if m['role'] == role]

    @property
    def primaries(self):
        return self.get_users_with_role('primary')

    @property
    def standins(self):
        return self.get_users_with_role('standin')

    @property
    def observers(self):
        return self.get_users_with_role('observer')


class PresentWithVoteGroupsVoters(ElegibleVotersMethod):
    name = 'present_with_vote_groups'
    title = _("Present with group voter rights.")
    description = _("present_with_vote_groups_description",
                    default="Will set voter rights for present user according to vote groups settings.")

    def get_voters(self, request=None, **kw):
        if request is None:
            request = get_current_request()
        meeting_presence = request.registry.getAdapter(self.context, IMeetingPresence)
        groups = IVoteGroups(self.context)
        group_voter_rights = set()
        for grp in groups.values():
            group_voter_rights.update(list(grp.assignments.values()) +
                                      filter(lambda uid: uid not in grp.assignments, grp.primaries))
        return frozenset(group_voter_rights.intersection(meeting_presence.present_userids))


def includeme(config):
    config.registry.registerAdapter(VoteGroups)
    config.registry.registerAdapter(PresentWithVoteGroupsVoters, name=PresentWithVoteGroupsVoters.name)
