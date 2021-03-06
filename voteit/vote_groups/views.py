# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from collections import Counter
from typing import Iterable

from arche.security import groupfinder
from arche.views.base import BaseForm
from arche.views.base import BaseView
from arche.views.base import DefaultDeleteForm
from arche.views.base import DefaultEditForm
from pyramid.decorator import reify
from pyramid.httpexceptions import HTTPForbidden
from pyramid.httpexceptions import HTTPFound
from pyramid.httpexceptions import HTTPNotFound
from pyramid.traversal import resource_path
from pyramid.view import view_config
from repoze.catalog.query import Eq

from voteit.core import security
from voteit.core.models.interfaces import IMeeting
from voteit.core.security import ROLE_VOTER
from voteit.core.views.control_panel import control_panel_category
from voteit.core.views.control_panel import control_panel_link
try:
    from voteit.qr.interfaces import IPresenceQR
except ImportError:
    IPresenceQR = None
try:
    from voteit.irl.models.interfaces import IElectoralRegister
except ImportError:
    IElectoralRegister = None

from voteit.vote_groups import _
from voteit.vote_groups.exceptions import GroupPermissionsException
from voteit.vote_groups.fanstaticlib import vote_groups_all
from voteit.vote_groups.interfaces import IVoteGroups
from voteit.vote_groups.interfaces import VOTE_GROUP_ROLES
from voteit.vote_groups.mixins import VoteGroupEditMixin
from voteit.vote_groups.mixins import VoteGroupMixin
from voteit.vote_groups.models import apply_adjust_meeting_roles


_polls_ongoing_msg = _("Note! Polls ongoing within meeting!")


class VoteGroupsView(BaseView, VoteGroupEditMixin):

    @view_config(name="vote_groups", context=IMeeting, renderer="templates/meeting_vote_groups.pt")
    def delegations_view(self):
        vote_groups_all.need()
        show_all = self.request.GET.get('show_all') == '1'
        response = {
            'vote_groups': self.vote_groups,
            'my_groups': self.vote_groups.vote_groups_for_user(self.request.authenticated_userid),
            'role_choices': dict(VOTE_GROUP_ROLES),
            'has_qr': IPresenceQR is not None,
            'show_all': show_all,
        }
        return response

    def is_voter(self, userid):
        try:
            return self._cached_voters[userid]
        except KeyError:
            pass
        except AttributeError:
            self._cached_voters = {}
        self._cached_voters[userid] = ROLE_VOTER in groupfinder(userid, self.request)
        return self._cached_voters[userid]

    def is_checked(self, userid):
        return userid in self.pqr

    @reify
    def pqr(self):
        if IPresenceQR:
            return IPresenceQR(self.context, ())
        return ()

    @view_config(name="add_vote_group", context=IMeeting, permission=security.MODERATE_MEETING)
    def add_vote_group(self):
        """ Add a new delegation and redirect to edit view.
        """
        name = self.vote_groups.new()
        url = self.request.resource_url(self.context, 'edit_vote_group', query={'vote_group': name})
        return HTTPFound(location=url)

    @view_config(name="release_standin", context=IMeeting, permission=security.VIEW)
    def release_standin(self):
        """ Release stand-in
        """
        group_name = self.request.GET.get('vote_group')
        error = False
        try:
            group = self.vote_groups[group_name]
        except KeyError:
            group = None
            self.flash_messages.add(_("No such group"), type='danger')
            error = True
        voter = self.request.GET.get('voter')
        if group:
            try:
                self.vote_groups.release_substitute(voter, group)
            except GroupPermissionsException:
                self.flash_messages.add(_("You do not have authorization to change voter rights."), type='danger')
                error = True
        if not error:
            self.flash_messages.add(_("Vote transfered"), type='success')
        url = self.request.resource_url(self.context, 'vote_groups')
        return HTTPFound(location=url)

    @view_config(
        name='__vote_group_save_roles__',
        context=IMeeting,
        permission=security.MODERATE_MEETING,
        renderer='json')
    def save_roles(self):
        # TODO Load Schema(?), validate and save.
        group = self.group
        message = None
        changed = set()
        for userid, role in self.request.POST.items():
            if userid in group and group[userid] != role:
                changed.add(userid)
        change_disallowed = set(group.assignments.keys()).union(group.assignments.values())
        change_intersect = changed.intersection(change_disallowed)
        if change_intersect:
            message = _('Can not change role for user(s) ${users} with assigned voter rights.',
                        mapping={'users': ', '.join(change_intersect)})
        other_primaries = self.vote_groups.get_primaries(exclude_group=group)
        changed_to_primary = filter(lambda userid: self.request.POST[userid] == 'primary', changed)
        primary_intersect = other_primaries.intersection(changed_to_primary)
        if primary_intersect:
            message = _('User(s) ${users} are already primary in another group.',
                        mapping={'users': ', '.join(primary_intersect)})
        if message:
            return {
                'status': 'failed',
                'error_message': self.request.localizer.translate(message),
            }
        if changed:
            for userid in changed:
                role = self.request.POST[userid]
                self.vote_groups.set_role(userid, role, group, event=False)
            self.vote_groups.notify_changed(group)
        return {
            'status': 'success',
            'changed_roles': len(changed)
        }


