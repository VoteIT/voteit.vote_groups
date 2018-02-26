# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import colander
import deform
from arche.schemas import userid_hinder_widget
from arche.validators import existing_userids
from voteit.core.schemas.common import strip_and_lowercase
from voteit.core.schemas.meeting import deferred_copy_from_meeting_widget
from voteit.core.validators import multiple_email_validator

from voteit.vote_groups import _
from voteit.vote_groups.interfaces import IVoteGroups
from voteit.vote_groups.mixins import VoteGroupEditMixin


ROLE_CHOICES = (
    ('primary', _('Primary')),
    ('standin', _('Stand-in')),
    ('observer', _('Observer')),
)


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
        lowercased_existing = [x.title.lower() for x in self.vote_groups.values() if x != self.group]
        if value.lower() in lowercased_existing:
            raise colander.Invalid(node, _("Already exists"))


class EditVoteGroupSchema(colander.Schema):
    title = colander.SchemaNode(
        colander.String(),
        title=_("Title"),
        validator = UniqueVGTitleValidator,
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
        title = _("Emails of potential members"),
        description = _("Add one per row"),
        widget=deform.widget.TextAreaWidget(rows=4),
        preparer=strip_and_lowercase,
        validator=multiple_email_validator,
        missing="",
    )


@colander.deferred
def deferred_choices_widget(node, kw):
    choices = kw.get('choices')
    return deform.widget.SelectWidget(values=choices)


class AssignVoteSchema(colander.Schema):
    standin = colander.SchemaNode(
        colander.String(),
        widget=deferred_choices_widget,
    )


class ApplyQRPresentVotersSchema(colander.Schema):
    update_register = colander.SchemaNode(
        colander.Bool(),
        title = _("Update electoral register too?"),
        description = _("Will only update if a new one is needed."),
        default = True,
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


def includeme(config):
    config.add_schema('VoteGroup', EditVoteGroupSchema, 'edit')
    config.add_schema('VoteGroup', ApplyQRPresentVotersSchema, 'apply_qr_present')
    config.add_schema('VoteGroup', CopyFromOtherMeetingSchema, 'copy')
