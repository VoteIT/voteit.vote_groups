# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from UserDict import IterableUserDict
from persistent import Persistent
from uuid import uuid4

from arche.interfaces import IEmailValidatedEvent
from arche.interfaces import IUser
from BTrees.OOBTree import OOBTree
from BTrees.OOBTree import OOSet
from pyramid.decorator import reify
from pyramid.interfaces import IRequest
from pyramid.threadlocal import get_current_request
from pyramid.traversal import find_interface
from pyramid.traversal import find_root
from repoze.catalog.query import Any, Eq
from six import string_types
from typing import Iterable

from voteit.core.models.interfaces import IMeeting
from zope.component import adapter
from zope.copy import copy
from zope.interface import implementer

from voteit.vote_groups.events import AssignmentChanged
from voteit.vote_groups.exceptions import GroupPermissionsException
from voteit.vote_groups.interfaces import IAssignmentChanged
from voteit.vote_groups.interfaces import IVoteGroup
from voteit.vote_groups.interfaces import IVoteGroups
from voteit.vote_groups.interfaces import ROLE_PRIMARY
from voteit.vote_groups.interfaces import ROLE_STANDIN
from voteit.vote_groups.interfaces import VOTE_GROUP_ROLES


@implementer(IVoteGroups)
@adapter(IMeeting, IRequest)
class VoteGroups(object, IterableUserDict):
    """ See .interfaces.IVoteGroups """

    def __init__(self, context, request):
        self.context = context
        self.request = request

    # @property
    # def ongoing_poll(self):
    #     # type: () -> bool
    #     _poll_query = Eq('type_name', 'Poll') & Eq('workflow_state', 'ongoing')
    #     query = _poll_query & Eq('path', resource_path(self.context))
    #     if self.request.root is not None:  # pragma: no cover
    #         return self.request.root.catalog.query(query)[0].total > 0
    #     return False

    @reify
    def data(self):
        try:
            return self.context._vote_groups
        except AttributeError:
            self.context._vote_groups = OOBTree()
            return self.context._vote_groups

    @property
    def settings(self):
        return dict(getattr(self.context, '_vote_groups_settings', {}))
    @settings.setter
    def settings(self, value):
        if value != self.settings:
            self.context._vote_groups_settings = OOBTree(value)

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
            if group.name not in group_names:  # pragma: no cover
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
                if validated and not user.email_validated:  # pragma: no cover
                    continue
                emails.add(user.email)
        return emails

    def get_voters(self):
        voter_rights = set()
        for grp in self.values():
            voter_rights.update(grp.get_voters())
        return voter_rights

    @property
    def voters(self):
        # try:
        #     return self._voters
        # except AttributeError:
        #     self._voters = self.get_voters()
        #     return self._voters
        return self.get_voters()
        # TODO Cache this, but drop on any changes, even in individual groups.

    def get_primaries(self, exclude_group=None):
        # type: (IVoteGroup) -> set[string_types]
        all_primaries = set()
        for group in filter(lambda g: g != exclude_group, self.values()):
            all_primaries.update(group.primaries)
        return all_primaries

    def sorted(self):
        # type: () -> Iterable[IVoteGroup]
        return sorted(self.values(), key=lambda g: g.title.lower())

    def vote_groups_for_user(self, userid):
        # type: (string_types) -> Iterable[IVoteGroup]
        return filter(lambda g: userid in g, self.sorted())

    def get_free_standins(self, group):
        # type: (IVoteGroup) -> set[string_types]
        return set(group.standins).difference(self.voters)

    def __setitem__(self, key, vg):
        assert IVoteGroup.providedBy(vg)
        # To make traversal work
        vg.__parent__ = self.context
        self.data[key] = vg

    def __bool__(self):
        # type: () -> bool
        """ This object should be "true" even if it has no content. """
        return True
    __nonzero__ = __bool__

    def email_validated(self, user):
        # type: (IUser) -> None
        assert IUser.providedBy(user)
        if user.email:
            for group in self.values():
                if user.email in group.potential_members:
                    group.potential_members.remove(user.email)
                    group[user.userid] = ROLE_STANDIN

    def copy_from_meeting(self, meeting):
        # type: (IMeeting) -> int
        """ Transfer all groups from another meeting, if they don't already exist.
        """
        new_vote_groups = self.request.registry.getMultiAdapter((meeting, self.request), IVoteGroups)
        counter = 0
        for (name, vote_group) in new_vote_groups.items():
            if name not in self:
                self[name] = copy(vote_group)
                # Clear all assignments
                self[name].assignments.clear()
                counter += 1
        return counter

    def can_substitute(self, userid, group):
        # type: (string_types, VoteGroup) -> bool
        return userid in self.get_free_standins(group)

    def can_assign(self, userid, group):
        # type: (string_types, IVoteGroup) -> bool
        return bool(userid in group.primaries and
                    userid not in group.assignments and
                    self.get_free_standins(group))

    def can_set_role(self, userid, role, group):
        # type: (string_types, IVoteGroup) -> bool
        assert role in dict(VOTE_GROUP_ROLES), 'Role does not exist'
        if role == ROLE_PRIMARY and userid in self.get_primaries(exclude_group=group):
            return False
        return userid in group

    def get_assign_permission(self, userid, group):
        # type: (string_types, VoteGroup) -> bool
        if self.request.is_moderator or self.request.authenticated_userid == userid:
            return bool(group.get(userid) == ROLE_PRIMARY or group.get_primary_for(userid))
        return False

    def assign_vote(self, from_userid, to_userid, group, event=True):
        if not self.can_assign(from_userid, group) or not self.can_substitute(to_userid, group):
            raise GroupPermissionsException('Cannot assign vote')
        group.assignments[from_userid] = to_userid
        if event:
            self.notify_changed(group)

    def release_substitute(self, voter, group, event=True):
        if not self.get_assign_permission(voter, group):
            raise GroupPermissionsException('Cannot assign vote')
        primary = group.get_primary_for(voter)
        del group.assignments[primary]
        if event:
            self.notify_changed(group)

    def set_role(self, userid, role, group, event=True):
        # type: (string_types, string_types, IVoteGroup, bool) -> None
        if not self.can_set_role(userid, role, group):
            raise GroupPermissionsException('Cannot set role')
        group[userid] = role
        if event:
            self.notify_changed(group)

    def update_from_appstruct(self, appstruct, group):
        # type: (dict, VoteGroup) -> None
        group.update_from_appstruct(appstruct, self.request)
        self.notify_changed(group)

    def notify_changed(self, group):
        event = AssignmentChanged(group, self.request)
        self.request.registry.notify(event)

    def __repr__(self):
        klass = self.__class__
        classname = '%s.%s' % (klass.__module__, klass.__name__)
        return '<%s adapter at %#x>' % (classname, id(self))