@view_config(name="edit_vote_group",
             context=IMeeting,
             permission=security.MODERATE_MEETING,
             renderer="arche:templates/form.pt")
class EditVoteGroupForm(DefaultEditForm, VoteGroupEditMixin):
    """ Edit vote group, for moderators.
    """
    title = _("Edit vote group")
    type_name = 'VoteGroup'

    def appstruct(self):
        return self.group.appstruct()

    def save_success(self, appstruct):
        self.vote_groups.update_from_appstruct(appstruct, self.group)
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

    def delete_success(self, appstruct):
        msg = _("Deleted '${title}'",
                mapping={'title': self.group.title})
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
    schema_name = 'assign'

    @property
    def title(self):
        return _("vote_assignment",
                 default="Choose stand-in for ${user} (${vote_group_title})",
                 mapping={
                     'user': self.for_user,
                     'vote_group_title': self.group.title})

    @reify
    def for_user(self):
        return self.request.GET.get('primary')

    @reify
    def current_standin(self):
        if self.for_user in self.group.assignments:
            return self.group.assignments[self.for_user]
        return ''

    @reify
    def allowed(self):
        return self.vote_groups.get_assign_permission(self.for_user, self.group)

    def __init__(self, context, request):
        super(AssignVoteForm, self).__init__(context, request)
        if not self.allowed:
            raise HTTPForbidden(_("You do not have authorization to change voter rights."))

    def appstruct(self):
        #Not used since you only assign new
        return {}

    def save_success(self, appstruct):
        try:
            self.vote_groups.assign_vote(self.for_user, appstruct['standin'], self.group)
        except GroupPermissionsException:
            raise HTTPForbidden(_("You do not have authorization to change voter rights."))
        self.flash_messages.add(_("Done"), type='success')
        url = self.request.resource_url(self.context, 'vote_groups')
        return HTTPFound(location=url)

    def cancel_success(self, *args):
        url = self.request.resource_url(self.context, 'vote_groups')
        return HTTPFound(location=url)
    cancel_failure = cancel_success


@view_config(name="_qr_voter_groups",
             context=IMeeting,
             permission=security.MODERATE_MEETING,
             renderer="arche:templates/form.pt")
