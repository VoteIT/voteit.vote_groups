from unittest import TestCase

from pyramid import testing
from zope.interface.verify import verifyClass
from zope.interface.verify import verifyObject

from voteit.vote_groups.interfaces import IVoteGroup
from voteit.vote_groups.interfaces import IVoteGroups

from voteit.vote_groups.models import VoteGroups
from voteit.vote_groups.models import VoteGroup


class VoteGroupsTests(TestCase):

    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    @property
    def _cut(self):
        return VoteGroups

    def _mk_one(self):
        from voteit.core.models.meeting import Meeting
        groups = self._cut(Meeting())
        name = groups.new()
        group = groups[name]
        group['one'] = 'standin'
        group['two'] = 'primary'
        group['three'] = 'observer'
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


class VoteGroupTests(TestCase):

    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    @property
    def _cut(self):
        return VoteGroup

    def _mk_one(self):
        # type: () -> VoteGroup
        from voteit.core.models.meeting import Meeting
        from voteit.vote_groups.models import VoteGroups
        groups = VoteGroups(Meeting())
        name = groups.new()
        group = groups[name]
        group['one'] = 'standin'
        group['two'] = 'primary'
        group['three'] = 'observer'
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