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
import tarfile
from subprocess import Popen

import redis
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
    default='/var/dominion/pieman',
    help='')
)
APP.user_options['worker'].add(Option(
    '--redis-host',
    dest='redis_host',
    default='localhost',
    help='')
)
APP.user_options['worker'].add(Option(
    '--redis-port',
    dest='redis_port',
    default=6379,
    help='')
)
APP.user_options['worker'].add(Option(
    '--workspace',
    dest='workspace',
    help='')
)
BUILD_FAILED = 1
BUILDS_NUMBER_KEY = 'builds_number'
LOGGER = get_task_logger(__name__)


class ConfigBootstep(bootsteps.Step):
    def __init__(self, worker,
                 base_systems=None, builder_location=None, redis_host=None,
                 redis_port=None, workspace=None,
                 **options):
        if base_systems:
            # TODO: check if the specified directory exists
            APP.conf['BASE_SYSTEMS'] = base_systems

        if builder_location:
            APP.conf['BUILDER_LOCATION'] = builder_location

        if redis_host:
            APP.conf['REDIS_HOST'] = redis_host

        if redis_port:
            APP.conf['REDIS_PORT'] = redis_port

        if workspace:
            APP.conf['WORKSPACE'] = workspace
        else:
            APP.conf['WORKSPACE'] = '/tmp/dominion'
            if not os.path.exists(APP.conf['WORKSPACE']):
                os.makedirs(APP.conf['WORKSPACE'])

APP.steps['worker'].add(ConfigBootstep)


@APP.task(name='tasks.build')
def build(user_id, image):
    workspace = APP.conf.get('WORKSPACE')

    redis_host = APP.conf.get('REDIS_HOST')
    redis_port = APP.conf.get('REDIS_PORT')
    redis_conn = redis.StrictRedis(host=redis_host, port=redis_port)

    redis_conn.incr(BUILDS_NUMBER_KEY)

    user = routines.get_user(user_id)
    if not user:
        routines.notify_us_on_fail(user_id, image)
        # We cannot notify the user here.
        return BUILD_FAILED

    build_id = image.get('id', None)
    if not build_id:
        LOGGER.critical('There is no build id {} '
                        'for user {}'.format(build_id, user_id))
        routines.notify_us_on_fail(user_id, image)
        routines.notify_user_on_fail(user, image)
        return BUILD_FAILED

    firmware = routines.get_firmware(build_id, user)
    if not firmware:
        routines.notify_us_on_fail(user_id, image)
        routines.notify_user_on_fail(user, image)
        return BUILD_FAILED

    # Create the build script process environment
    env = {
        'PATH': os.environ['PATH'],
        'PIEMAN_PATH': APP.conf.get('BUILDER_LOCATION', './pieman'),
        'ENABLE_UNATTENDED_INSTALLATION': 'true',
        'PROJECT_NAME': build_id,
        'TERM': 'linux',
        'WORKSPACE': workspace,
        'COMPRESS_WITH_GZIP': true
    }
    target_dir = '{}/{}'.format(workspace, build_id)
    build_log_file = '{}.log'.format(target_dir)
    routines.touch(build_log_file)

    #
    # Base parameters
    #

    target = image.get('target', None)
    if target:
        device = target.get('device', None)
        if device:
            env['DEVICE'] = routines.get_device_name(device)

        distro = target.get('distro', None)
        if distro:
            env['OS'] = routines.get_os_name(distro)

    if env.get('OS', None):
        env['BASE_DIR'] = os.path.join(APP.conf.get('BASE_SYSTEMS'), env['OS'])

    #
    # Package manager
    #

    packages_list = image.get('selected_packages', None)
    if packages_list:
        env['INCLUDES'] = ','.join(packages_list) if packages_list else ''

    #
    # Users
    #

    root_password = image.get('root_password', None)
    if root_password:
        env['ENABLE_ROOT'] = 'true'
        env['PASSWORD'] = root_password

    users = image.get('users', None)
    if users:
        # Pieman can't work with multiple users so far
        env['ENABLE_USER'] = 'true'
        env['USER_NAME'] = users[0]['username']
        env['USER_PASSWORD'] = users[0]['password']

    #
    # Unsorted parameters
    #

    configuration = image.get('configuration', None)
    if configuration:
        allowed = [
            'HOST_NAME',
            'TIME_ZONE',
        ]
        env.update({k: v for k, v in configuration.items() if k in allowed})

    firmware.status = Firmware.BUILDING
    firmware.save()

    routines.write(build_log_file, 'Running build script...')
    with open(build_log_file, 'a') as output:
        command_line = ['sh', 'run.sh']
        proc = Popen(command_line, env=env, stdout=output, stderr=output)

    ret_code = proc.wait()
    if ret_code == 0:
        redis_conn.decr(BUILDS_NUMBER_KEY)

        firmware.status = Firmware.DONE
        firmware.save()
        routines.notify_user_on_success(user, image)
    else:
        redis_conn.decr(BUILDS_NUMBER_KEY)

        LOGGER.critical('Build failed: {}'.format(build_id))
        firmware.status = Firmware.FAILED
        firmware.save()
        routines.notify_us_on_fail(user_id, image, build_log_file)
        routines.notify_user_on_fail(user, image, build_log_file)

    return ret_code
