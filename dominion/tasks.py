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

import errno
import os
import pty
import shutil
import socket
import subprocess
import threading
import time

import django
import redis
from celery import Celery, bootsteps
from celery.bin import Option
from celery.utils.log import get_task_logger

import dominion.util
from firmwares.models import Firmware
from users.models import User


app = Celery('tasks', backend='rpc://', broker='amqp://guest@localhost//')
app.user_options['worker'].add(Option(
    '--base-system',
    dest='base_system',
    default='/var/dominion/jessie-armhf',
    help='The path to a chroot environment which contains '
         'the Debian base system')
)
app.user_options['worker'].add(Option(
    '--builder-location',
    dest='builder_location',
    default='/var/dominion/rpi2-gen-image',
    help='')
)
app.user_options['worker'].add(Option(
    '--workspace',
    dest='workspace',
    default='/var/dominion/workspace',
    help='')
)

django.setup()


class ConfigBootstep(bootsteps.Step):
    def __init__(self, worker,
                 base_system=None, builder_location=None, workspace=None,
                 **options):
        if base_system:
            # TODO: check if the specified directory exists
            app.conf['BASE_SYSTEM'] = base_system

        if builder_location:
            app.conf['BUILDER_LOCATION'] = builder_location

        if workspace:
            app.conf['WORKSPACE'] = workspace

app.steps['worker'].add(ConfigBootstep)

LOGGER = get_task_logger(__name__)
MAGIC_PHRASE = b"Let's wind up"


def pass_fd(sock, socket_name, fd):
    """Connects to the server when it's ready and passes fd to it"""

    while True:
        try:
            sock.connect(socket_name)
        except OSError as e:
            if e.errno == errno.ENOENT:
                LOGGER.debug('The socket does not exist')

            if e.errno == errno.ECONNREFUSED:
                LOGGER.debug('Connection refused')

            time.sleep(1)
            continue

        break

    dominion.util.send_fds(sock, fd)


def get_user(user_id):
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return None


@app.task(name='tasks.build')
def build(user_id, build_id, packages_list=None, root_password=None,
          users=None, target=None):
    if packages_list is None:
        packages_list = []

    base_system = app.conf.get('BASE_SYSTEM', './jessie-armhf')
    builder_location = app.conf.get('BUILDER_LOCATION', './rpi2-gen-image')
    workspace = app.conf.get('WORKSPACE', './workspace')
    # ./workspace/63afa1cf-3599-4b76-818a-e2064d7fc829/build
    # ./workspace/63afa1cf-3599-4b76-818a-e2064d7fc829/intermediate
    target_dir = '{}/{}'.format(workspace, build_id)
    intermediate_dir = '{}/{}'.format(target_dir, 'intermediate')

    try:
        os.makedirs(target_dir)
    except os.error as e:
        LOGGER.critical('Cannot create tmp directory ({0}): {1}'.
                        format(e.errno, e.strerror))

    command_line = ['cp', '-r', base_system, intermediate_dir]
    proc = subprocess.Popen(command_line)
    proc.wait()

    LOGGER.info('intermediate: {}'.format(intermediate_dir))

    pid, fd = pty.fork()
    if pid == 0:  # child
        apt_includes = ','.join(packages_list) if packages_list else ''
        env = {
            'PATH': os.environ['PATH'],
            'BASEDIR': target_dir,
            'CHROOT_SOURCE': intermediate_dir,
            'IMAGE_NAME': '{}/{}'.format(workspace, build_id),
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

        command_line = ['sh', 'run.sh']
        os.execvpe(command_line[0], command_line, env)
    else:  # parent
        redis_conn = redis.StrictRedis()

        redis_key = dominion.util.get_redis_key(user_id)
        socket_name = '/tmp/{}'.format(build_id)

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        thread = threading.Thread(target=pass_fd, args=(sock, socket_name, fd))
        thread.start()

        os.waitpid(pid, 0)

        user = get_user(user_id)
        if user:
            firmware = Firmware(name=build_id, user=user)
            firmware.save()
        else:
            LOGGER.critical('User {} does not exist'.format(user))

        os.write(fd, MAGIC_PHRASE)

        # Cleaning up
        redis_conn.delete(redis_key)
        shutil.rmtree(target_dir)
