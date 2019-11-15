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
Will create a index of the GRIB files present in src dir in dst dir as
required by WPS.
"""

import argparse
import string
import glob
import os


def link_grib(src_dir, dst_dir):
    files = glob.glob(os.path.join(src_dir, "*"))
    dst_paths = ['GRIBFILE.'+i+j+k for i in string.ascii_uppercase
                 for j in string.ascii_uppercase
                 for k in string.ascii_uppercase]
    assert len(dst_paths) >= len(files)
    for f, t in zip(files, dst_paths):
        if not os.path.exists(os.path.join(dst_dir, t)):
            os.symlink(f, os.path.join(dst_dir, t))


def main(args):
    link_grib(args.source_directory, args.target_directory)


def add_parser(subparsers):
    parser = subparsers.add_parser(
        "link_grib",
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        '--target-directory', metavar='DIR', type=str,
        default='/run',
        help="directory where indexing files should be written"
    )
    parser.add_argument(
        '--source-directory', metavar='DIR', type=str,
        default='/gfs/model_data',
        help="directory with the GRIB files"
    )
    parser.set_defaults(func=main)
