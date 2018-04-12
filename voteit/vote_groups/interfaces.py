# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from pyramid.interfaces import IDict
from zope.interface import Interface
from zope.interface import Attribute

from voteit.vote_groups import _


ROLE_PRIMARY = 'primary'
ROLE_STANDIN = 'standin'
# None is also valid, but only in case user was removed from the group
VOTE_GROUP_ROLES = (
    (ROLE_PRIMARY, _('Primary')),
    (ROLE_STANDIN, _('Stand-in')),
)


class IVoteGroups(IDict):
    """ An adapter that handles meeting vote groups. Adapts a meeting.
        Implements a dict-like interface to handle VoteGroup objects.
    """

    def new():
        """ New meeting vote group. Returns id. """

    def get_standin_for(userid):
        """ Return delegation where userid has a substitute, or None if nothing can be found. """

    def get_primary_for(userid):
        """ Return primary and group where userid is a substitute, or None if nothing can be found. """

    def get_voting_group_for(userid):
        """ Return group where userid has vote rights, or None if nothing can be found. """

    def get_members():
        """ Return set with all group members """

    def get_voters():
        """ Return set of users with current vote rights according to groups """

    def get_primaries(exclude_group):
        """ Return set with all primary voters, excluding exclude_group if present """

    def get_free_standins(group):
        """ Return set with free stand-ins for vote group """

    def copy_from_meeting(meeting):
        """ Transfer all groups from another meeting, if they don't already exist. """

    def can_substitute(userid, group):
        """ Check if user is available as substitute in group """

    def can_assign(userid, group):
        """ Check if user can assign it's vote in group """

    def can_set_role(userid, role, group):
        """ Check if user can have a certains role """

    def assign_vote(from_userid, to_userid, group):
        """ Assign vote from/to user in group. Fire event when assigned. """

    def set_role(userid, role, group, request=None):
        """ Set role for user in group. Fire event when role is set. """


class IVoteGroup(IDict):
    """ A meeting delegation. Handled by IVoteGroups adapter.
    """
    name = Attribute("Name of the interface. Used to fetch this object from the IVoteGroups adapter.")
    title = Attribute("Title of delegation.")
    description = Attribute("Description")
    assignments = Attribute("Votes assigned from a primary voter to a standin.")
    potential_members = Attribute("Persistent set of email addresses.")
    primaries = Attribute("Primary representatives")
    standins = Attribute("Standins, iterator")

    def __init__(name, title="", description=""):
        """ Constructor, normally not passed any values within this app. """

    def get_roles(role):
        """ Return userids with role"""

    def get_voters():
        """ Return set of users with current vote rights according to group """

    def get_primary_for(userid):
        """ Who made this userid a voter? """


class IAssignmentChanged(Interface):
    group = Attribute("Vote group with chenges")
