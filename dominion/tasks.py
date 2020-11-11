# Copyright 2020 Evgeny Golyshev. All Rights Reserved.
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
# limitations under the License

import time

from celery.utils.log import get_task_logger

from images.models import Image

from dominion.app import APP
from dominion.base import BaseBuildTask
from dominion.engine import EXIT_STATUS, PiemanDocker
from dominion.exceptions import DoesNotExist, Failed, Interrupted
from dominion.settings import (
    CHANNEL_NAME,
    CONTAINER_NAME,
    POLLING_FREQUENCY,
    QUEUE_BUILD_NAME,
    QUEUE_WATCH_NAME,
    TIMEOUT,
)
from dominion.util import connect_to_redis

LOGGER = get_task_logger(__name__)


@APP.task(bind=True, base=BaseBuildTask)
def build(self, image_id):
    """Builds an image. """

    container_name = CONTAINER_NAME.format(image_id=image_id)
    LOGGER.info(f'Running {container_name}')

    self.request.kwargs['image_id'] = image_id
    self.request.kwargs['pieman'] = pieman = PiemanDocker(container_name)
    pieman.run()

    watch.apply_async((image_id, ), queue=QUEUE_WATCH_NAME)

    channel_name = CHANNEL_NAME.format(image_id=image_id)
    conn = connect_to_redis()
    for line in pieman.logs(stream=True):
        conn.publish(channel_name, line)

    try:
        pieman.wait()
    except Interrupted as exc:
        conn.publish(channel_name, str(exc))
        raise exc


@APP.task
def spawn():
    """Spawns the 'build' tasks. """

    image = Image.objects.get_any()
    if image:
        image.set_started_at()
        build.apply_async((image.image_id, ), queue=QUEUE_BUILD_NAME)


@APP.task
def watch(image_id):
    """Watches the corresponding Pieman container associated with an image id. The primary goal of
    the task is to kill the container if it exceeds its time limit specified via TIMEOUT.
    """

    container_name = CONTAINER_NAME.format(image_id=image_id)
    LOGGER.info(f'Watching {container_name}')

    try:
        pieman = PiemanDocker(container_name, must_exist=True)
    except DoesNotExist:
        LOGGER.info(f'{container_name} does not exist, so finishing the task')
        return

    retries_number = TIMEOUT // POLLING_FREQUENCY
    for _ in range(retries_number):
        try:
            status = pieman.get_status()
        except DoesNotExist:
            status = EXIT_STATUS

        if status == EXIT_STATUS:
            LOGGER.info(f'{container_name} finished in time')
            break

        time.sleep(POLLING_FREQUENCY)
    else:
        LOGGER.info(f'Killing {container_name} because it exceeded its time limit.')
        pieman.kill()
