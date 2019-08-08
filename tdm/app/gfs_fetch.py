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

"""\
Fetch GFS files from a remote production service.
"""

import os
import sys
import shutil
import logging
import argparse
from datetime import datetime
from tdm.gfs.noaa import ftp_noaa_fetcher, http_noaa_fetcher

NOW = datetime.now()

LOGGER = logging.getLogger('tdm.app.gfs_fetch')

SUPPORTED_PROTOCOLS = ["ftp", "http"]


def main(args):
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    fetcher_class = ftp_noaa_fetcher \
        if args.protocol == SUPPORTED_PROTOCOLS[0] \
        else http_noaa_fetcher
    nf = fetcher_class(args.year, args.month, args.day, args.hour)
    if os.path.exists(args.target_directory):
        LOGGER.debug("Target folder '%s' already exists",
                     args.target_directory)
        if args.overwrite:
            shutil.rmtree(args.target_directory, ignore_errors=True)
            LOGGER.info("Cleaned target folder '%s'.", args.target_directory)
        else:
            LOGGER.error("Target folder already exists. "
                         "Use '--overwrite' option to enable overwrite.")
            sys.exit(99)
    os.makedirs(args.target_directory)
    nf.fetch(args.requested_resolution, args.target_directory,
             nthreads=args.n_download_threads)
    with open(args.semaphore_file, "w") as f:
        f.close()


def add_parser(subparsers):
    parser = subparsers.add_parser(
        "gfs_fetch",
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        '--year', metavar='INT', type=int,
        default=NOW.year,
        help="Requested year, defaults to current year"
    )
    parser.add_argument(
        '--month', metavar='INT', type=int,
        default=NOW.month,
        help="Requested month, defaults to current month"
    )
    parser.add_argument(
        '--day', metavar='INT', type=int,
        default=NOW.day,
        help="Requested day, defaults to today"
    )
    parser.add_argument(
        '--hour', metavar='INT', type=int,
        default=0,
        help="Requested hour, defaults to 0"
    )
    parser.add_argument(
        '--n-download-threads', metavar='INT', type=int,
        default=10,
        help="Number of parallel download threads, defaults to 10"
    )
    parser.add_argument(
        '--target-directory', metavar='DIR', type=str,
        default='/gfs/model_data',
        help="directory where the dataset should be downloaded"
    )
    parser.add_argument(
        '--semaphore-file', metavar='FILE', type=str,
        default='/gfs/.__success__',
        help="zero size semaphore file written when all went well"
    )
    parser.add_argument(
        '--requested-resolution', metavar='RESOLUTION',
        type=str, default='0p50',
        help="Requested resolution in fraction of degree. Defaults to '0p50'"
    )
    parser.add_argument(
        '--protocol', metavar='protocol',
        type=str, default=SUPPORTED_PROTOCOLS[0], choices=SUPPORTED_PROTOCOLS,
        help="Protocol {} to download data. "
             "Defaults to '{}'".format(SUPPORTED_PROTOCOLS,
                                       SUPPORTED_PROTOCOLS[0])
    )
    parser.add_argument(
        '--overwrite', action='store_true', default=False,
        help="Overwrite the target directory. Defaults to 'False'"
    )
    parser.add_argument(
        '--debug', action='store_true', default=False,
        help="Enable debug messages. Defaults to 'False'"
    )
    parser.set_defaults(func=main)
