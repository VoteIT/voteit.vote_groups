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
        self.context.__vote_groups__[name] = VoteGroup(name)
        return name

    def get_standin_for(self, userid):
        for delegation in self.values():
            if userid in delegation.members:
                return delegation

    def get_members(self):
        members = set()
        for grp in self.values():
            members.update([m['user'] for m in grp.members])
        return members

    def get_voters(self):
        voter_rights = set()
        for grp in self.values():
            voter_rights.update(list(grp.assignments.values()))
            voter_rights.update(filter(lambda uid: uid not in grp.assignments, grp.primaries))
        return voter_rights

    def get_primaries(self, exclude_group=None):
        all_primaries = set()
        for group in filter(lambda g: g != exclude_group, self.values()):
            all_primaries.update(group.primaries)
        return all_primaries

    def get_free_standins(self, group):
        return set(group.standins).difference(self.get_voters())

    def get(self, name, default=None):
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
        return frozenset(groups.get_members().intersection(meeting_presence.present_userids))


def includeme(config):
    config.registry.registerAdapter(VoteGroups)
    config.registry.registerAdapter(PresentWithVoteGroupsVoters, name=PresentWithVoteGroupsVoters.name)
