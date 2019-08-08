# Copyright 2018-2019 CRS4
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# SITE: https://www.emc.ncep.noaa.gov/GFS/impl.php

import os
import re
import time
import logging
import datetime
import requests
from math import pow
from ftplib import FTP
from concurrent import futures
from abc import ABC, abstractmethod
from requests_html import HTMLSession

LOGGER = logging.getLogger('tdm.gfs.noaa')


class noaa_fetcher(ABC):
    NOAA_DATASET_FOLDER_SIZE = 196608
    FETCH_ATTEMPTS = 3

    def __init__(self, year, month, day, hour):
        self.date = datetime.datetime(year, month, day, hour, 0)
        self.ds = 'gfs.%s' % self.date.strftime("%Y%m%d")
        LOGGER.info('Initialized for dataset %s', self.ds)

    def is_dataset_ready(self):
        available_groups = self.list_available_dataset_groups()
        LOGGER.debug("Available groups: %r", available_groups)
        return (self.ds in available_groups and
                available_groups[self.ds]['size']
                <= self.NOAA_DATASET_FOLDER_SIZE)

    @classmethod
    @abstractmethod
    def list_files_in_path(cls, path):
        pass

    @classmethod
    @abstractmethod
    def list_available_dataset_groups(cls):
        pass

    @abstractmethod
    def fetch_file(self, ds_path, fname, tdir):
        pass

    def fetch(self, res, tdir, pattern='gfs.t%Hz.pgrb2',
              nthreads=4, tsleep=300):
        def recover_results(fut_by_name):
            failed = []
            for fut in futures.as_completed(fut_by_fname):
                fname = fut_by_fname[fut]
                try:
                    res = fut.result()
                except Exception as exc:
                    LOGGER.error('%s generated an exception: %s', fname, exc)
                    failed.append(fname)
                    LOGGER.info('adding %s to failed', fname)
                else:
                    LOGGER.info('%s saved in %s', fname, res)
            return failed

        ds_path = os.path.join(self.NOAA_BASE_PATH, self.ds,
                               "{:02d}".format(self.date.hour))
        pre = self.date.strftime(pattern) + '.' + res
        LOGGER.info('Fetching %s/%s into %s', self.ds, pre, tdir)
        while not self.is_dataset_ready():
            LOGGER.info('Dataset %s not ready, sleeping for %d sec',
                        self.ds, tsleep)
            time.sleep(tsleep)
        files = [f for f in self.list_files_in_path(ds_path)
                 if f.startswith(pre) and not f.endswith('.idx')]
        begin = datetime.datetime.now()
        with futures.ThreadPoolExecutor(max_workers=nthreads) as executor:
            for i in range(self.FETCH_ATTEMPTS):
                fut_by_fname = {executor.submit(self.fetch_file,
                                                ds_path, fname, tdir): fname
                                for fname in files}
                files = recover_results(fut_by_fname)
                if len(files) == 0:
                    dt = datetime.datetime.now() - begin
                    LOGGER.info('It took %s secs to fetch %s.',
                                dt.total_seconds(), self.ds)
                    break
                else:
                    LOGGER.info(
                        'At fetch iteration %d of %d, %d files missing.',
                        i, self.FETCH_ATTEMPTS, len(files))
            else:
                LOGGER.error(
                    'Still %d files missing after %d iteration.',
                    len(files), self.FETCH_ATTEMPTS)


class ftp_noaa_fetcher(noaa_fetcher):
    NOAA_SERVER = 'ftp.ncep.noaa.gov'
    NOAA_BASE_PATH = '/pub/data/nccf/com/gfs/prod/'

    def __init__(self, year, month, day, hour):
        noaa_fetcher.__init__(self, year, month, day, hour)

    @classmethod
    def list_files_in_path(cls, path):
        entries = {}

        def add_clean_entry(x):
            size, name = [x.split()[i] for i in (4, 8)]
            entries[name] = {'size': int(size), 'name': name}

        with FTP(cls.NOAA_SERVER) as ftp:
            ftp.login()
            ftp.cwd(path)
            ftp.retrlines('LIST', callback=add_clean_entry)

        return entries

    @classmethod
    def list_available_dataset_groups(cls):
        return cls.list_files_in_path(cls.NOAA_BASE_PATH)

    def fetch_file(self, ds_path, fname, tdir):
        LOGGER.info('Fetching %s/%s into %s', self.ds, fname, tdir)
        begin = datetime.datetime.now()
        target = os.path.join(tdir, fname)
        with FTP(self.NOAA_SERVER) as ftp:
            ftp.login()
            ftp.cwd(ds_path)
            cmd = 'RETR %s' % fname
            ftp.retrbinary(cmd, open(target, 'wb').write,
                           blocksize=1024 * 1024)
        dt = datetime.datetime.now() - begin
        LOGGER.info('It took %s secs to fetch %s',
                    dt.total_seconds(), fname)
        return target


class http_noaa_fetcher(noaa_fetcher):
    A = "a"
    HREF = 'href'
    NOAA_SERVER = "http://www.ftp.ncep.noaa.gov"
    NOAA_BASE_PATH = "data/nccf/com/gfs/prod"

    def __init__(self, year, month, day, hour):
        noaa_fetcher.__init__(self, year, month, day, hour)
        self._session = None

    @property
    def session(self):
        if not self._session:
            self._session = requests.Session()
        return self._session

    @classmethod
    def to_bytes(cls, d):
        power = {"K": 1, "M": 2, "G": 3, "T": 4, "P": 5}
        r = re.search('(\d+)([KGMTP])', d)
        return int(r.group(1)) * pow(1024, power[r.group(2)]) if r else int(d) if r else 0

    @classmethod
    def list_files_in_path(cls, path):
        entries = {}
        url = os.path.join(cls.NOAA_SERVER, path)
        LOGGER.debug("Listing files in path %s", url)
        r = HTMLSession().get(url)
        if r.status_code == 200:
            LOGGER.debug(r.html.absolute_links)
            for a in r.html.find("a"):
                m = re.search("<a.*>([\w\.-/]+)</a>\s*([\w-]+)\s*([\d:]+)\s*([\dKMGTP-]+)", str(a.raw_html))
                if m:
                    name = m.group(1)[:-1] if m.group(1).endswith('/') else m.group(1)
                    entries[name] = {'name': name,
                                     'size': cls.to_bytes(m.group(4))}
        else:
            LOGGER.error("Unable to list path '%s' (error %r)", url, r.status_code)
        return entries

    @classmethod
    def list_available_dataset_groups(cls):
        return cls.list_files_in_path(cls.NOAA_BASE_PATH)

    def fetch_file(self, ds_path, fname, tdir):
        LOGGER.info('Fetching %s/%s into %s', self.ds, fname, tdir)
        begin = datetime.datetime.now()
        target = os.path.join(tdir, fname)
        url = os.path.join(self.NOAA_SERVER, ds_path, fname)
        r = self.session.get(url, allow_redirects=True)
        if r.status_code == 200:
            open(target, 'wb').write(r.content)
            dt = datetime.datetime.now() - begin
            LOGGER.info('It took %s secs to fetch %s',
                        dt.total_seconds(), fname)
        else:
            LOGGER.error("Unable to download file '%s' (error %r)", url, r.status_code)
        return target
