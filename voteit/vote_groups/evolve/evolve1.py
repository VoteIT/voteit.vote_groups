from voteit.core.models.interfaces import IMeeting
from voteit.vote_groups.interfaces import IVoteGroup


def evolve(root):
    """ Make sure traversal works on vote groups """
    for meeting in root.values():
        if not IMeeting.providedBy(meeting):
            continue
        for obj in getattr(meeting, '_vote_groups', {}).values():
            if IVoteGroup.providedBy(obj) and getattr(obj, '__parent__', None) is None:
                obj.__parent__ = meeting
