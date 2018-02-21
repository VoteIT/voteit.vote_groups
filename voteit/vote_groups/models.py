# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from UserDict import IterableUserDict
from persistent import Persistent
from uuid import uuid4

from BTrees.OOBTree import OOBTree
from BTrees.OOBTree import OOSet
from arche.interfaces import IEmailValidatedEvent
from pyramid.decorator import reify
from pyramid.threadlocal import get_current_request
from pyramid.traversal import find_root
from repoze.catalog.query import Any, Eq
from six import string_types
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

    def get_members(self):
        members = set()
        for group in self.values():
            members.update(group.keys())
        return members

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

    def __setitem__(self, key, value):
        assert IVoteGroup.providedBy(value)
        self.data[key] = value

    def __nonzero__(self):
        """ This object should be "true" even if it has no content. """
        return True

    def email_validated(self, user):
        if user.email:
            for group in self.values():
                if user.email in group.potential_members:
                    group.potential_members.remove(user.email)
                    group[user.userid] = 'observer'


@implementer(IVoteGroup)
class VoteGroup(Persistent, IterableUserDict):
    title = ""
    description = ""

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

    @property
    def observers(self):
        return self.get_roles('observer')

    def get_voters(self):
        return set(
            list(self.assignments.values()) +
            filter(lambda uid: uid not in self.assignments, self.primaries)
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
            self[userid] = 'observer'
        if set(self.potential_members) != potential_members:
            self.potential_members.clear()
            self.potential_members.update(potential_members)


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
        return frozenset(groups.get_voters().intersection(meeting_presence.present_userids))


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
        vote_groups.email_validated(user.email)


def includeme(config):  # pragma: no cover
    config.registry.registerAdapter(VoteGroups)
    config.registry.registerAdapter(PresentWithVoteGroupsVoters, name=PresentWithVoteGroupsVoters.name)
    config.add_subscriber(user_validated_email_subscriber, IEmailValidatedEvent)
