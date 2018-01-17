# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from arche.views.base import BaseView
from arche.views.base import DefaultDeleteForm
from arche.views.base import DefaultEditForm
from pyramid.decorator import reify
from pyramid.httpexceptions import HTTPForbidden
from pyramid.httpexceptions import HTTPFound
from pyramid.traversal import resource_path
from pyramid.view import view_config
from voteit.core import security
from voteit.core.models.interfaces import IMeeting

from voteit.vote_groups import _
from voteit.vote_groups.interfaces import IVoteGroups
from voteit.vote_groups.schemas import AssignVoteSchema


def _check_ongoing_poll(view):
    """ Check if a poll is ongoing, return number of ongoing polls """
    meeting_path = resource_path(view.request.meeting)
    ongoing = view.catalog_search(type_name='Poll',
                                  path=meeting_path,
                                  workflow_state='ongoing')
    if ongoing:
        raise HTTPForbidden(_("access_during_ongoing_not_allowed",
                            default="During ongoing polls, this action isn't allowed. "
                            "Try again when polls have closed."))


class MeetingVoteGroupsView(BaseView):

    @reify
    def meeting_vote_groups(self):
        return self.request.registry.getAdapter(self.request.meeting, IVoteGroups)

    @view_config(name="vote_groups", context=IMeeting, renderer="templates/meeting_vote_groups.pt")
    def delegations_view(self):
        show_all = self.request.GET.get('show_all', False)
        standins = sorted(self.meeting_vote_groups.values(), key=lambda x: x.title.lower())
        my_standin = None
        # if not self.request.is_moderator:
        #     for standin in standins:
        #         pool = set(standin.leaders) | set(delegation.members)
        #         if self.request.authenticated_userid in pool:
        #             my_delegations.append(delegation)
        response = {}
        response['all_count'] = len(self.meeting_vote_groups)
        response['my_standin'] = my_standin
        response['show_all'] = show_all
        if show_all or self.request.is_moderator:
            response['vote_groups'] = standins
        else:
            response['vote_groups'] = my_standin
        return response

    @view_config(name="add_vote_group", context=IMeeting, permission=security.MODERATE_MEETING)
    def add_vote_group(self):
        """ Add a new delegation and redirect to edit view.
        """
        _check_ongoing_poll(self)
        name = self.meeting_vote_groups.new()
        url = self.request.resource_url(self.context, 'edit_vote_group', query={'vote_group': name})
        return HTTPFound(location=url)

    @view_config(name="release_standin", context=IMeeting, permission=security.VIEW)
    def release_standin(self):
        """ Release stand-in
        """
        # TODO Check permission
        _check_ongoing_poll(self)

        group_name = self.request.GET.get('vote_group')
        group = self.request.registry.getAdapter(self.request.meeting, IVoteGroups)[group_name]
        primary = self.request.GET.get('primary')
        del group.assignments[primary]

        url = self.request.resource_url(self.context, 'vote_groups')
        return HTTPFound(location=url)


@view_config(name="edit_vote_group",
             context=IMeeting,
             permission=security.MODERATE_MEETING,
             renderer="arche:templates/form.pt")
class EditVoteGroupForm(DefaultEditForm):
    """ Edit vote group, for moderators.
    """
    title = _("Edit vote group")
    type_name = 'MeetingVoteGroup'

    @reify
    def group_name(self):
        return self.request.GET.get('vote_group')

    @reify
    def group(self):
        groups = self.request.registry.getAdapter(self.request.meeting, IVoteGroups)
        return groups[self.group_name]

    def __init__(self, context, request):
        super(EditVoteGroupForm, self).__init__(context, request)
        _check_ongoing_poll(self)

    def appstruct(self):
        return dict(title=self.group.title,
                    description=self.group.description,
                    members=self.group.members)

    def save_success(self, appstruct):
        group = self.group
        group.title = appstruct['title']
        group.description = appstruct['description']
        group.members.clear()
        group.members.update(appstruct['members'])
        # group.standins.clear()
        # group.standins.update(appstruct['standins'])
        self.flash_messages.add(self.default_success)
        url = self.request.resource_url(self.context, 'vote_groups')
        return HTTPFound(location=url)

    def cancel(self, *args):
        url = self.request.resource_url(self.context, 'vote_groups')
        return HTTPFound(location=url)

    cancel_success = cancel_failure = cancel


@view_config(name="delete_vote_group",
             context=IMeeting,
             permission=security.MODERATE_MEETING,
             renderer="arche:templates/form.pt")
class DeleteVoteGroupForm(DefaultDeleteForm):
    @property
    def title(self):
        return _("really_delete_vote_group_warning",
                 default="Really delete vote group '${vote_group_title}'? This can't be undone",
                 mapping={'vote_group_title': self.meeting_vote_groups[self.group_name].title})

    @reify
    def group_name(self):
        return self.request.GET.get('vote_group')

    @reify
    def meeting_vote_groups(self):
        return self.request.registry.getAdapter(self.request.meeting, IVoteGroups)

    def __init__(self, context, request):
        super(DeleteVoteGroupForm, self).__init__(context, request)
        _check_ongoing_poll(self)

    def delete_success(self, appstruct):
        msg = _("Deleted '${title}'",
                mapping={'title': self.meeting_vote_groups[self.group_name].title})
        self.flash_messages.add(msg, type='warning')
        del self.meeting_vote_groups[self.group_name]
        url = self.request.resource_url(self.context, 'vote_groups')
        return HTTPFound(location=url)

    def cancel_success(self, *args):
        url = self.request.resource_url(self.context, 'vote_groups')
        return HTTPFound(location=url)


@view_config(name="assign_vote",
             context=IMeeting,
             permission=security.VIEW,
             renderer="arche:templates/form.pt")
class AssignVoteForm(DefaultEditForm):
    """ Assign vote to stand-in.
    """
    # TODO Check permission
    type_name = 'MeetingVoteGroup'

    @property
    def title(self):
        return _("vote_assignment",
                 default="Choose stand-in for ${user} (${vote_group_title})",
                 mapping={
                     'user': self.for_user,
                     'vote_group_title': self.meeting_vote_groups[self.group_name].title})

    @reify
    def group_name(self):
        return self.request.GET.get('vote_group')

    @reify
    def group(self):
        groups = self.request.registry.getAdapter(self.request.meeting, IVoteGroups)
        return groups[self.group_name]

    @reify
    def for_user(self):
        return self.request.GET.get('primary')

    @reify
    def current_standin(self):
        if self.for_user in self.group.assignments:
            return self.group.assignments[self.for_user]

    def get_schema(self):
        choices = []
        for standin in self.group.free_standins:
            choices.append((standin, standin))
        return AssignVoteSchema().bind(choices=choices)

    def appstruct(self):
        return dict(standins=self.group.standins)

    @reify
    def meeting_vote_groups(self):
        return self.request.registry.getAdapter(self.request.meeting, IVoteGroups)

    def __init__(self, context, request):
        super(AssignVoteForm, self).__init__(context, request)
        _check_ongoing_poll(self)

    def save_success(self, appstruct):
        self.group.assignments[self.for_user] = appstruct['standin']
        url = self.request.resource_url(self.context, 'vote_groups')
        return HTTPFound(location=url)

    def cancel_success(self, *args):
        url = self.request.resource_url(self.context, 'vote_groups')
        return HTTPFound(location=url)


def includeme(config):
    config.scan(__name__)
