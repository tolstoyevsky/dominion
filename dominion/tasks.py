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

from celery.utils.log import get_task_logger
from dominion.app import APP
from dominion.base import BaseBuildTask
from dominion.settings import QUEUE_BUILD_NAME
from images.models import Image

LOGGER = get_task_logger(__name__)


@APP.task(bind=True, base=BaseBuildTask)
def build(self, image_id):
    """Builds an image. """

    self.request.image_id = image_id
    LOGGER.info(f'Building {image_id}')


@APP.task
def spawn_builds():
    """Spawns the 'build' tasks. """

    image = Image.objects.get_any()
    if image:
        image.set_started_at()
        build.apply_async((image.image_id, ), queue=QUEUE_BUILD_NAME)
