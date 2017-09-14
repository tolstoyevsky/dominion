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
import tarfile

from celery import Celery, bootsteps
from celery.bin import Option
from celery.utils.log import get_task_logger

from dominion import routines
from firmwares.models import Firmware


APP = Celery('tasks', backend='rpc://', broker='amqp://guest@localhost//')
APP.user_options['worker'].add(Option(
    '--base-systems',
    dest='base_systems',
    default='/var/dominion',
    help='The path to the directory which contains chroot environments '
         'which, in turn, contain the Debian base system')
)
APP.user_options['worker'].add(Option(
    '--builder-location',
    dest='builder_location',
    default='/var/dominion/rpi23-gen-image',
    help='')
)
APP.user_options['worker'].add(Option(
    '--workspace',
    dest='workspace',
    help='')
)
BUILD_FAILED = 1
LOGGER = get_task_logger(__name__)


class ConfigBootstep(bootsteps.Step):
    def __init__(self, worker,
                 base_systems=None, builder_location=None, workspace=None,
                 **options):
        if base_systems:
            # TODO: check if the specified directory exists
            APP.conf['BASE_SYSTEMS'] = base_systems

        if builder_location:
            APP.conf['BUILDER_LOCATION'] = builder_location

        if workspace:
            APP.conf['WORKSPACE'] = workspace
        else:
            APP.conf['WORKSPACE'] = '/tmp/dominion'
            if not os.path.exists(APP.conf['WORKSPACE']):
                os.makedirs(APP.conf['WORKSPACE'])

APP.steps['worker'].add(ConfigBootstep)


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
    suite = routines.get_suite_name(target['distro'])
    base_system = os.path.join(APP.conf.get('BASE_SYSTEMS'), suite + '-armhf')
    builder_location = APP.conf.get('BUILDER_LOCATION', './rpi23-gen-image')
    workspace = APP.conf.get('WORKSPACE')

    user = routines.get_user(user_id)
    if not user:
        routines.notify_us_on_fail(user_id, image)
        # We cannot notify the user here.
        return BUILD_FAILED

    if not build_id:
        LOGGER.critical('There is no build id {} for user {}'.format(build_id, 
                                                                     user_id))
        routines.notify_us_on_fail(user_id, image)
        routines.notify_user_on_fail(user, image)
        return BUILD_FAILED

    firmware = routines.get_firmware(build_id, user)
    if not firmware:
        routines.notify_us_on_fail(user_id, image)
        routines.notify_user_on_fail(user, image)
        return BUILD_FAILED

    # rpi23-gen-image creates
    # ./workspace/xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx/build, but we have to
    # create ./workspace/xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx/intermediate to
    # store the rootfs of the future image.
    target_dir = '{}/{}'.format(workspace, build_id)
    intermediate_dir = '{}/{}'.format(target_dir, 'intermediate')
    LOGGER.info('intermediate: {}'.format(intermediate_dir))
    build_log_file = '{}.log'.format(target_dir)

    routines.touch(build_log_file)
    routines.write(build_log_file, 'Starting build task...')

    try:
        os.makedirs(target_dir)
    except OSError:
        LOGGER.critical('The directory {} already exists'.format(target_dir))
        routines.notify_us_on_fail(user_id, image)
        routines.notify_user_on_fail(user, image)
        return BUILD_FAILED

    routines.write(build_log_file, 'Copying rootfs '
                                   'to {}...'.format(intermediate_dir))
    if not routines.cp(base_system, intermediate_dir):
        LOGGER.critical('Cannot copy {} to {}'.format(base_system,
                                                      intermediate_dir))
        routines.notify_us_on_fail(user_id, image)
        routines.notify_user_on_fail(user, image)
        return BUILD_FAILED

    apt_includes = ','.join(packages_list) if packages_list else ''
    env = {
        'PATH': os.environ['PATH'],
        'BASEDIR': target_dir,
        'CHROOT_SOURCE': intermediate_dir,
        'IMAGE_NAME': target_dir,
        'WORKSPACE_DIR': workspace,  # TODO: check and remove
        'BUILD_ID': build_id,  # TODO: check and remove
        'RPI2_BUILDER_LOCATION': builder_location,
        'APT_INCLUDES': apt_includes
    }

    if root_password:
        env['ENABLE_ROOT'] = 'true'
        env['PASSWORD'] = root_password

    if target:
        model = '3' if target['device'] == 'Raspberry Pi 3' else '2'
        env['RELEASE'] = suite
        env['RPI_MODEL'] = model

    if users:
        user = users[0]  # rpi23-gen-image can't work with multiple users
        env['ENABLE_USER'] = 'true'
        env['USER_NAME'] = user['username']
        env['USER_PASSWORD'] = user['password']

    if configuration:
        allowed = [
            'HOSTNAME',
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

    routines.write(build_log_file, 'Running build script...')
    with open(build_log_file, 'a') as output:
        command_line = ['sh', 'run.sh']
        proc = subprocess.Popen(command_line, env=env, stdout=output,
                                stderr=output)

    ret_code = proc.wait()
    shutil.rmtree(target_dir)  # cleaning up

    if ret_code == 0:
        os.chdir(workspace)
        with tarfile.open(build_id + '.tar.gz', 'w:gz') as tar:
            for name in [build_id + '.img', build_id + '.bmap', ]:
                tar.add(name)

        os.remove(build_id + '.img')
        os.remove(build_id + '.bmap')

        firmware.status = Firmware.DONE
        firmware.save()
        routines.notify_user_on_success(user, image)
    else:
        LOGGER.critical('Build failed: {}'.format(build_id))
        firmware.status = Firmware.FAILED
        firmware.save()
        routines.notify_us_on_fail(user_id, image)
        routines.notify_user_on_fail(user, image)

    return ret_code
