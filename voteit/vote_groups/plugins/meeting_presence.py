from pyramid.threadlocal import get_current_request
from voteit.irl.models.elegible_voters_method import ElegibleVotersMethod
from voteit.irl.models.interfaces import IMeetingPresence

from voteit.vote_groups import _
from voteit.vote_groups.interfaces import IVoteGroups


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


def includeme(config):
    config.registry.registerAdapter(PresentWithVoteGroupsVoters, name=PresentWithVoteGroupsVoters.name)
