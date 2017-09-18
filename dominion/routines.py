# Copyright 2017 Evgeny Golyshev. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import smtplib
import subprocess
from pathlib import Path

from celery.utils.log import get_task_logger
from django.core.mail import send_mail, EmailMessage

from firmwares.models import Firmware
from users.models import User


LOGGER = get_task_logger(__name__)

VALID_SUITES = {
    'Debian Jessie': 'jessie',
    'Debian Stretch': 'stretch',
}


class SuiteDoesNotSupport(Exception):
    """Exception raised by the get_suite_name function if the specified suite
    is not valid.
    """
    pass


def cp(src, dst):
    command_line = ['cp', '-r', src, dst]
    proc = subprocess.Popen(command_line)
    if proc.wait() != 0:
        LOGGER.critical('Cannot copy {} to {}'.format(src, dst))
        return False

    return True


def touch(path):
    Path(path).touch()


def get_user(user_id):
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        LOGGER.critical('User {} does not exist'.format(user_id))
        return None


def get_firmware(build_id, user):
    try:
        return Firmware.objects.get(name=build_id, user=user)
    except Firmware.DoesNotExist:
        LOGGER.critical('Firmware {} does not exist'.format(build_id))
        return None


# XXX: copy-pasted from BM. Need to share it in the future.
def get_suite_name(distro):
    if distro in VALID_SUITES.keys():
        return VALID_SUITES[distro]
    else:
        raise SuiteDoesNotSupport


def notify_user_on_success(user, image):
    distro = image.get('target', {}).get('distro', 'Image')
    subject = '{} has built!'.format(distro)
    message = ('Download it: '
               'https://cusdeb.com/download/{}'.format(image.get('id')))

    if user.userprofile.email_notifications:
        try:
            user.email_user(subject, message)
        except smtplib.SMTPException as e:
            LOGGER.error('Unable to send email: {}'.format(e))


def notify_user_on_fail(user, image):
    distro = image.get('target', {}).get('distro', 'Image')
    subject = '{} build has failed!'.format(distro)
    message = ('Sorry, something went wrong. CusDeb team has been '
               'informed about the situation.')

    if user.userprofile.email_notifications:
        try:
            user.email_user(subject, message)
        except smtplib.SMTPException as e:
            LOGGER.error('Unable to send email: {}'.format(e))


def notify_us_on_fail(user_id, image, attachment=False):
    subject = 'Build has failed!'
    message = ('Please check dominion logs. '
               'user_id: {} {}'.format(user_id, image))
    email = EmailMessage(
        subject,
        message,
        'noreply@cusdeb.com',
        ['info@cusdeb.com'],
    )
    if attachment:
        email.attach_file(attachment)
    try:
        email.send()
    except smtplib.SMTPException as e:
        LOGGER.error('Unable to send email to info@cusdeb.com: {}'.format(e))


def write(path, s):
    with open(path, 'a') as output:
        output.write(s + '\n')
