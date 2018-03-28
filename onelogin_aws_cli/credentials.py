"""
Handles the saving and loading of username and password in a secure
manner
"""
import getpass
from typing import List

import keyring
from onelogin.api.models.device import Device

from onelogin_aws_cli.configuration import Section


class MFACredentials(object):
    """
    Class to encapsulate the handling and storage of MFA devices, and
    retrieving of OTP's
    """

    def __init__(self):
        self._interactive = True
        self._device_index = None
        self._devices = []
        self._otp = None

        self.reset()

    @property
    def has_device(self) -> bool:
        """True if the MFA has an MFA device selected waiting to be used"""
        return (self._device_index is not None) and \
               (self._device_index < len(self._devices))

    @property
    def has_otp(self) -> bool:
        """True if the MFA has an OTP waiting to be used"""
        return self._otp is not None

    @property
    def device(self) -> Device:
        """
        Return the device selected by the user

        :return:
        """
        return self._devices[self._device_index]

    @property
    def otp(self) -> str:
        """
        Return the OTP for the MFA and reset the OTP.
        OTP's can only be used once, so it will be reset after.

        :return:
        """
        result = self._otp
        self._otp = None
        return result

    def ready(self):
        """If the MFA is ready to be used"""
        return self.has_otp and self.has_device

    def reset(self):
        """Remove all state from this class"""

        self._devices = []
        self._device_index = None

        self._otp = None

    def select_device(self, devices: List[Device]):
        """
        Given a list of MFA devices, select one for use
        :param devices:
        """

        self._devices = devices

        if len(self._devices) > 1:

            if not self._interactive:
                raise MissingMfaDeviceException()

            for i, device in enumerate(self._devices):
                print("{i}. {device}".format(
                    i=i + 1,
                    device=device.type
                ))

            device_num = input("Which OTP Device? ")
            self._device_index = int(device_num) - 1
        else:
            self._device_index = 0

    def prompt_token(self):
        """Ask the user for an OTP token"""
        if not self._interactive:
            raise MissingMfaOtpException()

        self._otp = input("{device} Token: ".format(device=self.device.type))


class UserCredentials(object):
    """
    Class to encapsulate the handling of storing and retrieving user password
    in OS-Independent system keychain.
    """
    SERVICE_NAME = "onelogin-aws-cli"

    def __init__(self, username, config: Section):
        self.username = username
        self.configuration = config

        # This is `None`, as the password should be be emitted from this class
        # and should never be loaded from any other source outside this class
        self.password = None

        self._interactive = True

    @property
    def has_password(self) -> bool:
        """
        True if the class has a password.

        :return:Whether we have set a password or not, yet
        """
        return (self.password is not None) and \
               (self.password != "")

    def disable_interactive(self):
        """
        Disable all user prompts. In the event there is missing data,
        an exception will be thrown in place of a user prompt.
        """
        self._interactive = False

    def load_credentials(self):
        """Load the username and password"""

        self.load_username()
        self.load_password()

    def load_username(self):
        """
        Either load the username from configfile or prompt the user to supply
        one interactively
        """

        if not self.username:
            # Try the configurationfile first
            if 'username' in self.configuration:
                username = self.configuration['username']
            elif not self._interactive:
                raise MissingUsernameException()
            else:
                username = input("Onelogin Username: ")
            self.username = username

    def load_password(self):
        """
        Load the password from keychain if we expect to be able to save the
        password in a keychain, or prompt the user for a password through
        stdin.
        """

        save_password = False

        # Do we have a password?
        if not self.has_password:
            # Can we load the password from os keychain?
            if self.configuration.can_save_password:

                # Load the password from OS keychain
                self._load_password_from_keychain()

                # Could not find password in OS keychain
                if not self.has_password:
                    # Ask user for password
                    self._prompt_user_password()
                    # Remember to save password
                    save_password = True

                if not self.has_password:
                    # We still don't have a password and have exhausted all
                    # places to load one from.
                    raise RuntimeError(
                        "Could not load password from secure store " +
                        "nor from user input"
                    )
            else:
                # Ask the user
                self._prompt_user_password()

            if save_password:
                # We decided to save the password
                print("Saving password to keychain...")
                self._save_password_to_keychain()

    def _prompt_user_password(self):
        if not self._interactive:
            raise MissingPasswordException()
        self.password = getpass.getpass("Onelogin Password: ")

    def _load_password_from_keychain(self):
        self.password = keyring.get_password(self.SERVICE_NAME, self.username)

    def _save_password_to_keychain(self):
        keyring.set_password(self.SERVICE_NAME, self.username, self.password)


class MissingCredentials(Exception):
    """Superclass for missing credentials"""
    TYPE = "DEFAULT"

    def __init__(self):
        super().__init__("ONELOGIN_" + self.TYPE + "_MISSING")


class MissingPasswordException(Exception):
    """Throw when a required password can not be found"""
    TYPE = "PASSWORD"


class MissingUsernameException(Exception):
    """Throw when a required password can not be found"""
    TYPE = "USERNAME"


class MissingMfaDeviceException(Exception):
    """Throw when a required password can not be found"""
    TYPE = "MFA_DEVICE"


class MissingMfaOtpException(Exception):
    """Throw when a required password can not be found"""
    TYPE = "MFA_OTP"