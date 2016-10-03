"""
/**
 *   Copyright (C) 2016 BRGM (http:///brgm.fr)
 *   Copyright (C) 2016 Oslandia <infos@oslandia.com>
 *
 *   This library is free software; you can redistribute it and/or
 *   modify it under the terms of the GNU Library General Public
 *   License as published by the Free Software Foundation; either
 *   version 2 of the License, or (at your option) any later version.
 *
 *   This library is distributed in the hope that it will be useful,
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 *   Library General Public License for more details.
 *   You should have received a copy of the GNU Library General Public
 *   License along with this library; if not, see <http://www.gnu.org/licenses/>.
 */
"""
from builtins import object
# -*- coding: utf-8 -*-
import os
import tempfile

class URI(object):
    def __init__(self, uri, urlopener = None):
        self.set_uri(uri)
        self.__urlopener = urlopener

    def set_uri(self, uri):
        # the original URI
        self.__uri = uri
        if uri.startswith('http://'):
            self.__is_remote = True
            self.__prefix = uri[0:7]
            self.__path = uri[7:].split('/')
        elif uri.startswith('https://'):
            self.__is_remote = True
            self.__prefix = uri[0:8]
            self.__path = uri[8:].split('/')
        else:
            self.__is_remote = False
            if os.path.isabs(uri):
                drive, tail = os.path.splitdrive(uri)
                if drive == '':
                    self.__prefix = '/'
                else:
                    self.__prefix = drive + os.sep
                self.__path = tail.split(os.sep)[1:]
            else:
                self.__prefix = ''
                self.__path = uri.split(os.sep)

    def uri(self):
        return self.__uri
    def parent_uri(self):
        if self.__is_remote:
            return self.__prefix + '/'.join(self.__path[:-1])
        else:
            return self.__prefix + self.dirname()

    def is_remote(self):
        return self.__is_remote

    def dirname(self):
        return os.sep.join(self.__path[:-1])
    def path(self):
        return os.sep.join(self.__path)

    def resolve(self, local_file = None):
        """If the uri is remote, use the urlopener to download it and store it locally.
        If the uri is local, check that it exists.
        Returns the local file"""
        if self.__is_remote:
            if local_file is None:
                of = tempfile.NamedTemporaryFile()
                opath = of.name
                of.close()
                of = open(opath, "w+")
            else:
                opath = local_file
                of = open(opath, "w+")
            f = self.__urlopener(self.__uri)
            of.write(f.read())
            of.close()
            f.close()
            return opath
        else:
            if not os.path.exists(self.__uri):
                raise RuntimeError("File does not exist")
            else:
                return self.__uri

    def open(self):
        if self.__is_remote:
            return self.__urlopener(self.__uri)
        else:
            if not os.path.exists(self.__uri):
                raise RuntimeError("File does not exist")
            else:
                return open(self.__uri, 'r')

        
            