class ApplyQRPermissionsForm(BaseForm, VoteGroupMixin):
    """ Apply permissions """
    type_name = 'VoteGroup'
    schema_name = 'apply_qr_present'
    title = _("Apply voting rights according to groups + checked in?")

    def __call__(self):
        if IPresenceQR is None:
            self.flash_messages.add(_("voteit.qr not installed"), type='danger')
            raise HTTPFound(location=self.request.resource_url(self.context))
        if self.ongoing_poll:
            # OK for admins to override here
            self.flash_messages.add(_polls_ongoing_msg, type='danger')
        return super(ApplyQRPermissionsForm, self).__call__()

    @property
    def ongoing_poll(self):
        # type: () -> bool
        _poll_query = Eq('type_name', 'Poll') & Eq('workflow_state', 'ongoing')
        query = _poll_query & Eq('path', resource_path(self.context))
        return self.request.root.catalog.query(query)[0].total > 0

    def update_electoral_register(self):
        if IElectoralRegister is None:
            self.flash_messages.add(
                _("voteit.irl not installed, so electoral register doesn't exist."),
                type='danger'
            )
        else:
            er = IElectoralRegister(self.context)
            if er.new_register_needed():
                userids = er.currently_set_voters()
                er.new_register(userids)

    def save_success(self, appstruct):
        groups = self.vote_groups
        qr = IPresenceQR(self.context)
        new_voters = groups.get_voters().intersection(qr)
        current_voters = security.find_role_userids(self.context, security.ROLE_VOTER)
        removed_voters = current_voters - new_voters
        added_voters = new_voters - current_voters
        for userid in removed_voters:
            self.context.del_groups(userid, (security.ROLE_VOTER,))
        for userid in added_voters:
            self.context.add_groups(userid, (security.ROLE_VOTER,))
        msg = _("updated_voter_permissions_notice",
                default = "Total voters: ${total}. Added ${added_count} new and removed ${removed_count}.",
                mapping = {
                    'total': len(new_voters),
                    'added_count': len(added_voters),
                    'removed_count': len(removed_voters)
                })
        self.flash_messages.add(msg)
        if appstruct['update_register']:
            self.update_electoral_register()
        return HTTPFound(location=self.request.resource_url(self.context))


@view_config(name="_copy_vote_groups",
             context=IMeeting,
             permission=security.MODERATE_MEETING,
             renderer="arche:templates/form.pt")
class CopyFromOtherMeetingForm(BaseForm, VoteGroupMixin):
    """ Copy groups from another meeting """
    type_name = 'VoteGroup'
    schema_name = 'copy'
    title = _("Copy groups from another meeting?")

    def save_success(self, appstruct):
        meeting_name = appstruct['meeting_name']
        from_meeting = self.request.root[meeting_name]
        groups = self.vote_groups
        copied_count = groups.copy_from_meeting(from_meeting)
        if copied_count:
            msg = _("Copied ${count} groups", mapping = {'count': copied_count})
            self.flash_messages.add(msg, type='success')
        else:
            msg = _("No groups to copy.")
            self.flash_messages.add(msg, type='warning')
        return HTTPFound(location=self.request.resource_url(self.context, 'vote_groups'))


@view_config(name = "add_group_tickets",
             context = IMeeting,
             renderer = "arche:templates/form.pt",
             permission = security.ADD_INVITE_TICKET)
