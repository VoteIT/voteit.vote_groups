# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from UserDict import IterableUserDict
from persistent import Persistent
from uuid import uuid4

from BTrees.OOBTree import OOBTree
from BTrees.OOBTree import OOSet
from arche.interfaces import IEmailValidatedEvent
from arche.interfaces import IUser
from pyramid.decorator import reify
from pyramid.threadlocal import get_current_request
from pyramid.traversal import find_root
from repoze.catalog.query import Any, Eq
from six import string_types
from voteit.core.models.interfaces import IMeeting
from zope.copy import copy
from zope.component import adapter
from zope.interface import implementer

from voteit.vote_groups import _
from voteit.vote_groups.interfaces import IVoteGroup
from voteit.vote_groups.interfaces import IVoteGroups
from voteit.vote_groups.interfaces import VOTE_GROUP_ROLES


@implementer(IVoteGroups)
@adapter(IMeeting)
class VoteGroups(IterableUserDict):
    """ See .interfaces.IVoteGroups """

    def __init__(self, context):
        self.context = context

    @reify
    def data(self):
        try:
            return self.context._vote_groups
        except AttributeError:
            self.context._vote_groups = OOBTree()
            return self.context._vote_groups

    def new(self):
        name = unicode(uuid4())
        self[name] = VoteGroup(name)
        return name

    def get_standin_for(self, userid):
        for group in self.values():
            if userid in group.assignments:
                return group.assignments[userid]

    def get_primary_for(self, userid):
        """ Get the userid and group for who 'userid' replaces. """
        for group in self.values():
            primary_for = group.get_primary_for(userid)
            if primary_for:
                return primary_for, group
        return None, None

    def get_voting_group_for(self, userid):
        for group in self.values():
            if userid in group.get_voters():
                return group

    def get_members(self):
        members = set()
        for group in self.values():
            members.update(group.keys())
        return members

    def get_emails(self, group_names=None, potential=True, validated=True):
        if group_names is None:
            group_names = self.keys()
        root = find_root(self.context)
        emails = set()
        userids = set()
        for group in self.values():
            if group.name not in group_names:
                continue
            if potential:
                emails.update(group.potential_members)
                userids.update(group.keys())
        for userid in userids:
            try:
                user = root['users'][userid]
            except KeyError:
                continue
            if user.email:
                if validated and not user.email_validated:
                    continue
                emails.add(user.email)
        return emails

    def get_voters(self):
        voter_rights = set()
        for grp in self.values():
            voter_rights.update(grp.get_voters())
        return voter_rights

    def get_primaries(self, exclude_group=None):
        all_primaries = set()
        for group in filter(lambda g: g != exclude_group, self.values()):
            all_primaries.update(group.primaries)
        return all_primaries

    def sorted(self):
        return sorted(self.values(), key=lambda g: g.title.lower())

    def vote_groups_for_user(self, userid):
        return filter(lambda g: userid in g, self.sorted())

    def get_free_standins(self, group):
        return set(group.standins).difference(self.get_voters())

    def __setitem__(self, key, vg):
        assert IVoteGroup.providedBy(vg)
        # To make traversal work
        vg.__parent__ = self.context
        self.data[key] = vg

    def __nonzero__(self):
        """ This object should be "true" even if it has no content. """
        return True

    def email_validated(self, user):
        assert IUser.providedBy(user)
        if user.email:
            for group in self.values():
                if user.email in group.potential_members:
                    group.potential_members.remove(user.email)
                    group[user.userid] = 'standin'

    def copy_from_meeting(self, meeting):
        """ Transfer all groups from another meeting, if they don't already exist.
        """
        new_vote_groups = IVoteGroups(meeting)
        counter = 0
        for (name, vote_group) in new_vote_groups.items():
            if name not in self:
                self[name] = copy(vote_group)
                #Clear all asignments
                self[name].assignments.clear()
                counter += 1
        return counter


@implementer(IVoteGroup)
class VoteGroup(Persistent, IterableUserDict):
    title = ""
    description = ""
    __parent__ = None

    def __init__(self, name, title="", description=""):
        self.name = name
        self.title = title
        self.description = description
        #FIXME: Structure
        #Use userid as key and role as value, or none
        self.data = OOBTree()
        #Assigned
        self.assignments = OOBTree()
        #Potential members - simply list emails
        self.potential_members = OOSet()

    def get_roles(self, role):
        for (k, v) in self.items():
            if v == role:
                yield k

    @property
    def primaries(self):
        return self.get_roles('primary')

    @property
    def standins(self):
        return self.get_roles('standin')

    def get_voters(self):
        """
        :return: Set of userids who are potential voters for this group.
        """
        return set(
            list(self.assignments.values()) +
            filter(lambda userid: userid not in self.assignments, self.primaries)
        )

    def get_primary_for(self, userid):
        assert isinstance(userid, string_types)
        for k, v in self.assignments.items():
            if v == userid:
                return k

    def appstruct(self):
        return dict(title=self.title,
                    description=self.description,
                    members=list(self.keys()),
                    potential_members="\n".join(self.potential_members))

    def update_from_appstruct(self, appstruct, request):
        self.title = appstruct['title']
        self.description = appstruct['description']
        previous = set(self.keys())
        incoming = set(appstruct['members'])
        # Find all potential members already registered
        potential_members = set()
        found = 0
        for email in appstruct['potential_members'].splitlines():
            user = request.root['users'].get_user_by_email(email, only_validated=True)
            if user:
                incoming.add(user.userid)
                found += 1
            else:
                potential_members.add(email)
        for userid in previous.difference(incoming):
            del self[userid]
        for userid in incoming.difference(previous):
            self[userid] = 'standin'
        if set(self.potential_members) != potential_members:
            self.potential_members.clear()
            self.potential_members.update(potential_members)


def user_validated_email_subscriber(event):
    """ Check for potential memberships.
        This may be slow with a lot of ongoing meetings at the same time.
    """
    request = get_current_request()
    user = event.user
    query = Eq('type_name', 'Meeting') & Any('workflow_state', ['ongoing', 'upcoming'])
    docids = request.root.catalog.query(query)[1]
    for meeting in request.resolve_docids(docids, perm=None):
        vote_groups = IVoteGroups(meeting, None)
        vote_groups.email_validated(user)


def includeme(config):
    config.registry.registerAdapter(VoteGroups)
    config.add_subscriber(user_validated_email_subscriber, IEmailValidatedEvent)
    try:
        from voteit.irl.models.elegible_voters_method import ElegibleVotersMethod
        has_irl = True
    except ImportError:
        has_irl = True
    if has_irl:
        config.include('voteit.vote_groups.plugins.meeting_presence')
