# Copyright 2016 Evgeny Golyshev. All Rights Reserved.
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

import os
import shutil
import subprocess
from pathlib import Path

import django
import smtplib
from django.core.mail import send_mail
from celery import Celery, bootsteps
from celery.bin import Option
from celery.utils.log import get_task_logger

from firmwares.models import Firmware
from users.models import User


APP = Celery('tasks', backend='rpc://', broker='amqp://guest@localhost//')
APP.user_options['worker'].add(Option(
    '--base-system',
    dest='base_system',
    default='/var/dominion/jessie-armhf',
    help='The path to a chroot environment which contains the Debian base '
         'system')
)
APP.user_options['worker'].add(Option(
    '--builder-location',
    dest='builder_location',
    default='/var/dominion/rpi2-gen-image',
    help='')
)
APP.user_options['worker'].add(Option(
    '--workspace',
    dest='workspace',
    help='')
)
LOGGER = get_task_logger(__name__)
BUILD_FAILED = 1

django.setup()


class ConfigBootstep(bootsteps.Step):
    def __init__(self, worker,
                 base_system=None, builder_location=None, workspace=None,
                 **options):
        if base_system:
            # TODO: check if the specified directory exists
            APP.conf['BASE_SYSTEM'] = base_system

        if builder_location:
            APP.conf['BUILDER_LOCATION'] = builder_location

        if workspace:
            APP.conf['WORKSPACE'] = workspace
        else:
            APP.conf['WORKSPACE'] = '/tmp/dominion'
            if not os.path.exists(APP.conf['WORKSPACE']):
                os.makedirs(APP.conf['WORKSPACE'])

APP.steps['worker'].add(ConfigBootstep)


def _cp(src, dst):
    command_line = ['cp', '-r', src, dst]
    proc = subprocess.Popen(command_line)
    if proc.wait() != 0:
        LOGGER.critical('Cannot copy {} to {}'.format(src, dst))
        return False

    return True


def _touch(path):
    Path(path).touch()


def _get_user(user_id):
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        LOGGER.critical('User {} does not exist'.format(user_id))
        return None


def _get_firmware(build_id, user):
    try:
        firmware = Firmware.objects.get(name=build_id, user=user)
    except Firmware.DoesNotExist:
        LOGGER.critical('Firmware {} does not exist'.format(build_id))
        return None


def _notify_user_on_success(user, image):
    distro = image.get('target', {}).get('distro', 'Image')
    subject = '{} has built!'.format(distro)
    message = ('You can directly download it from Dashboard: '
               'https://cusdeb.com/dashboard/')
    if user.userprofile.email_notifications:
        user.email_user(subject, message)


def _notify_user_on_fail(user, image):
    distro = image.get('target', {}).get('distro', 'Image')
    subject = '{} build has failed!'.format(distro)
    message = ('Sorry, something went wrong. Cusdeb team has been '
               'informed about the situation.')
    if user.userprofile.email_notifications:
        user.email_user(subject, message)


def _notify_us_on_fail(user_id, image):
    try:
        send_mail('Build has failed!',
                  'Please check dominion logs. user_id: {} {}'.format(user_id, 
                                                                      image),
                  'noreply@cusdeb.com',
                  ['info@cusdeb.com'],
                  fail_silently=False)
    except smtplib.SMTPException as e:
        LOGGER.error('Unable to send email to info@cusdeb.com: {}'.format(e))

def _write(path, s):
    with open(path, 'a') as output:
        output.write(s + '\n')


