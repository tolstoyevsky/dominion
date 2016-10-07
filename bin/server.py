#!/usr/bin/env python3
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
import socket

import tornado.options
import tornado.web
import tornado.websocket
from shirow.ioloop import IOLoop
from shirow.server import RPCServer, remote
from tornado import gen
from tornado.options import options

import dominion.util
from dominion.tasks import MAGIC_PHRASE


class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r'/dominion/token/([_\-\w\.]+)', Dominion),
        ]
        tornado.web.Application.__init__(self, handlers)


class Dominion(RPCServer):
    def __init__(self, application, request, **kwargs):
        RPCServer.__init__(self, application, request, **kwargs)

        self._attempts_number = 30
        self._fd_added = False  # to prevent adding fd twice
        self._ptyfd = None
        self._redis_key = None
        self._sock = None

    def _bind(self, socket_name):
        while True:
            try:
                self._sock.bind(socket_name)
            except OSError as e:
                if e.errno == errno.EADDRINUSE:
                    # After closing one of the previous connections there must
                    # be the possibility, using the same socket name, to
                    # re-create the server in order to receive the file
                    # descriptor one more time.
                    self.logger.debug('Removing old socket')
                    os.unlink(socket_name)

                continue

            break

    def create(self):
        self._redis_key = dominion.util.get_redis_key(self.user_id)

    @remote
    def get_rt_build_log(self, request):
        socket_name = None

        for i in range(self._attempts_number):
            socket_name = self.redis_conn.get(self._redis_key)
            if socket_name:
                break
            else:
                self.logger.debug('Could not get a socket name')
                yield gen.sleep(1)

        if not socket_name:
            error_message = 'Build process is not running'
            request.ret_error(error_message)
            self.logger.error(error_message)
            return

        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._bind(socket_name)
        self._sock.listen(1)

        def request_handler(*args, **kwargs):
            sock, addr = self._sock.accept()
            (message, [fd, ]) = dominion.util.recv_fds(sock)
            self._ptyfd = fd

            # Cleaning up
            self.io_loop.remove_handler(self._sock.fileno())
            self._sock.close()

        self.io_loop.add_handler(self._sock.fileno(), request_handler,
                                 self.io_loop.READ)

        def build_log_handler(*args, **kwargs):
            try:
                data = os.read(self._ptyfd, 65536)
                request.ret_and_continue(data.decode('utf8'))

                # Cleaning up
                if data == MAGIC_PHRASE:
                    self.io_loop.remove_handler(self._ptyfd)
                    self._ptyfd = None
            except OSError:
                pass

        for i in range(self._attempts_number):
            if self._ptyfd and not self._fd_added:
                fd = os.fdopen(self._ptyfd)
                self.io_loop.add_handler(fd, build_log_handler,
                                         self.io_loop.READ)
                self._fd_added = True
                break

            self.logger.debug('An fd has not been received yet')
            yield gen.sleep(1)

        if not self._ptyfd:
            error_message = 'An fd has not been received'
            request.ret_error(error_message)
            self.logger.error(error_message)


def main():
    tornado.options.parse_command_line()
    IOLoop().start(Application(), options.port)

if __name__ == "__main__":
    main()
