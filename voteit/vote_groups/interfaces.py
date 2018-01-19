# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from zope.interface import Interface
from zope.interface import Attribute


class IVoteGroups(Interface):
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


class IVoteGroup(Interface):
    """ A meeting delegation. Handled by IVoteGroups adapter.
    """
    name = Attribute("Name of the interface. Used to fetch this object from the IVoteGroups adapter.")
    title = Attribute("Title of delegation")
    primaries = Attribute("Primaries who are allowed to delegate or take back votes.")
    standins = Attribute("Stand-ins. You need to be a registered stand-in to be able to receive voting rights.")
    assignments = Attribute("Votes assigned from a primary voter to a standin.")

    def __init__(name, title = u"", primaries = (), standins = ()):
        """ Constructor, normally not passed any values within this app. """
