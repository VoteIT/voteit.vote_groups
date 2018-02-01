# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from arche.views.base import BaseView
from arche.views.base import DefaultDeleteForm
from arche.views.base import DefaultEditForm
from deform_autoneed import need_lib
from pyramid.decorator import reify
from pyramid.httpexceptions import HTTPForbidden, HTTPNotFound
from pyramid.httpexceptions import HTTPFound
from pyramid.traversal import resource_path
from pyramid.view import view_config
from voteit.vote_groups.fanstaticlib import vote_groups_js

from voteit.core import security
from voteit.core.models.interfaces import IMeeting

from voteit.vote_groups import _
from voteit.vote_groups.interfaces import IVoteGroups
from voteit.vote_groups.schemas import AssignVoteSchema
from voteit.vote_groups.schemas import ROLE_CHOICES
from voteit.vote_groups.mixins import VoteGroupEditMixin

from voteit.core.views.control_panel import control_panel_category, control_panel_link


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


class VoteGroupsView(BaseView, VoteGroupEditMixin):

    @reify
    def vote_groups(self):
        return self.request.registry.getAdapter(self.request.meeting, IVoteGroups)

    @view_config(name="vote_groups", context=IMeeting, renderer="templates/meeting_vote_groups.pt")
    def delegations_view(self):
        vote_groups_js.need()
        sorted_groups = self.request.is_moderator and \
                        self.vote_groups.sorted() or \
                        self.vote_groups.vote_groups_for_user(self.request.authenticated_userid)
        response = {
            'all_count': len(self.vote_groups),
            'vote_groups': self.vote_groups,
            'sorted_groups': sorted_groups,
            'role_choices': ROLE_CHOICES,
        }
        return response

    @view_config(name="add_vote_group", context=IMeeting, permission=security.MODERATE_MEETING)
    def add_vote_group(self):
        """ Add a new delegation and redirect to edit view.
        """
        _check_ongoing_poll(self)
        name = self.vote_groups.new()
        url = self.request.resource_url(self.context, 'edit_vote_group', query={'vote_group': name})
        return HTTPFound(location=url)

    @view_config(name="release_standin", context=IMeeting, permission=security.VIEW)
    def release_standin(self):
        """ Release stand-in
        """
        _check_ongoing_poll(self)

        group_name = self.request.GET.get('vote_group')
        group = self.request.registry.getAdapter(self.request.meeting, IVoteGroups)[group_name]
        primary = self.request.GET.get('primary')

        if not self.request.is_moderator and \
           self.request.authenticated_userid != primary:
            raise HTTPForbidden(_("You do not have authorization to change voter rights."))

        del group.assignments[primary]

        url = self.request.resource_url(self.context, 'vote_groups')
        return HTTPFound(location=url)

    @view_config(
        name='__vote_group_save_roles__',
        context=IMeeting,
        permission=security.MODERATE_MEETING,
        renderer='json')
    def save_roles(self):
        _check_ongoing_poll(self)
        # TODO Load Schema(?), validate and save.
        group = self.group
        message = None
        valid_roles = [r[0] for r in ROLE_CHOICES]

        changed = set()
        for uid, role in self.request.POST.items():
            if uid in group and group[uid] != role:
                changed.add(uid)

        change_disallowed = set(group.assignments.keys()).union(group.assignments.values())
        change_intersect = changed.intersection(change_disallowed)
        if change_intersect:
            message = _('Can not change role for user(s) ${users} with assigned voter rights.',
                        mapping={'users': ', '.join(change_intersect)})

        other_primaries = self.vote_groups.get_primaries(exclude_group=group)
        changed_to_primary = filter(lambda uid: self.request.POST[uid] == 'primary', changed)
        primary_intersect = other_primaries.intersection(changed_to_primary)
        if primary_intersect:
            message = _('User(s) ${users} are already primary in another group.',
                        mapping={'users': ', '.join(primary_intersect)})

        if message:
            return {
                'status': 'failed',
                'error_message': self.request.localizer.translate(message),
            }

        for uid in changed:
            if role in valid_roles:
                group[uid] = self.request.POST[uid]
        return {'status': 'success', 'changed_roles': len(changed)}


@view_config(name="edit_vote_group",
             context=IMeeting,
             permission=security.MODERATE_MEETING,
             renderer="arche:templates/form.pt")
