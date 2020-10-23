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

from dominion.app import APP
from dominion.base import BaseBuildTask
from dominion.settings import QUEUE_NAME


@APP.task(bind=True, base=BaseBuildTask)
def build(_self):
    """Builds an image. """

    print('Stub')


@APP.task
def spawn_builds():
    """Spawns the 'build' tasks. """

    build.apply_async((), queue=QUEUE_NAME)
