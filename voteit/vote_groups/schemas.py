# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import colander
import deform
from arche.schemas import userid_hinder_widget
from arche.validators import existing_userids
from pyramid.decorator import reify
from pyramid.httpexceptions import HTTPNotFound

from voteit.vote_groups import _
from voteit.vote_groups.interfaces import IVoteGroups


ROLE_CHOICES = (
    ('primary', _('Primary')),
    ('standin', _('Stand-in')),
    ('observer', _('Observer')),
)


class MemberSchema(colander.Schema):
    user = colander.SchemaNode(
        colander.String(),
        title=_("Username"),
        description=_("Start typing a userid"),
        widget=userid_hinder_widget,
        validator=existing_userids,
        missing='',
    )
    email = colander.SchemaNode(
        colander.String(),
        title=_("Associate with email"),
        validator=colander.Email(),
        missing='',
    )
    role = colander.SchemaNode(
        colander.String(),
        title=_('Role'),
        widget=deform.widget.SelectWidget(values=ROLE_CHOICES),
    )


class MembersSequence(colander.SequenceSchema):
    member = MemberSchema(title=_('Member'))


@colander.deferred
class VoteGroupValidator(object):
    def __init__(self, node, kw):
        self.request = kw['request']

    @reify
    def groups(self):
        return IVoteGroups(self.request.meeting)

    @reify
    def group(self):
        try:
            group_id = self.request.GET['vote_group']
        except KeyError:
            raise HTTPNotFound
        return self.groups[group_id]

    def get_users_with_role(self, members, role):
        return set([m['user'] for m in members if m['role'] == role])

    def get_users_mapping(self, users):
        return {'users': ', '.join(users)}

    def __call__(self, form, value):
        exc = colander.Invalid(form, 'Error when selecting group members')
        primaries = self.get_users_with_role(value['members'], 'primary')
        standins = self.get_users_with_role(value['members'], 'standin')

        # Users can only have one role in a group.
        all_members = [m['user'] or m['email'] for m in value['members']]
        non_unique = set([u for u in all_members if all_members.count(u) > 1])
        if non_unique:
            exc['members'] = _('User(s) ${users} have more than one role in this group.',
                               mapping=self.get_users_mapping(non_unique))

        # Users can only be primary in one group.
        intersect = primaries.intersection(self.groups.get_primaries(self.group))
        if intersect:
            exc['members'] = _('User(s) ${users} is already primary in other group.',
                               mapping=self.get_users_mapping(intersect))

        # Users with transferred voter rights can't be changed.
        changed = set()
        changed.update(set(self.group.assignments.keys()).difference(primaries))
        changed.update(set(self.group.assignments.values()).difference(standins))
        if changed:
            exc['members'] = _('Cannot change user(s) ${users} with transferred voter permission.',
                               mapping=self.get_users_mapping(changed))

        # Group members must have one of userid or email.
        for m in value['members']:
            if bool(m['user']) == bool(m['email']):
                exc['members'] = _('Users must be added with userid or email (not both).')
                break

        if len(exc.children):
            raise exc


class EditVoteGroupSchema(colander.Schema):
    title = colander.SchemaNode(
        colander.String(),
        title=_("Title"),
    )
    description = colander.SchemaNode(
        colander.String(),
        title=_("Description"),
        missing="",
        widget=deform.widget.TextAreaWidget(),
    )
    members = MembersSequence(
        title=_("Vote group members"),
        description=_("Add one UserID per row."),
    )
    validator = VoteGroupValidator


@colander.deferred
def deferred_choices_widget(node, kw):
    choices = kw.get('choices')
    return deform.widget.SelectWidget(values=choices)


class AssignVoteSchema(colander.Schema):
    standin = colander.SchemaNode(
        colander.String(),
        widget=deferred_choices_widget,
    )


def includeme(config):
    config.add_schema('VoteGroup', EditVoteGroupSchema, 'edit')
