#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
#############################################################
#                                                           #
#      Copyright @ 2018 -  Dashingsoft corp.                #
#      All rights reserved.                                 #
#                                                           #
#      pyarmor                                              #
#                                                           #
#      Version: 4.3.2 -                                     #
#                                                           #
#############################################################
#
#
#  @File: packer.py
#
#  @Author: Jondy Zhao(jondy.zhao@gmail.com)
#
#  @Create Date: 2018/11/08
#
#  @Description:
#
#   Pack obfuscated Python scripts with any of third party
#   tools: py2exe, py2app, cx_Freeze, PyInstaller
#

'''After the py2exe or cx_Freeze setup script works, this tool let you
to obfuscate all the python source scripts and package them again. The
basic usage:

    python packer.py --type py2exe /path/to/src/entry.py

It will replace all the original python scripts with obfuscated ones
in the compressed archive generated by py2exe or cx_Freeze.

'''

import logging
import os
import shutil
import subprocess
import sys
import time

from distutils.util import get_platform
from py_compile import compile as compile_file
from zipfile import PyZipFile

try:
    import argparse
except ImportError:
    # argparse is new in version 2.7
    import polyfills.argparse as argparse

def logaction(func):
    def wrap(*args, **kwargs):
        logging.info('')
        logging.info('%s', func.__name__)        
        return func(*args, **kwargs)
    return wrap

@logaction
def update_library(libzip, obfdist):
    '''Update compressed library generated by py2exe or cx_Freeze, replace
the original scripts with obfuscated ones.

    '''
    # # It's simple ,but there are duplicated .pyc files
    # with PyZipFile(libzip, 'a') as f:
    #     f.writepy(obfdist)
    filelist = []
    for root, dirs, files in os.walk(obfdist):
        filelist.extend([os.path.join(root, s) for s in files])

    with PyZipFile(libzip, 'r') as f:
        namelist = f.namelist()
        f.extractall(obfdist)

    for s in filelist:
        compile_file(s, s + 'c')

    with PyZipFile(libzip, 'w') as f:
        for name in namelist:
            f.write(os.path.join(obfdist, name), name)

@logaction
def run_setup_script(src, entry, setup, packcmd, new_entry):
    '''Update entry script, copy pytransform.py to source path, then run
setup script to build the bundle.

    '''
    cwd = os.path.dirname(setup)
    script = os.path.basename(setup)

    tempfile = '%s.armor.bak' % entry
    shutil.copy('pytransform.py', src)
    shutil.move(os.path.join(src, entry), tempfile)
    shutil.move(new_entry, src)

    p = subprocess.Popen([sys.executable, script] + packcmd, cwd=cwd,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    stdoutdata, _ = p.communicate()

    shutil.move(tempfile, os.path.join(src, entry))
    os.remove(os.path.join(src, 'pytransform.py'))

    if p.returncode != 0:        
        logging.error('\n\n%s\n\n', stdoutdata)
        # raise RuntimeError('Run setup script failed')
        sys.exit(1)

@logaction
def copy_runtime_files(runtimes, output):
    for s in os.listdir(runtimes):
        if s == 'pytransform.py':
            continue
        shutil.copy(os.path.join(runtimes, s), output)

def call_armor(args):
    logging.info('')
    logging.info('')
    p = subprocess.Popen([sys.executable, 'pyarmor.py'] + list(args))
    p.wait()
    if p.returncode != 0:       
        sys.exit(1)    

def pathwrapper(func):
    def wrap(*args, **kwargs):
        path = os.getcwd()
        os.chdir(os.path.abspath(os.path.dirname(__file__)))
        try:
            return func(*args, **kwargs)
        finally:
            os.chdir(path)
    return wrap

@pathwrapper
def _packer(src, entry, setup, packcmd, output, libname):
    project = os.path.join('projects', 'build-for-packer-v0.1')
    prodist = os.path.join(project, 'dist')

    options = 'init', '-t', 'app', '-src', src, '--entry', entry, project
    call_armor(options)

    filters = ('global-include *.py', 'prune build, prune dist', 
               'exclude %s pytransform.py' % entry)
    options = ('config', '--runtime-path', '',  '--disable-restrict-mode', '1',
               '--manifest', ','.join(filters), project)
    call_armor(options)

    options = 'build', '--no-runtime', project
    call_armor(options)

    run_setup_script(src, entry, setup, packcmd, os.path.join(prodist, entry))

    update_library(os.path.join(output, libname), prodist)

    runtimes = 'packer-runtimes-v0.1'
    options = 'build', '--only-runtime', '--output', runtimes, project
    call_armor(options)

    copy_runtime_files(runtimes, output)

    shutil.rmtree(runtimes)
    shutil.rmtree(project)

def packer(args):
    _type = 'freeze' if args.type.lower().endswith('freeze') else 'py2exe'

    if args.path is None:
        src = os.path.abspath(os.path.dirname(args.entry[0]))
        entry = os.path.basename(args.entry[0])
    else:
        src = os.path.abspath(args.path)
        entry = os.path.relpath(args.entry[0], args.path)
    setup = os.path.join(src, 'setup.py') if args.setup is None \
        else os.path.abspath(args.setup)

    if args.output is None:
        dist = os.path.join(
            'build', 'exe.%s-%s' % (get_platform(), sys.version[0:3])
        ) if _type == 'freeze' else 'dist'
        output = os.path.join(os.path.dirname(setup), dist)
    else:
        output = os.path.abspath(args.output)

    packcmd = ['py2exe', '--dist-dir', output] if _type == 'py2exe' \
        else ['build', '--build-exe', output]
    libname = 'library.zip' if _type == 'py2exe' else \
        'python%s%s.zip' % sys.version_info[:2]

    logging.info('Prepare to pack obfuscated scripts with %s', args.type)
    _packer(src, entry, setup, packcmd, output, libname)

    logging.info('')
    logging.info('Pack obfuscated scripts successfully in the path')
    logging.info('')
    logging.info('\t%s', os.path.relpath(output, os.getcwd()))

def add_arguments(parser):
    parser.add_argument('-v', '--version', action='version', version='v0.1')

    parser.add_argument('-t', '--type', default='py2exe',
                        choices=('py2exe', 'py2app',
                                 'cx_Freeze', 'PyInstaller'))
    parser.add_argument('-p', '--path',
                        help='Base path, default is the path of entry script')
    parser.add_argument('-s', '--setup',
                        help='Setup script, default is setup.py')
    parser.add_argument('-O', '--output',
                        help='Directory to put final built distributions in' \
                        ' (default is output path of setup script)')
    parser.add_argument('entry', metavar='Entry Script', nargs=1,
                        help='Entry script')

def main(args):
    parser = argparse.ArgumentParser(
        prog='packer.py',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='Pack obfuscated scripts',
        epilog=__doc__,
    )
    add_arguments(parser)
    packer(parser.parse_args(args))

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)-8s %(message)s',
    )
    main(sys.argv[1:])