class EditVoteGroupForm(DefaultEditForm, VoteGroupEditMixin):
    """ Edit vote group, for moderators.
    """
    title = _("Edit vote group")
    type_name = 'VoteGroup'

    def __init__(self, context, request):
        super(EditVoteGroupForm, self).__init__(context, request)
        _check_ongoing_poll(self)

    def appstruct(self):
        return dict(title=self.group.title,
                    description=self.group.description,
                    members=list(self.group.keys()))

    def save_success(self, appstruct):
        group = self.group
        group.title = appstruct['title']
        group.description = appstruct['description']
        previous = set(group.keys())
        incoming = set(appstruct['members'])
        for uid in previous.difference(incoming):
            del group[uid]
        for uid in incoming.difference(previous):
            group[uid] = 'observer'
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
class DeleteVoteGroupForm(DefaultDeleteForm, VoteGroupEditMixin):
    @property
    def title(self):
        return _("really_delete_vote_group_warning",
                 default="Really delete vote group '${vote_group_title}'? This can't be undone",
                 mapping={'vote_group_title': self.vote_groups[self.group_name].title})

    def __init__(self, context, request):
        super(DeleteVoteGroupForm, self).__init__(context, request)
        _check_ongoing_poll(self)

        if not request.is_moderator:
            raise HTTPForbidden(_("You do not have authorization to delete groups."))

    def delete_success(self, appstruct):
        msg = _("Deleted '${title}'",
                mapping={'title': self.vote_groups[self.group_name].title})
        self.flash_messages.add(msg, type='warning')
        del self.vote_groups[self.group_name]
        url = self.request.resource_url(self.context, 'vote_groups')
        return HTTPFound(location=url)

    def cancel_success(self, *args):
        url = self.request.resource_url(self.context, 'vote_groups')
        return HTTPFound(location=url)


@view_config(name="assign_vote",
             context=IMeeting,
             permission=security.VIEW,
             renderer="arche:templates/form.pt")
class AssignVoteForm(DefaultEditForm, VoteGroupEditMixin):
    """ Assign vote to stand-in.
    """
    type_name = 'VoteGroup'

    @property
    def title(self):
        return _("vote_assignment",
                 default="Choose stand-in for ${user} (${vote_group_title})",
                 mapping={
                     'user': self.for_user,
                     'vote_group_title': self.vote_groups[self.group_name].title})

    @reify
    def for_user(self):
        return self.request.GET.get('primary')

    @reify
    def current_standin(self):
        if self.for_user in self.group.assignments:
            return self.group.assignments[self.for_user]

    def get_schema(self):
        choices = []
        for standin in self.vote_groups.get_free_standins(self.group):
            choices.append((standin, standin))
        return AssignVoteSchema().bind(choices=choices)

    def appstruct(self):
        return dict(standins=self.group.standins)

    def __init__(self, context, request):
        super(AssignVoteForm, self).__init__(context, request)
        _check_ongoing_poll(self)

        if not request.is_moderator and \
           request.authenticated_userid not in self.group.assignments.values() and \
           request.authenticated_userid not in self.group.primaries:
            raise HTTPForbidden(_("You do not have authorization to change voter rights."))

    def save_success(self, appstruct):
        self.group.assignments[self.for_user] = appstruct['standin']
        url = self.request.resource_url(self.context, 'vote_groups')
        return HTTPFound(location=url)

    def cancel_success(self, *args):
        url = self.request.resource_url(self.context, 'vote_groups')
        return HTTPFound(location=url)


def vote_groups_active(context, request, va):
    vote_groups = request.registry.queryAdapter(request.meeting, IVoteGroups)
    if vote_groups:
        return bool(len(vote_groups))
    return False


def includeme(config):
    config.scan(__name__)
    config.add_view_action(
        control_panel_category,
        'control_panel', 'vote_groups',
        panel_group='control_panel_vote_groups',
        title=_("Vote groups"),
        description=_("Handle voter rights with vote groups."),
        permission=security.MODERATE_MEETING,
        check_active=vote_groups_active
    )
    config.add_view_action(
        control_panel_link,
        'control_panel_vote_groups', 'vote_groups',
        title=_("Manage vote groups"),
        view_name='vote_groups',
    )
