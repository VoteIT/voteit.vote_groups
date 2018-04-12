from unittest import TestCase

from pyramid import testing
from pyramid.request import apply_request_extensions
from voteit.core.models.interfaces import IMeeting
from voteit.core.testing_helpers import bootstrap_and_fixture
from zope.interface.verify import verifyClass
from zope.interface.verify import verifyObject

from voteit.vote_groups.interfaces import IVoteGroup
from voteit.vote_groups.interfaces import IVoteGroups


class VoteGroupsTests(TestCase):

    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    @property
    def _cut(self):
        from voteit.vote_groups.models import VoteGroups
        return VoteGroups

    def _mk_one(self):
        from voteit.core.models.meeting import Meeting
        groups = self._cut(Meeting())
        name = groups.new()
        group = groups[name]
        group['one'] = 'standin'
        group['two'] = 'primary'
        group['three'] = 'standin'
        group.assignments['two'] = 'one'
        name = groups.new()
        group = groups[name]
        group['three'] = 'primary'
        return groups

    def test_verify_class(self):
        self.assertTrue(verifyClass(IVoteGroups, self._cut))

    def test_verify_obj(self):
        self.assertTrue(verifyObject(IVoteGroups, self._mk_one()))

    def test_standins(self):
        groups = self._mk_one()
        self.assertEqual(groups.get_standin_for('two'), 'one')

    def test_members(self):
        groups = self._mk_one()
        self.assertEqual(groups.get_members(), {'one', 'two', 'three'})

    def test_voters(self):
        groups = self._mk_one()
        self.assertEqual(groups.get_voters(), {'one', 'three'})

    def test_primaries(self):
        groups = self._mk_one()
        self.assertEqual(groups.get_primaries(), {'two', 'three'})

    def test_nonzero(self):
        groups = self._mk_one()
        self.assertTrue(groups)

    def test_group_count(self):
        groups = self._mk_one()
        self.assertEqual(len(groups.sorted()), 2)
        self.assertEqual(len(groups.vote_groups_for_user('one')), 1)
        self.assertEqual(len(groups.vote_groups_for_user('two')), 1)
        self.assertEqual(len(groups.vote_groups_for_user('three')), 2)

    def test_free_standins(self):
        groups = self._mk_one()
        name = groups.new()
        group = groups[name]
        group['four'] = 'primary'
        group['five'] = 'standin'
        group['one'] = 'standin'
        self.assertEqual(groups.get_free_standins(group), {'five'})

    def test_traversal(self):
        groups = self._mk_one()
        name = groups.new()
        group = groups[name]
        self.failUnless(IMeeting.providedBy(group.__parent__))


class VoteGroupTests(TestCase):

    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    @property
    def _cut(self):
        from voteit.vote_groups.models import VoteGroup
        return VoteGroup

    def _mk_one(self):
        from voteit.core.models.meeting import Meeting
        from voteit.vote_groups.models import VoteGroups
        groups = VoteGroups(Meeting())
        name = groups.new()
        group = groups[name]
        group['one'] = 'standin'
        group['two'] = 'primary'
        group['three'] = 'standin'
        return group

    def test_verify_class(self):
        self.assertTrue(verifyClass(IVoteGroup, self._cut))

    def test_verify_obj(self):
        self.assertTrue(verifyObject(IVoteGroup, self._mk_one()))

    def test_members(self):
        group = self._mk_one()
        self.assertEqual(set(group.keys()), {'one', 'two', 'three'})
        self.assertEqual(set(group.primaries), {'two'})
        self.assertEqual(group.get_voters(), {'two'})

    def test_assignments(self):
        group = self._mk_one()
        group.assignments['two'] = 'one'
        self.assertEqual(group.get_voters(), {'one'})
        self.assertEqual(group.get_primary_for('one'), 'two')
        self.assertIs(group.get_primary_for('two'), None)


class UserValidatedEmailIntegrationTests(TestCase):

    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    def test_email_validated_subscriber(self):
        from arche.events import EmailValidatedEvent
        from arche.resources import User
        from voteit.core.models.meeting import Meeting
        from voteit.vote_groups.models import VoteGroups
        self.config.include('arche.testing')
        self.config.include('voteit.core.testing_helpers.register_catalog')
        root = bootstrap_and_fixture(self.config)
        request = testing.DummyRequest()
        apply_request_extensions(request)
        request.root = root
        self.config.begin(request)
        root['m'] = m = Meeting()
        root['users']['jane'] = user = User(email='hello@world.org', email_validated=True)
        groups = VoteGroups(m)
        name = groups.new()
        group = groups[name]
        group.potential_members.add('hello@world.org')
        self.config.include('voteit.vote_groups.models')
        event = EmailValidatedEvent(user)
        self.config.registry.notify(event)
        # Should have been picked up
        self.assertNotIn('hello@world.org', group.potential_members)
        # And added
        self.assertIn('jane', group)