class AddGroupTicketsForm(BaseForm, VoteGroupMixin):
    schema_name = 'add_group_tickets'
    type_name = 'VoteGroup'

    title = _("Invite participants from groups")

    def __call__(self):
        role_keys = ['assigned_voter_roles', 'inactive_voter_roles']
        check = sum(bool(self.vote_groups.settings.get(k)) for k in role_keys)
        if check != len(role_keys):
            self.flash_messages.add(_("Assign roles before inviting. At least the role view is required."), type='danger')
            raise HTTPFound(location=self.request.resource_url(self.context, 'vote_groups_settings'))
        return super(AddGroupTicketsForm, self).__call__()

    @property
    def buttons(self):
        return (self.button_add, self.button_cancel)

    def invite_emails(self, emails, roles, counter):
        # type: (Iterable, list, Counter) -> None
        for email in emails:
            result = self.context.add_invite_ticket(email, roles, sent_by=self.request.authenticated_userid)
            if result:
                counter['added'] += 1
            else:
                counter['rejected'] += 1

    def add_success(self, appstruct):
        groups = appstruct['groups']
        all_emails = self.vote_groups.get_emails(group_names=groups)

        assigned_voters = self.vote_groups.get_voters()
        # Filter on selected groups
        assigned_voter_emails = all_emails.intersection(self.vote_groups.userids_to_emails(assigned_voters))
        # Potential members included as inactive
        inactive_voter_emails = all_emails - assigned_voter_emails
        assigned_voter_roles = self.vote_groups.settings.get('assigned_voter_roles', set())
        inactive_voter_roles = self.vote_groups.settings.get('inactive_voter_roles', set())

        counter = Counter()
        self.invite_emails(assigned_voter_emails, assigned_voter_roles, counter)
        self.invite_emails(inactive_voter_emails, inactive_voter_roles, counter)

        if not counter['rejected']:
            msg = _('added_tickets_text', default = "Successfully added ${added} invites",
                    mapping={'added': counter['added']})
        elif not counter['added']:
            msg = _('no_tickets_added',
                    default = "No tickets added - all you specified probably exist already. "
                              "(Proccessed ${rejected})",
                    mapping = {'rejected': counter['rejected']})
            self.flash_messages.add(msg, type = 'warning', auto_destruct = False)
            url = self.request.resource_url(self.context, 'add_group_tickets')
            return HTTPFound(location = url)
        else:
            msg = _('added_tickets_text_some_rejected',
                    default = "Successfully added ${added} invites but discarded ${rejected} "
                              "since they already existed or were already used.",
                    mapping={'added': counter['added'], 'rejected': counter['rejected']})
        self.flash_messages.add(msg)
        self.request.session['send_tickets.emails'] = list(all_emails)
        self.request.session['send_tickets.message'] = appstruct['message']
        url = self.request.resource_url(self.context, 'send_tickets')
        return HTTPFound(location = url)


@view_config(name = "vote_groups_settings",
             context = IMeeting,
             renderer = "arche:templates/form.pt",
             permission = security.MODERATE_MEETING)
class SettingsForm(BaseForm, VoteGroupMixin):
    schema_name = 'settings'
    type_name = 'VoteGroup'
    title = _("Vote Group settings")

    @property
    def buttons(self):
        return (self.button_save, self.button_cancel)

    def appstruct(self):
        appstruct = self.vote_groups.settings
        appstruct['apply_now'] = True
        return appstruct

    def save_success(self, appstruct):
        apply_now = appstruct.pop('apply_now')
        self.vote_groups.settings = appstruct
        if apply_now:
            apply_adjust_meeting_roles(self.context)
        else:
            self.flash_messages.add(
                _("Saved, updates will occur when assignments do."), type="success")
        url = self.request.resource_url(self.context, 'vote_groups')
        return HTTPFound(location = url)

    def cancel_failure(self, *args):
        url = self.request.resource_url(self.context, 'vote_groups')
        return HTTPFound(location = url)


def vote_groups_active(context, request, *args, **kw):
    vote_groups = request.registry.queryMultiAdapter((request.meeting, request), IVoteGroups)
    if vote_groups:
        return bool(len(vote_groups))
    return False


def vote_groups_link(context, request, va, **kw):
    if vote_groups_active(context, request):
        title = request.localizer.translate(va.title)
        url = request.resource_url(request.meeting, 'vote_groups')
        return """
        <li><a href="%s">%s</a></li>
        """ % (url, title)


def includeme(config):
    config.scan(__name__)
    config.add_view_action(
        vote_groups_link,
        'nav_meeting', 'vote_groups',
        title = _("Groups"),
        permission=_(security.VIEW),
    )
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
        title=_("Manage"),
        view_name='vote_groups',
    )
    config.add_view_action(
        control_panel_link,
        'control_panel_vote_groups', 'settings',
        title=_("Settings"),
        view_name='vote_groups_settings',
    )
    config.add_view_action(
        control_panel_link,
        'control_panel_vote_groups', 'copy_vote_groups',
        title=_("Copy from another meeting"),
        view_name='_copy_vote_groups',
    )
    config.add_view_action(
        control_panel_link,
        'control_panel_vote_groups', 'add_group_tickets',
        title=_("Invite participants"),
        view_name='add_group_tickets',
    )
    if IPresenceQR is not None:
        config.add_view_action(
            control_panel_link,
            'control_panel_vote_groups', 'apply_qr_present',
            title=_("Apply present"),
            view_name='_qr_voter_groups',
        )
