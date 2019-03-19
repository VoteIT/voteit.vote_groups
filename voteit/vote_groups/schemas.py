# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import colander
import deform
from arche.schemas import userid_hinder_widget
from arche.validators import existing_userids
from pyramid.httpexceptions import HTTPNotFound
from voteit.core import security
from voteit.core.schemas.common import strip_and_lowercase
from voteit.core.schemas.meeting import deferred_copy_from_meeting_widget
from voteit.core.validators import html_string_validator
from voteit.core.validators import multiple_email_validator

from voteit.vote_groups import _
from voteit.vote_groups.interfaces import IVoteGroups
from voteit.vote_groups.mixins import VoteGroupEditMixin


_GROUP_ADJUSTED_ROLES = [(k, v) for (k, v) in security.STANDARD_ROLES if k != security.ROLE_VOTER]


def _getvg(meeting, request):
    return request.registry.getMultiAdapter((meeting, request), IVoteGroups)


@colander.deferred
class VoteGroupValidator(VoteGroupEditMixin):

    def __init__(self, node, kw):
        self.request = kw['request']

    def __call__(self, form, value):
        exc = colander.Invalid(form, 'Error when selecting group members')
        # Users with transferred voter rights can't be removed.
        in_assigned = set(self.group.assignments.keys() + self.group.assignments.values())
        assigned_removed = in_assigned.difference(set(value['members']))
        if assigned_removed:
            exc['members'] = _('Cannot remove user(s) ${users} with transferred voter permission.',
                               mapping={'users': ', '.join(assigned_removed)})
            raise exc


@colander.deferred
class UniqueVGTitleValidator(VoteGroupEditMixin):

    def __init__(self, node, kw):
        self.request = kw['request']

    def __call__(self, node, value):
        lowercased_existing = [x.title.lower() for x in self.vote_groups.values() if
                               x != self.group]
        if value.lower() in lowercased_existing:
            raise colander.Invalid(node, _("Already exists"))


class EditVoteGroupSchema(colander.Schema):
    title = colander.SchemaNode(
        colander.String(),
        title=_("Title"),
        validator=UniqueVGTitleValidator,
    )
    description = colander.SchemaNode(
        colander.String(),
        title=_("Description"),
        missing="",
        widget=deform.widget.TextAreaWidget(),
    )
    members = colander.SchemaNode(
        colander.Sequence(),
        colander.SchemaNode(
            colander.String(),
            title=_("Username"),
            name=_('User'),
            description=_("Start typing a userid"),
            widget=userid_hinder_widget,
            validator=existing_userids,
        )
    )
    potential_members = colander.SchemaNode(
        colander.String(),
        title=_("Emails of potential members"),
        description=_("Add one per row"),
        widget=deform.widget.TextAreaWidget(rows=4),
        preparer=strip_and_lowercase,
        validator=multiple_email_validator,
        missing="",
    )


@colander.deferred
def deferred_choices_widget(node, kw):
    request = kw['request']
    groups = _getvg(request.meeting, request)
    group_name = request.GET.get('vote_group', None)
    try:
        group = groups[group_name]
    except KeyError:
        raise HTTPNotFound("No such group")
    choices = [('', _("- Select -"))]
    for standin in groups.get_free_standins(group):
        title = request.creators_info([standin], portrait=False, at=False, no_tag=True)
        choices.append((standin, title))
    return deform.widget.SelectWidget(values=choices)


class AssignVoteSchema(colander.Schema):
    standin = colander.SchemaNode(
        colander.String(),
        title=_("Stand-in"),
        widget=deferred_choices_widget,
    )


class ApplyQRPresentVotersSchema(colander.Schema):
    update_register = colander.SchemaNode(
        colander.Bool(),
        title=_("Update electoral register too?"),
        description=_("Will only update if a new one is needed."),
        default=True,
    )


class CopyFromOtherMeetingSchema(colander.Schema):
    meeting_name = colander.SchemaNode(
        colander.String(),
        title=_("Copy groups from another meeting"),
        description=_("copy_groups_description",
                      default="You can only pick meeting where you've been a moderator. "
                              "If a group exist here already it will be skipped"),
        widget=deferred_copy_from_meeting_widget,
    )


@colander.deferred
def all_group_ids(node, kw):
    context = kw['context']
    request = kw['request']
    groups = _getvg(context, request)
    return set(groups.keys())


@colander.deferred
def selectable_groups_widget(node, kw):
    context = kw['context']
    request = kw['request']
    groups = _getvg(context, request)
    values = []
    for group in groups.sorted():
        title = "%s (%s)" % (group.title, len(group))
        values.append((group.name, title))
    return deform.widget.CheckboxChoiceWidget(values=values)


class AddGroupTicketsSchema(colander.Schema):
    message = colander.SchemaNode(
        colander.String(),
        title=_("Welcome text of the email that will be sent"),
        description=_(
            "ticket_message_description",
            default="The mail will contain instructions on how to access the meeting, "
                    "so focus on anything that might be specific for your participants."
        ),
        widget=deform.widget.TextAreaWidget(rows=5, cols=40),
        missing="",
        validator=html_string_validator,
    )
    groups = colander.SchemaNode(
        colander.Set(),
        title=_("Groups to invite from"),
        default=all_group_ids,
        widget=selectable_groups_widget,
    )


@colander.deferred
class VoteGroupsSettingsValidator(object):

    def __init__(self, node, kw):
        pass

    def __call__(self, node, value):
        # Raised if trouble
        exc = colander.Invalid(node)
        assigned_voter_roles = value['assigned_voter_roles']
        inactive_voter_roles = value['inactive_voter_roles']
        if inactive_voter_roles.difference(assigned_voter_roles):
            exc['inactive_voter_roles'] = _("Inactive users assigned more roles than active")
            raise exc


class VoteGroupsSettingsSchema(colander.Schema):
    validator = VoteGroupsSettingsValidator
    assigned_voter_roles = colander.SchemaNode(
        colander.Set(),
        title = _("Assigned voter roles"),
        description = _("Assigned to anyone who's currently active as a voter, "
                        "either as replacement or primary."),
        widget=deform.widget.CheckboxChoiceWidget(values=_GROUP_ADJUSTED_ROLES),
    )
    inactive_voter_roles = colander.SchemaNode(
        colander.Set(),
        title = _("Inactive voter roles"),
        description = _("Any difference between this and the assigned status will be removed "
                        "from any user who's currently not assigned to anything."),
        widget=deform.widget.CheckboxChoiceWidget(values=_GROUP_ADJUSTED_ROLES),
    )
    apply_now = colander.SchemaNode(
        colander.Bool(),
        title = _("Apply now?"),
    )


def includeme(config):
    config.add_schema('VoteGroup', EditVoteGroupSchema, 'edit')
    config.add_schema('VoteGroup', AssignVoteSchema, 'assign')
    config.add_schema('VoteGroup', ApplyQRPresentVotersSchema, 'apply_qr_present')
    config.add_schema('VoteGroup', CopyFromOtherMeetingSchema, 'copy')
    config.add_schema('VoteGroup', AddGroupTicketsSchema, 'add_group_tickets')
    config.add_schema('VoteGroup', VoteGroupsSettingsSchema, 'settings')
