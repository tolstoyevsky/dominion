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

import array
import socket

MESSAGE = b'ptyfd'


def get_redis_key(user_id):
    return 'user:{}:build'.format(user_id)


def send_fds(sock, fd):
    return sock.sendmsg([MESSAGE],
                        [(socket.SOL_SOCKET,
                          socket.SCM_RIGHTS,
                          array.array('i', [fd]))])


def recv_fds(sock, fds_number=1):
    fds = array.array('i')
    control_message_len = fds_number * fds.itemsize

    message, ancdata, flags, addr = \
        sock.recvmsg(len(MESSAGE), socket.CMSG_LEN(control_message_len))
    for cmsg_level, cmsg_type, cmsg_data in ancdata:
        if cmsg_level == socket.SOL_SOCKET and \
           cmsg_type == socket.SCM_RIGHTS:
            # Append data, ignoring any truncated integers at the end.
            s = cmsg_data[:len(cmsg_data) - (len(cmsg_data) % fds.itemsize)]
            fds.fromstring(s)

    return message, list(fds)
