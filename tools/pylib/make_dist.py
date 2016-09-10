# -*- coding: utf-8 -*-

#
# Copyright (C) 2013-2016 Frogtoss Games, Inc.
#
# Usage rights granted under repo license
#

"""
This module packages up a built Native Project Standards project into 
installers, bundles or zip files for distribution.
"""

import sys
import time
import copy
import glob
import shutil
import os.path
import argparse
import tempfile
import subprocess
from os.path import join as path_join

_VALID_ARCHS = ('x86', 'x64')

def dist_cli(argv):
    """
    DistCLI queries the user for command line options.
    """
    version_def = path_join('..', 'VERSION')
    
    parser = argparse.ArgumentParser('Generate a distributable archive')
    parser.add_argument('-A', '--arch', dest='target_arch',
                        default='x64',
                        help='architecture [x86, x64] (default x64)')
    parser.add_argument('--version-file', dest='version_file',
                        default=version_def,
                        help='version file (default is %s)' % version_def)
    parser.add_argument('-o', '--output-dir', dest='output_dir',
                        default='.', required=True,
                        help='output dir to place finished archive')
    args = parser.parse_args()

    if args.target_arch not in _VALID_ARCHS:
        print('Invalid arch specified.  Valid archs: %s' % \
              (', '.join(_VALID_ARCHS)), file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(args.version_file):
        print('Version file does not exist at %s' % args.version_file, \
              file=sys.stderr)
        sys.exit(1)
    
    # currently, there is only support for building the current platform
    args.target_platform = sys.platform
    return vars(args)
        


def get_user_arch_str(target_arch):
    """
    for 'x64' or 'x86', return (64-bit) or (32-bit)
    """
    if target_arch == 'x64':
        arch_str = '(64-bit)'
    elif target_arch == 'x86':
        arch_str = '(32-bit)'
    else:
        arch_str = None
    return arch_str

def exe(name):
    if sys.platform == 'win32':
        return name+'.exe'
    return name

def read_version(options=None):
    if options != None and 'version_file' in options:
        version_path = options['version_file']
    else:
        script_path = _get_script_path()
        version_path = path_join(script_path, '..', VERSION)

    with open(version_path, "rb") as f:
        vstr = f.read()
    return vstr.decode("utf-8").rstrip()

class AppDefinition:
    """
    a data class that defines an app

    name:        The native language name of the app
    help_url:    a url users can use to get help
    exe_name:    name of release executable without extension
    version_str: a string denoting the version
    """
    def __init__(self):
        self.name = None
        self.help_url = None
        self.exe_name = None
        self.version_str = None
        self.publisher_name = ""
        self.w32icons = []

    def add_icon(self, w32_icon):
        """
        Add a Win32Icon to this AppDefinition.
        """
        self.w32icons.append(w32_icon)

def build_all(app_def, options):
    with tempfile.TemporaryDirectory(suffix='_make_dist') as tmp_dir:
        build_dir = path_join(tmp_dir, 'build')
        os.mkdir(build_dir)

        copy_exe(app_def,
                 options['target_arch'],
                 build_dir)
        copy_dlls(app_def,
                  options['target_arch'],
                  build_dir,
                  dist_dir=None)
        copy_insert(app_def, build_dir)

        make_innosetup_installer(app_def,
                                 options['target_arch'],
                                 options['output_dir'],
                                 tmp_dir)
        

        
class DistBuilder_deprecated:
    """
    for common apps configurations, build everything in a temp directory.
    """
    def __init__(self, app_def, options):
        self.app_def = app_def
        self.options = options
        
    def build_all(self):
        with tempfile.TemporaryDirectory(suffix='_make_dist') as tmp_dir:
            build_dir = path_join(tmp_dir, 'build')
            os.mkdir(build_dir)

            print("**copying files")
            copy_exe(self.app_def,
                     self.options['target_arch'],
                     build_dir)
            copy_dlls(self.app_def,
                      self.options['target_arch'],
                      build_dir,
                      dist_dir=None)
            copy_insert(self.app_def, build_dir)

            print("**running installer")
            make_innosetup_installer(self.app_def,
                                     self.options['target_arch'],
                                     self.options['output_dir'],
                                     tmp_dir)
            input("press enter\n")



class Win32Icon:
    def __init__(self, name, filename, icon_filename):
        """
        One Win32Icon represent one InnoSetup icon file.
        @staticmethods are shortcuts.

        See http://www.jrsoftware.org/ishelp/index.php?topic=iconssection
        for what these parameters do.
        """
        self.args = {}
        self.args['name'] = _swap_slashes(name)
        self.args['filename'] = _swap_slashes(filename)
        self.args['icon_filename'] = _swap_slashes(icon_filename)

    @staticmethod
    def add_std_icons(app_def, options,
                      main_icon,
                      support_url_file):
        """
        Create all five standard icons and insert them into app_def:

        - desktop icon
        - start menu icon
        - uninstall icon
        - support url icon
        - quicklaunch icon

        main_icon: innosetup path in format "{app}/someicon.ico"
        support_url_file: innosetup path in format "{app}/somelink.url"
        """
        desktop_icon = Win32Icon.init_desktop_icon(app_def, options,
                                                   main_icon)
        startmenu_icon = Win32Icon.init_startmenu_icon(app_def, options,
                                                       main_icon)
        uninstall_icon = Win32Icon.init_uninstall_icon(app_def, options,
                                                       main_icon)
        support_icon = Win32Icon.init_support_url_icon(app_def, options,
                                                       support_url_file,
                                                       main_icon)
        quicklaunch_icon = Win32Icon.init_quicklaunch_icon(app_def, options,
                                                           main_icon)

        app_def.add_icon(desktop_icon)
        app_def.add_icon(startmenu_icon)        
        app_def.add_icon(uninstall_icon)
        app_def.add_icon(support_icon)
        app_def.add_icon(quicklaunch_icon)
        
    @staticmethod
    def _exe_path(options, app_def):
        return "{app}/bin/win32_%s/%s" % (options['target_arch'], app_def.exe_name)

    @staticmethod
    def init_desktop_icon(app_def, options, icon_filename):
        """
        static method to initialize a desktop app launch icon.

        icon_filename should be in the format {app}/filename.ico or None
        to use a void icon.
        """
        name = "{userdesktop}/%s %s" % (app_def.name,
                                        get_user_arch_str(options['target_arch']))
        return Win32Icon(name,
                         filename=Win32Icon._exe_path(options, app_def),
                         icon_filename=icon_filename)

    @staticmethod
    def init_startmenu_icon(app_def, options, icon_filename):
        """
        static method to initialize a start menu launch icon.
        """
        name = "{group}/%s %s" % (app_def.name,
                                  get_user_arch_str(options['target_arch']))
        return Win32Icon(name,
                         filename=Win32Icon._exe_path(options, app_def),
                         icon_filename=icon_filename)
        

    @staticmethod
    def init_uninstall_icon(app_def, options, icon_filename):
        """
        static method to init an uninstall icon
        """
        prog_name = "{group}/{cm:UninstallProgram,%s %s}" % \
                    (app_def.name,
                     get_user_arch_str(options['target_arch']))
        
        return Win32Icon(name=prog_name,
                         filename="{uninstallexe}",
                         icon_filename=icon_filename)

    @staticmethod
    def init_support_url_icon(app_def, options, shortcut_filename, icon_filename):
        """
        creates an icon in the app folder that is "foo on the web".
        url_filename is the name to a windows .url shortcut that is
        being installed to the user's system.  It is in the format:

        "{app}/somefile.url"
        """
        prog_name = "{group}/%s on the web" % app_def.name
        
        return Win32Icon(name=prog_name,
                         filename=shortcut_filename,
                         icon_filename=icon_filename)

    @staticmethod
    def init_quicklaunch_icon(app_def, options, icon_filename):
        """
        create a quicklaunch icon
        """
        ql_prefix = "{userappdata}/Microsoft/Internet Explorer/Quick Launch/"
        full_name = "%s %s" % (app_def.name, \
                               get_user_arch_str(options['target_arch']))
        
        icon = Win32Icon(name=ql_prefix+full_name,
                         filename=Win32Icon._exe_path(options, app_def),
                         icon_filename=icon_filename)
        icon.args['tasks'] = 'quicklaunchicon'
        return icon
        
    def add_optional_arg(self, arg, value):
        """
        Any additional arguments supported by innosetup can be passed in here.
        """
        self.args[arg] = _swap_slashes(value)

        
def _get_installer_filename(app_name, target_arch, version_str):
    bits = 32
    if target_arch == 'x64':
        bits = 64

    # always apprend 'pre' -- the idea is that a real human has to remove
    # the prerelease tag when it is time to launch
    return  "%s%s-%s-pre" % (app_name, bits, version_str)


def copy_exe(app_def, target_arch, build_dir):
    """
    copy the exe for the target_arch to the proper subdirectory in build_dir
    """
    script_path = _get_script_path()
    src_path = path_join(script_path, '..',  \
                         'build', 'vs2015', 'bin', 'Release', target_arch, \
                         app_def.exe_name)

    dst_path = path_join(build_dir, 'bin', _arch_dir(target_arch))
    os.makedirs(dst_path)
    dst_path = path_join(dst_path, app_def.exe_name)

    if not os.path.isfile(src_path):
        print("Could not find " + src_path)
        sys.exit(1)
    shutil.copyfile(src_path, dst_path)


def copy_dlls(app_def, target_arch, build_dir, dist_dir=None):
    """
    copy all dlls for the target arch to tmp_dir

    dist_dir:  The root distribution dir to copy all files from.
               (currently unsupported)
    """
    script_path = _get_script_path()

    # fixme: assumes no dist_dir
    if not dist_dir:
        src_path = path_join(script_path, '..', '..', \
                             'bin', _arch_dir(target_arch))

    dst_dir = path_join(build_dir, 'bin', _arch_dir(target_arch))

    for dll in glob.iglob(path_join(src_path, "*.dll")):
        shutil.copy(dll, dst_dir)

        
def copy_insert(app_def, build_dir):
    """
    Copy the designated directory's "insert" files into the build.
    """
    script_path = _get_script_path()

    src_path = path_join(script_path, '..', 'build', 'dist',
                         'insert_%s' % sys.platform)
    dst_path = build_dir
    _copyintotree(src_path, dst_path)
    


def make_innosetup_installer(app_def,
                             target_arch,
                             output_dir,
                             tmp_dir,
                             insert_dir=None,
                             innosetup_asset_dir=None,
                             innosetup_exe=None):
    """
    Using InnoSetup 5, create an installer executable.

    app_def:    An AppDefinition with all parameters initialized.

    target_arch: 'x86' or 'x64'

    output_dir: The directory to move the completed installer to.

    tmp_dir: The temporary root directory

    <optional>
    insert_dir: Directory of files to fully copy into root of installed directory
                or None.  Used for msvcp*.dlls, readme.txt, etc.

    installer_asset_dir:
                Directory containing assets linked in during the installer creation.

    icon_list:  List of make_dist.Win32Icons to include in the installer.

    innosetup_exe: path to innosetup if not the default install location.
    """
    script_path = _get_script_path()
    
    if insert_dir == None:
        insert_dir = path_join(script_path, '..', 'build', 'dist', 'insert_win32')
    insert_dir = os.path.abspath(insert_dir)
        
    if innosetup_asset_dir == None:
        innosetup_asset_dir = path_join(script_path, '..',
                                        'build', 'dist', 'innosetup_assets')
    innosetup_asset_dir = os.path.abspath(innosetup_asset_dir)
        
    if innosetup_exe == None:
        innosetup_exe = path_join('c:\\', 'Program Files (x86)',
                                  'Inno Setup 5', 'ISCC.exe')
    # installer path
    installer_filename = _get_installer_filename(app_def.name, \
                                                 target_arch, \
                                                 app_def.version_str)
        
    # create temp innosetup input file        
    tmpl = _innosetup_template(app_def, insert_dir, target_arch,\
                               installer_filename, path_join(tmp_dir, 'build'))
    print(tmpl)
    setup_iss = path_join(tmp_dir, 'setup.iss')
        
    with open(setup_iss, 'wt') as f:
        f.write(tmpl)
        
    cmd = [innosetup_exe, '/O'+output_dir, setup_iss]
    print(' '.join(cmd))
    po = subprocess.Popen(cmd)
    po.wait()
    if po.returncode != 0:
        print("last command errored with returncode %d" % po.returncode)
        sys.exit(1)

def _get_script_path():    
    return os.path.dirname(os.path.realpath(sys.argv[0]))

def _icon_line(param, value, quotes=True):
    return '%s: "%s"; ' % (param, value)
    
def _icon_str(icon_args):
    s =  _icon_line('Name', icon_args['name'])
    s += _icon_line('Filename', icon_args['filename'])
    if icon_args['icon_filename'] != None:
        s += _icon_line('IconFilename', icon_args['icon_filename'])
    if 'tasks' in icon_args:
        s += _icon_line('Tasks', icon_args['tasks'])
    if 'working_dir' in icon_args:
        s += _icon_line('WorkingDir', icon_args['working_dir'])
    s += '\n'
    return s


def _swap_slashes(s):
    """in-place slash swapping"""
    if s == None: return
    return s.replace('/','\\')


def _copyintotree(src, dst, symlinks=False, ignore=None):
    """Copy files in src into possibly existing directly dst"""
    if not os.path.exists(dst):
        os.makedirs(dst)
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            _copyintotree(s, d, symlinks, ignore)
        else:
            if not os.path.exists(d) or os.stat(s).st_mtime - os.stat(d).st_mtime > 1:
                shutil.copy2(s, d)

    
def _innosetup_template(app_def, insert_dir, target_arch,
                        installer_filename, build_dir):
    context = {}
    context['name'] = app_def.name
    context['help_url'] = app_def.help_url
    context['exe_name'] = app_def.exe_name
    context['version_str'] = app_def.version_str
    context['publisher_name'] = app_def.publisher_name
    context['license_path'] = path_join(insert_dir, "license.txt")
    context['year'] = time.strftime("%Y", time.gmtime())
    context['installer_filename'] = installer_filename
    context['build_dir'] = build_dir
    context['arch_dir'] = _arch_dir(target_arch)
    
    sec_setup = """; Script generated by Frogtoss make_dist.py
[Setup]
AppName=%(name)s
AppVerName=%(name)s %(version_str)s
AppPublisher=%(publisher_name)s
AppSupportUrl=%(help_url)s
AppUpdatesUrl=%(help_url)s
DefaultDirName={pf}\%(publisher_name)s\%(name)s
DefaultGroupName=%(name)s
OutputBaseFilename=%(installer_filename)s
LicenseFile=%(license_path)s
Compression=lzma2
SolidCompression=yes
AppCopyright=Copyright (C) %(year)s %(publisher_name)s
""" % context

    if target_arch == 'x64':
        sec_setup += "ArchitecturesAllowed=x64\n"
        sec_setup += "ArchitecturesInstallIn64BitMode=x64\n"

    sec_tasks = """
[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}";
Name: quicklaunchicon; Description: "Create a &Quick Launch icon"; GroupDescription: "Additional icons:"; Flags: unchecked
""" % context

    sec_icons = """
[Icons]
""" % context
    for icon in app_def.w32icons:
        sec_icons += _icon_str(icon.args)

    sec_files = """
[Files]
Source: "%(build_dir)s\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
""" % context

    sec_run = """
[Run]
Filename: "{app}\\bin\\%(arch_dir)s\\%(exe_name)s"; Description: "{cm:LaunchProgram,%(name)s}"; Flags: nowait postinstall skipifsilent
""" % context
        
    return sec_setup+sec_tasks+sec_icons+sec_files+sec_run


def _arch_dir(target_arch):
    plat = sys.platform
    return "%s_%s" % (plat, target_arch)
