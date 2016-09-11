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

import re
import sys
import time
import copy
import glob
import shutil
import os.path
import argparse
import tempfile
import subprocess

from apple_bundle import AppleBundle
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
    publisher_name: Company name
    icon_graphics_path: Path to directory containing source png files for icons
    w32icons:    A list of Win32Icons
    """
    def __init__(self):
        self.name = None
        self.help_url = None
        self.exe_name = None
        self.version_str = None
        self.publisher_name = ""
        self.icon_graphics_path = path_join('..', 'build', 'dist', 'icon_src')
        self.w32icons = []

    def add_icon(self, w32_icon):
        """
        Add a Win32Icon to this AppDefinition.
        """
        self.w32icons.append(w32_icon)

def build_all(app_def, options):
    """run through all of the build steps for the platform"""
    with tempfile.TemporaryDirectory(suffix='_make_dist') as tmp_dir:
        if options['target_platform'] == 'win32':
            build_dir = path_join(tmp_dir, 'build')
            os.mkdir(build_dir)

            copy_exe(app_def,
                     options,
                     build_dir,
                     'vs2015')
            copy_dlls(app_def,
                      options['target_arch'],
                      build_dir,
                      dist_dir=None)

            # generate an icon with the app's name and stick it in the root
            # of the built project.
            # this can be referenced with "{app}/appname.ico" in InnoSetup
            # files.
            #
            # this is done before the insert is copied, so an explicitly
            # created icon overrides the generated one.
            icon_path = path_join(build_dir, '%s.ico' % app_def.name.lower())
            generate_icon(app_def.icon_graphics_path,
                          options['target_platform'],
                          icon_path)
            
            copy_insert(app_def, build_dir)


            make_innosetup_installer(app_def,
                                     options['target_arch'],
                                     options['output_dir'],
                                     tmp_dir)

        elif options['target_platform'] == 'darwin':
            script_path = _get_script_path()            
            exe_src_path = path_join(script_path, '..',
                                     'build', 'gmake_macosx', 'bin',
                                     'Release', options['target_arch'],
                                     app_def.exe_name)

            icon_path = path_join(tmp_dir, 'icon.icns')
            generate_icon(app_def.icon_graphics_path, options['target_platform'],
                          icon_path)

            # fixme: this does not copy dlls and it should
            ab = AppleBundle(app_def.name, exe_src_path, \
                             icon_path, app_def.version_str)
            ab.write(tmp_dir)

            build_dmg(app_def,
                      tmp_dir,
                      options['output_dir'])

        elif options['target_platform'] == 'linux':
            archive_dir = app_def.name.lower() + '-' + app_def.version_str
            archive_path = path_join(tmp_dir, archive_dir)
            os.makedirs(archive_path)
            
            copy_exe(app_def,
                     options,
                     archive_path,
                     'gmake_linux')
            # fixme: this does not copy dlls
            copy_insert(app_def,
                        archive_path)

            build_tgz(app_def,
                      tmp_dir,
                      options['output_dir'],
                      options['target_arch'])


        
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

        
def _get_installer_filename(app_name, target_arch, version_str, include_bits):
    bits = 32
    if target_arch == 'x64':
        bits = 64

    # always apprend 'pre' -- the idea is that a real human has to remove
    # the prerelease tag when it is time to launch
    if include_bits:
        return  "%s%s-%s-pre" % (app_name, bits, version_str)
    else:
        return "%s-%s-pre" % (app_name, version_str)


def copy_exe(app_def, options, dst_build_dir, src_build_folder):
    """
    copy the exe for the target_arch to the proper subdirectory in dst_build_dir

    src_build_folder: the folder name in /build for the target platform
    """
    script_path = _get_script_path()
    target_arch = options['target_arch']

    src_path = path_join(script_path, '..',  \
                         'build', src_build_folder, 'bin', 'Release', \
                         target_arch, app_def.exe_name)

    dst_path = path_join(dst_build_dir, 'bin', _arch_dir(target_arch))
    os.makedirs(dst_path)
    dst_path = path_join(dst_path, app_def.exe_name)

    if not os.path.isfile(src_path):
        print("Could not find " + src_path)
        sys.exit(1)
    shutil.copyfile(src_path, dst_path)
    if sys.platform == 'linux':
        _run_cmd(['chmod', '+x', dst_path])


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
    

def generate_icon(icon_graphics_path, target_platform, out_path):
    """
    Generate at icon for the target platform, returning the path to a tempfile
    that is that icon.

    icon_graphics_path: a path containing exclusively png files. See
    lazyicon.py for more detail.

    If out_path has .icns extension, it will generate a mac
    icon.  .ico generates windows icon.
    """
    script_path = path_join(_get_script_path(), 'lazyicon.py')
    cmd = [sys.executable, script_path, '-i', icon_graphics_path,
           '-o', out_path]
    _run_cmd(cmd)
    
    

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
                                                 app_def.version_str,
                                                 include_bits=True)
        
    # create temp innosetup input file        
    tmpl = _innosetup_template(app_def, insert_dir, target_arch,\
                               installer_filename, path_join(tmp_dir, 'build'))
    print(tmpl)
    setup_iss = path_join(tmp_dir, 'setup.iss')
        
    with open(setup_iss, 'wt') as f:
        f.write(tmpl)
        
    cmd = [innosetup_exe, '/O'+output_dir, setup_iss]
    _run_cmd(cmd)

def build_dmg(app_def, tmp_dir, output_dmg_dir):
    """
    Build a dmg containing an app bundle at tmp_dir.
    """
    dmg_filename = _get_installer_filename(app_def.name,
                                           'x64',
                                           app_def.version_str,
                                           include_bits=False) + '.dmg'
    dmg_path = path_join(tmp_dir, dmg_filename)

    # create writeable disk image
    cmd = ['hdiutil', 'create', '-megabytes', '400', dmg_path, '-layout', 'NONE']
    _run_cmd(cmd)

    # mount the image, get the device name
    cmd = ['hdid', '-nomount', dmg_path]
    result = _run_cmd(cmd, get_stdout=True)
    device_name = result.readline().decode("utf-8").rstrip()

    # format the mounted disk as hfs+ volume
    _run_cmd(['newfs_hfs', '-v', app_def.name, device_name])

    # unmount the formatted disk
    _run_cmd(['hdiutil', 'eject', device_name])

    # mount image as editable
    result = _run_cmd(['hdid', dmg_path], get_stdout=True)
    result = result.readline().decode("utf-8").rstrip()
    (device_name, volume_name) = re.split('\s\s+', result)

    # copy app bundle to mounted volume
    bundle_dir = glob.glob(path_join(tmp_dir, "*.app"))[0]
    app_bundle_path = path_join(tmp_dir, bundle_dir)
    _run_cmd(['cp', '-rv', bundle_dir, volume_name])

    # unmount the rw volume
    _run_cmd(['hdiutil', 'eject', device_name])

    # Compress and make read-only
    if not os.path.exists(output_dmg_dir):
        os.makedirs(output_dmg_dir)

    output_path = path_join(output_dmg_dir, dmg_filename)
    if os.path.exists(output_path):
        os.remove(output_path)
    _run_cmd(['hdiutil', 'convert', '-format', 'UDZO', dmg_path,
              '-o', output_path])
    

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


def build_tgz(app_def, in_dir, output_dir, target_arch):
    """
    Build a .tar.gz distributable at output_dir with the intended
    archive name, copying all of the files in in_dir.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    out_filename = _get_installer_filename(app_def.name,
                                           target_arch,
                                           app_def.version_str,
                                           include_bits=True) + '.tar.gz'

    output_path = path_join(output_dir, out_filename)

    cmd = ['tar', 'zcvf', output_path, '-C', in_dir+'/', '.']
    _run_cmd(cmd)


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
            if not os.path.exists(d) or \
               os.stat(s).st_mtime - os.stat(d).st_mtime > 1:
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


def _run_cmd(cmd, get_stdout=False):
    if get_stdout:
        stdout_arg = subprocess.PIPE
    else:
        stdout_arg = None
    
    print(' '.join(cmd))
    po = subprocess.Popen(cmd, stdout=stdout_arg)
    po.wait()
    if po.returncode != 0:
        print("%s failed with returncode %d" % \
              (' '.join(cmd), po.returncode))
        sys.exit(1)
    return po.stdout
