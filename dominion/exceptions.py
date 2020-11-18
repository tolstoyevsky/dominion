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

class DoesNotExist(Exception):
    """Raised if the required Pieman container does not exist. """


class Failed(Exception):
    """Raised if the status code of the Pieman container is greater than 0. """


class Interrupted(Exception):
    """Raised if the status code of the Pieman container is 137. """

    def __init__(self):
        blue = '\x1b[34m'
        reset = '\x1b[m'
        super().__init__(f'{blue}Interrupted{reset}: building exceeded its time limit.')


class UnknownStatus(Exception):
    """Raised if the 'email' task takes a status it is not familiar with. """
