# -*- coding: utf-8 -*-
#
"""Tests for this project's own RADIUS backend behaviour.

The RADIUS path had no coverage at all until the django-radius dependency was
moved off a fork and onto upstream. The library provides the protocol work; what
is asserted here is the part this project overrides, because that is what the
swap could quietly change.

The library's own `get_django_user` assigns `is_staff` and `is_superuser` from
the RADIUS reply's `Class` attribute. `CreateUserMixin` replaces that method and
discards those arguments, so a RADIUS server cannot grant Django privileges
here. That property depends on the method resolution order and on a signature
that swallows the arguments; both are asserted below so a future dependency
bump cannot restore the library's behaviour unnoticed.
"""
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from authentication.backends.radius.backends import (
    CreateUserMixin,
    RadiusBackend,
    RadiusRealmBackend,
)

User = get_user_model()


@override_settings(EMAIL_SUFFIX='radius.example.com')
class RadiusUserCreationTests(TestCase):
    def test_existing_user_is_returned_without_creating_another(self):
        existing = User.objects.create(
            username='someone', name='someone', email='someone@elsewhere.test'
        )

        user = CreateUserMixin.get_django_user('someone')

        self.assertEqual(user.pk, existing.pk)
        self.assertEqual(user.email, 'someone@elsewhere.test')
        self.assertEqual(User.objects.filter(username='someone').count(), 1)

    def test_new_user_gets_the_configured_email_suffix(self):
        user = CreateUserMixin.get_django_user('newcomer')

        self.assertEqual(user.username, 'newcomer')
        self.assertEqual(user.name, 'newcomer')
        self.assertEqual(user.email, 'newcomer@radius.example.com')

    def test_username_that_is_already_an_address_is_used_as_the_email(self):
        user = CreateUserMixin.get_django_user('person@corp.test')

        self.assertEqual(user.email, 'person@corp.test')

    def test_bytes_username_is_decoded(self):
        user = CreateUserMixin.get_django_user(b'bytesuser')

        self.assertEqual(user.username, 'bytesuser')
        self.assertEqual(User.objects.filter(username='bytesuser').count(), 1)

    def test_creation_notifies_the_radius_signal(self):
        with patch(
            'authentication.backends.radius.backends.radius_create_user'
        ) as signal:
            user = CreateUserMixin.get_django_user('signalled')

        signal.send.assert_called_once()
        self.assertEqual(signal.send.call_args.kwargs['user'], user)

    def test_existing_user_does_not_notify_the_signal(self):
        User.objects.create(username='quiet', name='quiet', email='quiet@x.test')

        with patch(
            'authentication.backends.radius.backends.radius_create_user'
        ) as signal:
            CreateUserMixin.get_django_user('quiet')

        signal.send.assert_not_called()


@override_settings(EMAIL_SUFFIX='radius.example.com')
class RadiusRemotePrivilegeTests(TestCase):
    """A RADIUS server must not be able to grant Django staff or superuser."""

    def test_remote_roles_are_discarded_for_a_new_user(self):
        user = CreateUserMixin.get_django_user(
            'elevated',
            None,
            ['admins'],
            True,
            True,
        )

        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_remote_roles_are_discarded_for_an_existing_user(self):
        User.objects.create(
            username='plain', name='plain', email='plain@x.test'
        )

        user = CreateUserMixin.get_django_user(
            'plain', None, groups=['admins'], is_staff=True, is_superuser=True
        )

        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_backends_resolve_to_the_overriding_implementation(self):
        # The library's get_django_user is what applies is_staff/is_superuser.
        # If a dependency bump ever moved this project's override out of the
        # way, the two assertions above would still pass while the real backend
        # started honouring remote roles.
        for backend in (RadiusBackend, RadiusRealmBackend):
            with self.subTest(backend=backend.__name__):
                self.assertEqual(
                    backend.get_django_user.__qualname__,
                    'CreateUserMixin.get_django_user',
                )
                defining = [
                    klass
                    for klass in backend.__mro__
                    if 'get_django_user' in klass.__dict__
                ]
                self.assertIs(defining[0], CreateUserMixin)


class RadiusClassAttributeDecodingTests(TestCase):
    """The mixin swallows a UnicodeError raised while decoding `Class`.

    Upstream may fix this; the workaround must keep failing closed until it
    does, rather than letting the error reach the caller as an auth crash.
    """

    def _backend(self, side_effect=None, return_value=None):
        class Stub:
            def _perform_radius_auth(self, client, packet):
                if side_effect is not None:
                    raise side_effect
                return return_value

        class Backend(CreateUserMixin, Stub):
            pass

        return Backend()

    def test_class_decode_unicode_error_is_swallowed(self):
        def raise_in_cl_decode():
            cl = b'\xff'
            return cl.decode('utf-8')

        try:
            raise_in_cl_decode()
        except UnicodeError as error:
            captured = error
        else:  # pragma: no cover - the decode above always raises
            self.fail('expected a UnicodeError from cl.decode')

        backend = self._backend(side_effect=captured)

        self.assertEqual(
            backend._perform_radius_auth(Mock(), Mock()), ([], False, False)
        )

    def test_successful_auth_is_passed_through(self):
        backend = self._backend(return_value=(['group'], True, False))

        self.assertEqual(
            backend._perform_radius_auth(Mock(), Mock()), (['group'], True, False)
        )


class RadiusBackendEnablementTests(TestCase):
    @override_settings(AUTH_RADIUS=True)
    def test_enabled_when_configured(self):
        self.assertTrue(RadiusBackend.is_enabled())
        self.assertTrue(RadiusRealmBackend.is_enabled())

    @override_settings(AUTH_RADIUS=False)
    def test_disabled_when_not_configured(self):
        self.assertFalse(RadiusBackend.is_enabled())
        self.assertFalse(RadiusRealmBackend.is_enabled())