@APP.task(name='tasks.build')
def build(user_id, image):
    build_id = image.get('id', None)
    packages_list = image.get('selected_packages', None)
    if packages_list is None:
        packages_list = []
    root_password = image.get('root_password', None)
    users = image.get('users', None)
    target = image.get('target', None)
    configuration = image.get('configuration', None)
    base_system = APP.conf.get('BASE_SYSTEM', './jessie-armhf')
    builder_location = APP.conf.get('BUILDER_LOCATION', './rpi2-gen-image')
    workspace = APP.conf.get('WORKSPACE')

    user = _get_user(user_id)
    if not user:
        _notify_us_on_fail(user_id, image)
        # it cannot notify user here
        return BUILD_FAILED;
    if not build_id:
        LOGGER.critical('There is no build id {} for user {}'.format(build_id, 
                                                                     user_id))
        _notify_us_on_fail(user_id, image)
        _notify_user_on_fail(user, image)
        return BUILD_FAILED
    firmware = _get_firmware(build_id, user)
    if not firmware:
        _notify_us_on_fail(user_id, image)
        _notify_user_on_fail(user, image)
        return BUILD_FAILED;

    # rpi23-gen-image creates
    # ./workspace/xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx/build, but we have to
    # create ./workspace/xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx/intermediate to
    # store the rootfs of the future image.
    target_dir = '{}/{}'.format(workspace, build_id)
    intermediate_dir = '{}/{}'.format(target_dir, 'intermediate')
    LOGGER.info('intermediate: {}'.format(intermediate_dir))
    build_log_file = '{}.log'.format(target_dir)

    _touch(build_log_file)
    _write(build_log_file, 'Starting build task...')

    try:
        os.makedirs(target_dir)
    except OSError:
        LOGGER.critical('The directory {} already exists'.format(target_dir))
        _notify_us_on_fail(user_id, image)
        _notify_user_on_fail(user, image)
        return BUILD_FAILED

    _write(build_log_file, 'Copying rootfs to {}...'.format(intermediate_dir))
    if not _cp(base_system, intermediate_dir):
        LOGGER.critical('Cannot copy {} to {}'.format(base_system,
                                                      intermediate_dir))
        _notify_us_on_fail(user_id, image)
        _notify_user_on_fail(user, image)
        return BUILD_FAILED

    apt_includes = ','.join(packages_list) if packages_list else ''
    env = {
        'PATH': os.environ['PATH'],
        'BASEDIR': target_dir,
        'CHROOT_SOURCE': intermediate_dir,
        'IMAGE_NAME': target_dir,
        'WORKSPACE_DIR': workspace,
        'BUILD_ID': build_id,
        'RPI2_BUILDER_LOCATION': builder_location,
        'APT_INCLUDES': apt_includes
    }

    if root_password:
        env['ENABLE_ROOT'] = 'true'
        env['PASSWORD'] = root_password

    if target:
        model = '3' if target['device'] == 'Raspberry Pi 3' else '2'
        env['RPI_MODEL'] = model

    if users:
        user = users[0]  # rpi23-gen-image can't work with multiple users
        env['ENABLE_USER'] = 'true'
        env['USER_NAME'] = user['username']
        env['USER_PASSWORD'] = user['password']

    if configuration:
        allowed = [
            'HOSTNAME',
            'DEFLOCAL',
            'TIMEZONE',
            'ENABLE_REDUCE',
            'REDUCE_APT',
            'REDUCE_DOC',
            'REDUCE_MAN',
            'REDUCE_VIM',
            'REDUCE_BASH',
            'REDUCE_HWDB',
            'REDUCE_SSHD',
            'REDUCE_LOCALE'
        ]
        configuration = \
            {k: v for k, v in configuration.items() if k in allowed}
        env.update(configuration)

    firmware.status = Firmware.BUILDING
    firmware.save()

    _write(build_log_file, 'Running build script...')
    with open(build_log_file, 'a') as output:
        command_line = ['sh', 'run.sh']
        proc = subprocess.Popen(command_line, env=env, stdout=output,
                                stderr=output)

    ret_code = proc.wait()
    shutil.rmtree(target_dir)  # cleaning up

    if ret_code == 0:
        firmware.status = Firmware.DONE
        _notify_user_on_success(user, image)
    else:
        firmware.status = Firmware.FAILED
        LOGGER.critical('Build failed: {}'.format(build_id))
        _notify_us_on_fail(user_id, image)
        _notify_user_on_fail(user, image)

    firmware.save()

    return ret_code
