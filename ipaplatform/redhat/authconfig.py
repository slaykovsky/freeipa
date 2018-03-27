# Authors: Simo Sorce <ssorce@redhat.com>
#          Alexander Bokovoy <abokovoy@redhat.com>
#          Tomas Babej <tbabej@redhat.com>
#
# Copyright (C) 2007-2014  Red Hat
# see file 'COPYING' for use and warranty information
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
import six
import abc
import re

from ipaplatform.paths import paths
from ipapython import ipautil
from ipapython.admintool import ScriptError
import os

FILES_TO_NOT_BACKUP = ['passwd', 'group', 'shadow', 'gshadow']

logger = logging.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class RedHatAuthTool(object):

    @staticmethod
    def get_tool():
        return RedHatAuthSelect()

    @abc.abstractmethod
    def configure(self, sssd, mkhomedir, statestore):
        pass

    @abc.abstractmethod
    def unconfigure(self, fstore, statestore,
                    was_sssd_installed,
                    was_sssd_configured):
        pass

    @abc.abstractmethod
    def backup(self, path):
        pass

    @abc.abstractmethod
    def restore(self, path):
        pass


class RedHatAuthSelect(RedHatAuthTool):

    def __get_authselect_current_output(self):
        current = ipautil.run([
                paths.AUTHSELECT,
                "current"
        ])
        return current.raw_output

    def __parse_authselect_output(self, output_text=None):
        if output_text is None:
            output_text = self.__get_authselect_current_output()

        cfg_params = re.findall(
            ".*?:\s*(\S+)\s*\\n.*?:\s*(.*)",
            output_text,
            re.DOTALL
        )

        profile = cfg_params[0][0]

        if not profile:
            return None

        features = re.findall("-\s*(\S+)", cfg_params[0][1], re.DOTALL)

        return (profile, features)

    def configure(self, sssd, mkhomedir, statestore):
        if not sssd:
            logger.error("no-sssd options is not supported by installer. "
                         "For client installation without sssd check the "
                         "output of 'ipa-advise config-fedora-authconfig'")
            return
            # raise ScriptError("Non-sssd installation is not supported")

        cfg = self.__parse_authselect_output()
        if cfg:
            statestore.backup_state('authselect', 'profile', cfg[0])
            statestore.backup_state('authselect', 'features_list',
                                    " ".join(cfg[1]))

        cmd = [paths.AUTHSELECT, "select", "sssd"]
        if mkhomedir:
            cmd.append("with-mkhomedir")
        cmd.append("--force")

        ipautil.run(cmd)

    def unconfigure(self, fstore, statestore,
                    was_sssd_installed,
                    was_sssd_configured):

        if not statestore.has_state('authselect'):
            return

        profile = statestore.restore_state('authselect', 'profile')
        features = statestore.restore_state('authselect', 'features_list')

        cmd = [paths.AUTHSELECT, "select", profile, features, "--force"]
        ipautil.run(cmd)

    def backup(self, path):
        current = ipautil.run([
                paths.AUTHSELECT,
                "current"
        ])

        with open(os.path.join(path, "authselect.backup"), 'wb') as f:
            f.write(current.raw_output)

    def restore(self, path):
        with open(os.path.join(path, "authselect.backup"), "r") as f:
            cfg = self.__parse_authselect_output(f.read())

            if cfg:
                profile = cfg[0]

                cmd = [
                    paths.AUTHSELECT, "select",
                    profile, " ".join(cfg[1]),
                    "--force"
                ]
                ipautil.run(cmd)


# RedHatAuthConfig concrete class definition to be removed later
# when agreed on exact path to migrate to authselect
class RedHatAuthConfig(RedHatAuthTool):
    """
    AuthConfig class implements system-independent interface to configure
    system authentication resources. In Red Hat systems this is done with
    authconfig(8) utility.

    AuthConfig class is nothing more than a tool to gather configuration
    options and execute their processing. These options then converted by
    an actual implementation to series of a system calls to appropriate
    utilities performing real configuration.

    If you need to re-use existing AuthConfig instance for multiple runs,
    make sure to call 'AuthConfig.reset()' between the runs.
    """

    def __init__(self):
        self.parameters = {}

    def enable(self, option):
        self.parameters[option] = True
        return self

    def disable(self, option):
        self.parameters[option] = False
        return self

    def add_option(self, option):
        self.parameters[option] = None
        return self

    def add_parameter(self, option, value):
        self.parameters[option] = [value]
        return self

    def reset(self):
        self.parameters = {}
        return self

    def build_args(self):
        args = []

        for (option, value) in self.parameters.items():
            if type(value) is bool:
                if value:
                    args.append("--enable%s" % (option))
                else:
                    args.append("--disable%s" % (option))
            elif type(value) in (tuple, list):
                args.append("--%s" % (option))
                args.append("%s" % (value[0]))
            elif value is None:
                args.append("--%s" % (option))
            else:
                args.append("--%s%s" % (option, value))

        return args

    def execute(self, update=True):
        if update:
            self.add_option("update")

        args = self.build_args()
        try:
            ipautil.run([paths.AUTHCONFIG] + args)
        except ipautil.CalledProcessError:
            raise ScriptError("Failed to execute authconfig command")

    def configure(self, sssd, mkhomedir, statestore):
        if sssd:
            statestore.backup_state('authconfig', 'sssd', True)
            statestore.backup_state('authconfig', 'sssdauth', True)
            self.enable("sssd")
            self.enable("sssdauth")
        else:
            statestore.backup_state('authconfig', 'ldap', True)
            self.enable("ldap")
            self.enable("forcelegacy")

            statestore.backup_state('authconfig', 'krb5', True)
            self.enable("krb5")
            self.add_option("nostart")

        if mkhomedir:
            statestore.backup_state('authconfig', 'mkhomedir', True)
            self.enable("mkhomedir")

        self.execute()
        self.reset()

    def unconfigure(self, fstore, statestore,
                    was_sssd_installed,
                    was_sssd_configured):
        if statestore.has_state('authconfig'):
            # disable only those configurations that we enabled during install
            for conf in ('ldap', 'krb5', 'sssd', 'sssdauth', 'mkhomedir'):
                cnf = statestore.restore_state('authconfig', conf)
                # Do not disable sssd, as this can cause issues with its later
                # uses. Remove it from statestore however, so that it becomes
                # empty at the end of uninstall process.
                if cnf and conf != 'sssd':
                    self.disable(conf)
        else:
            # There was no authconfig status store
            # It means the code was upgraded after original install
            # Fall back to old logic
            self.disable("ldap")
            self.disable("krb5")
            if not(was_sssd_installed and was_sssd_configured):
                # Only disable sssdauth. Disabling sssd would cause issues
                # with its later uses.
                self.disable("sssdauth")
            self.disable("mkhomedir")

        self.execute()
        self.reset()

    def backup(self, path):
        try:
            ipautil.run([paths.AUTHCONFIG, "--savebackup", path])
        except ipautil.CalledProcessError:
            raise ScriptError("Failed to execute authconfig command")

        # do not backup these files since we don't want to mess with
        # users/groups during restore. Authconfig doesn't seem to mind about
        # having them deleted from backup dir
        files_to_remove = [os.path.join(path, f) for f in FILES_TO_NOT_BACKUP]
        for filename in files_to_remove:
            try:
                os.remove(filename)
            except OSError:
                pass

    def restore(self, path):
        try:
            ipautil.run([paths.AUTHCONFIG, "--restorebackup", path])
        except ipautil.CalledProcessError:
            raise ScriptError("Failed to execute authconfig command")
