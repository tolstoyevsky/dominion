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

import redis

from dominion.settings import REDIS_HOST, REDIS_PORT


def connect_to_redis():
    """Connects to the specified Redis server. The function raises the exceptions derived from
    redis.exceptions.RedisError in case of a problem.
    """

    conn = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT)
    conn.ping()

    return conn
