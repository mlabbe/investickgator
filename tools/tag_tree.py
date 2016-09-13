#!/usr/bin/env python3

# -*- coding: utf-8 -*-

#
# Copyright (C) 2016 Frogtoss Games, Inc.
#

"""Tag a tree.
"""

import sys
import time
import os.path
import argparse
import subprocess

from os.path import join as path_join

def _get_script_path():    
    return os.path.dirname(os.path.realpath(sys.argv[0]))

def _get_project_root():
    return os.path.abspath(path_join(_get_script_path(), '..'))    

def do_args():
    p = argparse.ArgumentParser(description="tag the build")
    p.add_argument('--buildername', required=True,
                   help='name of the machine that made the build')
    p.add_argument('--buildnumber', required=True, type=int,
                   help='unique build event number')
    p.add_argument('--output-filename', required=True,
                   help='path to write out to')
    #p.add_argument('--rev-short', required=True,
    #               help='short revision')
    #p.add_argument('--rev-long', required=True,
    #               help='long revision (or same as --rev-short)')
    return p.parse_args()
                   
                   
def get_git_hashes():
    wd = _get_project_root()
    cmd = ['git', 'log', '--pretty="%h"', '-n 1']

    # Short hash
    pipe = subprocess.Popen( ' '.join(cmd), shell=True, \
                             bufsize=0, stdout=subprocess.PIPE, cwd=wd ).stdout
    hash_short = pipe.readline().decode('utf-8')
    hash_short = hash_short.rstrip()
    pipe.close()

    # Long hash
    cmd[2] = '--pretty="%H"'
    pipe = subprocess.Popen( ' '.join(cmd), shell=True, \
                             bufsize=0, stdout=subprocess.PIPE, cwd=wd ).stdout
    hash_long = pipe.readline().decode('utf-8')
    hash_long = hash_long.rstrip()
    pipe.close()
        
    return (hash_short, hash_long)

def get_timestamp():
    # style choice: Emulate DOS .bat %time% and %date%
    return time.strftime( "%a %m/%d/%Y  %I:%M:%S.00", time.localtime() )

def get_version_tuple():
    version_file = path_join(_get_project_root(), "VERSION")
    with open(version_file) as f:
        version = f.readline().rstrip()
    return tuple(version.split('.'))
        

if __name__ == '__main__':
    args = do_args()

    context = {}
    context['buildername'] = args.buildername
    context['buildnumber'] = args.buildnumber
    context['revision'], context['revision_long'] = get_git_hashes()
    context['build_timestamp'] = get_timestamp()

    version = get_version_tuple()
    context['version'] = '.'.join(map(str,version))
    context['version_major'] = version[0]
    context['version_minor'] = version[1]
    context['version_micro'] = version[2]
    
    doc = """// generated buildinfo from build server. 
// do not check in. do not modify

// name of the machine that compiled the build.
#define BUILDERNAME "%(buildername)s"

// unique build event number from builder.  
const unsigned int BUILDNUMBER=%(buildnumber)d;

// Git short hash or similar
#define REVISION "%(revision)s"

// Git long hash (or same as REVISION)
#define REVISION_LONG "%(revision_long)s"

// Build timestamp string
#define BUILD_TIMESTAMP "%(build_timestamp)s"

// version bits
#define VERSION_STRING "%(version)s"
#define VERSION_MAJOR %(version_major)s
#define VERSION_MINOR %(version_minor)s
#define VERSION_MICRO %(version_micro)s
""" % context

    print(doc)

    with open(args.output_filename, 'wt') as f:
        print(doc, file=f)
    
    sys.exit(0)
