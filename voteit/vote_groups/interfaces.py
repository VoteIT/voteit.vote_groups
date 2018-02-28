# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from pyramid.interfaces import IDict
from zope.interface import Interface
from zope.interface import Attribute


class IVoteGroups(IDict):
    """ An adapter that handles meeting vote groups. Adapts a meeting.
        Implements a dict-like interface to handle VoteGroup objects.
    """

    def new():
        """ New meeting vote group. Returns id. """

    def get_standin_for(userid):
        """ Return delegation where userid is a member, or None if nothing can be found. """

    def get_members():
        """ Return set with all group members """

    def get_voters():
        """ Return set of users with current vote rights """

    def get_primaries(exclude_group):
        """ Return set with all primary voters, excluding exclude_group if present """

    def get_free_standins(group):
        """ Return set with free stand-ins for vote group """


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
        """ Return voters"""

    def get_primary_for(userid):
        """ Who made this userid a voter? """