@implementer(IVoteGroup)
class VoteGroup(Persistent, IterableUserDict):
    title = ""
    description = ""
    __parent__ = None

    def __init__(self, name, title="", description=""):
        self.name = name
        self.title = title
        self.description = description
        # Use userid as key and role as value, or none
        self.data = OOBTree()
        # Assigned
        self.assignments = OOBTree()
        # Potential members - simply list emails
        self.potential_members = OOSet()

    def get_roles(self, role):
        for (k, v) in self.items():
            if v == role:
                yield k

    @property
    def primaries(self):
        return self.get_roles(ROLE_PRIMARY)

    @property
    def standins(self):
        return self.get_roles(ROLE_STANDIN)

    def get_voters(self):
        """
        :return: Set of userids who are potential voters for this group.
        """
        return set(
            list(self.assignments.values()) +
            filter(lambda userid: userid not in self.assignments, self.primaries)
        )

    def get_primary_for(self, userid):
        # type: (string_types) -> string_types
        assert isinstance(userid, string_types)
        for k, v in self.assignments.items():
            if v == userid:
                return k

    def get_substitute_for(self, userid):
        # type: (string_types) -> string_types
        assert isinstance(userid, string_types)
        return self.assignments.get(userid)

    def appstruct(self):
        # type: () -> dict
        return dict(title=self.title,
                    description=self.description,
                    members=list(self.keys()),
                    potential_members="\n".join(self.potential_members))

    def update_from_appstruct(self, appstruct, request):
        # type: (dict, IRequest) -> None
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
            self[userid] = ROLE_STANDIN
        if set(self.potential_members) != potential_members:
            self.potential_members.clear()
            self.potential_members.update(potential_members)


def apply_adjust_meeting_roles(meeting, group=None, request=None):
    # type: (IMeeting, IVoteGroup, IRequest) -> None
    """
    Adjust meeting roles according to settings, if there are any settings for this meeting.

    :param meeting: Meeting object
    :param group: Only check members of this group
    :param request: Current request
    """
    assert IMeeting.providedBy(meeting)
    if request is None:
        request = get_current_request()
    vote_groups = request.registry.queryMultiAdapter((meeting, request), IVoteGroups)
    if vote_groups is None:  # pragma: no cover
        return
    assigned_voter_roles = vote_groups.settings.get('assigned_voter_roles', None)
    if not assigned_voter_roles:  # pragma: no cover
        # System is inactive
        return
    inactive_voter_roles = vote_groups.settings.get('inactive_voter_roles', set())
    remove_on_inactive = assigned_voter_roles.difference(inactive_voter_roles)
    if group:
        # Only for a specific group
        assigned_voter_members = group.get_voters()
        members = set(group.keys())
    else:  # pragma: no cover
        # Check all
        assigned_voter_members = vote_groups.get_voters()
        members = vote_groups.get_members()
    inactive_voters_members = members.difference(assigned_voter_members)
    roles = meeting.local_roles
    for userid in assigned_voter_members:
        roles.add(userid, assigned_voter_roles, event=False)
    for userid in inactive_voters_members:
        roles.remove(userid, remove_on_inactive, event=False)
    roles.send_event()


def user_validated_email_subscriber(event):
    """ Check for potential memberships.
        This may be slow with a lot of ongoing meetings at the same time.
    """
    request = get_current_request()
    user = event.user
    query = Eq('type_name', 'Meeting') & Any('workflow_state', ['ongoing', 'upcoming'])
    docids = request.root.catalog.query(query)[1]
    for meeting in request.resolve_docids(docids, perm=None):
        vote_groups = request.registry.queryMultiAdapter((meeting, request), IVoteGroups)
        if vote_groups is not None:
            vote_groups.email_validated(user)


def adjust_roles_after_assignment(event):
    meeting = find_interface(event.group, IMeeting)
    apply_adjust_meeting_roles(meeting, event.group)


def includeme(config):
    config.registry.registerAdapter(VoteGroups)
    config.add_subscriber(user_validated_email_subscriber, IEmailValidatedEvent)
    config.add_subscriber(adjust_roles_after_assignment, IAssignmentChanged)
    try:
        from voteit.irl.models.elegible_voters_method import ElegibleVotersMethod
        has_irl = True
    except ImportError:  # pragma: no cover
        has_irl = True
    if has_irl:
        config.include('voteit.vote_groups.plugins.meeting_presence')
