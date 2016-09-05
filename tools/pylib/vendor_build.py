# -*- coding: utf-8 -*-

#
# Copyright (C) 2013-2016 Frogtoss Games, Inc.
#
# Usage rights granted under repo license
#

# This is a library that assists with cross platform building.
# Do not run it directly.

import os
import sys
import shutil
import tempfile
import platform
import optparse
import subprocess

from os.path import join as path_join

globals = {'default_parallel_jobs': 4,
           'print_shell_cmd':       True,
           'execute_shell_cmd':     True,
           'use_ccache':            False,  # set to True with --use-ccache
           'force_clang':           False,  # set to True with --force-clang
           'supported_platforms':   ['Linux', 'Darwin', 'Windows', 'Android', 'Pi'] }


# Platform-independent way of specifying architecture
(arch_x86, arch_x64, arch_armv7a) = list(range(0,3))

ndk_debug_build_args = ['V=1', '-B', 'NDK_DEBUG=1']

def get_project_root_dir(project_prefix):
    """Resolve the project root dir.  First, look in the environment variable <project_prefix>ROOT.
    Failing that, verify that we are in '../vendors', and then set it to the absolute
    path value for '../../'"""
    lookup_var = '%sROOT' % project_prefix
    if lookup_var in os.environ:
        return os.environ[lookup_var]
    
    up_path = os.path.abspath(path_join(os.getcwd(), '..'))
    if os.path.split(up_path)[-1].lower() == 'vendors':
        return os.path.abspath(path_join(os.getcwd(), '..', '..'))
    else:
        raise BuildError("Project root dir not found.  Set %s to the project root." % lookup_var)

def get_project_bin_dir(project_prefix):
    """Resolve the project bin dir by looking in <project_prefix>BIN, or looking for a single _dist
    directory right underneath the code root dir."""
    lookup_var = '%sBIN' % project_prefix
    if lookup_var in os.environ:
        bin_dir = os.environ[lookup_var]
        print("Project bin dir: %s" % os.path.abspath(bin_dir))
        return os.environ[lookup_var]

    print("No project bin dir in env var %s" % lookup_var)

    # search for path sibling to the code root
    code_root = get_project_root_dir(project_prefix)
    code_root_up = os.path.abspath(path_join(code_root, '..'))
    sibling_paths = os.listdir(code_root_up)

    dist_count = 0
    sibling_path_name = ''
    for sibling_path in sibling_paths:
        if sibling_path.endswith('_dist'):
            dist_count += 1
            sibling_path_name = sibling_path
    
    return os.path.abspath(path_join(code_root_up, sibling_path_name))

def _which(program):
    import os
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None

def copyintotree(src, dst, symlinks=False, ignore=None):
    """Copy files in src into possibly existing directly dst"""
    if not os.path.exists(dst):
        os.makedirs(dst)
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            copyintotree(s, d, symlinks, ignore)
        else:
            if not os.path.exists(d) or os.stat(s).st_mtime - os.stat(d).st_mtime > 1:
                shutil.copy2(s, d)


def get_compiler( target_platform, use_cpp=False  ):
    ccache_str = ''
    if globals['use_ccache']:
        ccache_str = '/usr/bin/ccache '


    if target_platform == 'Darwin':
        if use_cpp:
            return ccache_str + '/usr/bin/clang++' 
        else:
            return ccache_str + '/usr/bin/clang' 

    elif target_platform == 'Linux':
        if globals['force_clang']:
            if use_cpp:
                return ccache_str + '/usr/bin/clang++'
            else:
                return ccache_str + '/usr/bin/clang'
        else:
            if use_cpp:
                return ccache_str + '/usr/bin/g++'
            else:
                return ccache_str + '/usr/bin/gcc -g -fno-omit-frame-pointer -O0 '

    elif target_platform == 'Windows':
        return 'devenv.com'

    elif target_platform == 'Android':
        return '' # ndk-build wraps this; unnecessary

    elif target_platform == 'Pi':
        if use_cpp:
            return os.environ['SYSROOT'] + '/arm-bcm2708/gcc-linaro-arm-linux-gnueabihf-raspbian/bin/arm-linux-gnueabihf-g++'
        else:
            return os.environ['SYSROOT'] + '/arm-bcm2708/gcc-linaro-arm-linux-gnueabihf-raspbian/bin/arm-linux-gnueabihf-gcc'

    return None

def build_args_from_supported_features( features ):
    """Build a list of --enable or --disable features from a dictionary.
    Ex: --enable-music-wave would be the result of {'music-wave': True}"""
    args = []
    for feature in features:
        if features[feature]:
            args.append( '--enable-' + feature )
        else:
            args.append( '--disable-' + feature )

    return args

        
def _get_compiler_archstring_from_arch( arch, target_platform ):    
    """Return compiler-specific architecture flag for an architecture."""
    if target_platform == 'Darwin':
        if arch == arch_x86:
            return 'i386'
        elif arch == arch_x64:
            return 'x86_64'
        else:
            raise BuildError("Invalid architecture for " + target_platform)

    if target_platform == 'Linux':
        if arch == arch_x86:
            return '32'
        elif arch == arch_x64:
            return '64'
        else:
            raise BuildError("Invalid architecture for " + target_platform)

    if target_platform == 'Pi':
        return 'armv7a'
    

def _get_standardized_archstring_from_arch( arch ):
    """Return the same archstring for the architecture, regardless of platform idiosyncrasies."""
    if arch == arch_x86:
        return 'x86'
    elif arch == arch_x64:
        return 'x64'
    elif arch == arch_armv7a:
        return 'armv7a'
    else:
        raise BuildError("Invalid architecture.")
    
def _get_standardized_platform_name(platform):
    """Return the native project standards platform name for the target platform string"""
    if platform.lower() == 'darwin' or platform.lower() == 'macosx':
        return 'macos'

    if platform.lower()[:3] == 'win':
        return 'win32' # true even for 64-bit builds

    if platform.lower()[:3] == 'lin':
        return 'linux'

def get_output_dir( code_root, arch, universal_working_dir ):
    """Get the lib install dir.  This works with a specific architecture,
    even on OS X.
    
    See globals['universal_dir'] for the ultimate output directory on
    universal binary installs.

    universal_working_dir: On universal binary OSes, return a temporary directory 
    that is used to hold binaries for a single architecture, prior to being combined.
    """

    base = code_root + '/vendors/out'
    if universal_working_dir:
        base = os.path.abspath('./out')

    return base + '.%s' % _get_standardized_archstring_from_arch( arch )



def decorate_cmd_with_setarch( cmd, arch ):
    """Take cmd, a list of arguments, and prefix it with "setarch <ta>", where
    <ta> is the target architecture."""
    prefix = []

    if arch == arch_x86:
        prefix = ['setarch', 'i386']
        return prefix + cmd

    if arch == arch_x64:
        prefix = ['setarch', 'x86_64']
        return prefix + cmd

    return cmd


class BuildError(Exception):
    def __init__( self, message ):
        self.message = message

    def __str__( self ):
        return repr(self.message)


class BuildCLI:
    """A BuildCLI queries the user for command line options. 
    The result is passed to a BuildLib object to dictate its behavior."""
    def __init__( self, argv, libname ):
        self.argv = argv
        self.libname = libname

        supported_platforms = ', '.join( globals['supported_platforms'] )
        
        parser = optparse.OptionParser()
        parser.add_option( '-a', '--action', dest='action',
                           help='action (default is build)' )
        parser.add_option( '-p', '--platform', dest='platform',
                           help='platform (default is current) [%s]' % supported_platforms )
        parser.add_option( '-A', '--arch', dest='arch',
                           help='architecture [x86, x64] (default is x64) Ignored if -p Android, Pi',
                           default='x64' )
        parser.add_option( '-c', '--clean-first', dest='clean',
                           action="store_true", default=False,
                           help='clean before building (default no)' )
        parser.add_option( '-C', '--use-ccache', dest='ccache',
                           action="store_true", default=False,
                           help='use ccache to build where possible' )
        parser.add_option( '-f', '--force-clang', dest='force_clang',
                           action="store_true", default=False,
                           help='force Clang for Linux target' )
        parser.add_option( '-d', '--debug', default=False,
                           help='build vendor in debug mode (if available)')


        (self.options, self.args) = parser.parse_args()

        # Validate
        #if parser.has_option('-p') and not self.options.platform in globals['supported_platforms']:
        if not self.get_target_platform() in globals['supported_platforms']:
            print("Invalid --platform: %s.  Valid choices are:" % self.options.platform)
            for platform in globals['supported_platforms']:
                print("\t%s" % platform)
            sys.exit(1)

        # Set global 
        if self.options.ccache:
            globals['use_ccache'] = True

        # Set global
        if self.options.force_clang:
            globals['force_clang'] = True


    def get_target_platform( self ):
        if self.options.platform == None:
            return platform.system()
        return self.options.platform

    def get_target_architecture( self ):
        if self.options.platform == 'Pi':
            return arch_armv7a

        if self.options.arch == None:
            return arch_x64
        else:
            if self.options.arch == 'x86':
                return arch_x86
            elif self.options.arch == 'x64':
                return arch_x64

        raise BuildError("Invalid architecture: " + self.options.arch )




class BuildLib:
    def __init__( self, buildCLI ):
        """buildCLI = a BuildCli() instantiated object; will contain all of the command line
        arguments passed in which modifies behavior."""
        self._cli = buildCLI
        os.environ['CC'] = self._take_from_environment( 'CC', get_compiler( self._cli.get_target_platform()  ) )
        os.environ['CXX'] = self._take_from_environment( 'CXX', get_compiler( self._cli.get_target_platform(), use_cpp=True ) )
        self._rootdir = None
        self._tmpdir = None
        self._outdir = ""

    def verify_environment( self, expectedVars=() ):
        """Raise BuildError if environment variables are not set."""
        #expectedVars = ('FROGLIBS', 'ORION_BUILD_TARGET')
        for env in expectedVars:
            if env not in os.environ:
                raise BuildError('required environment variable ' + env + ' not found')

        if self._cli.get_target_platform() == 'Android':
            if not _which( 'ndk-build' ):
                raise BuildError('ndk-build not in PATH')

        # if this is the only file in the script's dir, there is nothing to build.
        exec_dir = os.path.dirname(os.path.realpath(sys.argv[0]))
        if len(os.listdir(exec_dir)) == 1:
            raise BuildError("empty build directory. nothing to build.")
        

    def get_arch( self ):
        """Get the architecture.  Will be in the form buildhelp.arch_x86"""
        return self._cli.get_target_architecture()



    def set_arch_environment( self, code_root,
                              arch=None, universal_working_dir=False, use_cpp=False ):
        """Sets the CC environment variable so linker and compiler steps include the architecture.

        code_root: path to the repo root.

        pass in one of the vendor_help.arch_* flags or None to take it from the
        CLI. (Recommended for consistency for non-fat binary builds).

        On Windows, this is ignored as Visual Studio specifies its arch
        another way.

        Sets the output directory for the named build
        
        use_cpp optionally uses a C++ compiler and environment variables"""

        if arch == None:
            arch = self._cli.get_target_architecture()

        # OS X
        if self._cli.get_target_platform() == 'Darwin':

            arch_arg = _get_compiler_archstring_from_arch( arch, self._cli.get_target_platform() )

            universal_dir = path_join(code_root, 'vendors', 'lib')
            os.environ['LDFLAGS'] = '-L%s' % universal_dir
            
            # C
            if not use_cpp:
                os.environ['CC'] = get_compiler( self._cli.get_target_platform() ) + ' -arch ' + arch_arg + ' '
                os.environ['CFLAGS'] = "-I%s/include" % (universal_dir) + ' '

                
                print("tmpdebug: CC:%s\nCFLAGS:%s\n" % (os.environ['CC'], os.environ['CFLAGS']))
                # disable to follow updates in Xcode -ml
                #os.environ['CFLAGS'] += " -Wunused-command-line-argument-hard-error-in-future"

            # C++
            else:
                os.environ['CC'] = get_compiler( self._cli.get_target_platform() ) + ' -arch ' + arch_arg                
                os.environ['CXX'] = "%s -arch %s" % ( get_compiler( self._cli.get_target_platform(), use_cpp=True ), arch_arg )
                os.environ['CXXFLAGS'] = "-I%s/include" % universal_dir

            self._outdir = get_output_dir( code_root, arch, universal_working_dir  )


        # Linux
        elif self._cli.get_target_platform() == 'Linux':            

            arch_arg = _get_compiler_archstring_from_arch( arch, self._cli.get_target_platform() )

            out_root = path_join(code_root, 'vendors')

            os.environ['CC'] = get_compiler( self._cli.get_target_platform() ) + ' -m' + arch_arg
            os.environ['CXX'] = get_compiler( self._cli.get_target_platform(), use_cpp ) + ' -m' + arch_arg
            os.environ['LD'] = get_compiler( self._cli.get_target_platform() ) + ' -m' + arch_arg
            os.environ['CFLAGS'] = "-I%s/include" % ( out_root )
            os.environ['LDFLAGS'] = "-L%s/lib" % ( out_root )

        # Android
        elif self._cli.get_target_platform() == 'Android':
            
            os.environ['TARGETLIB'] = self._cli.libname.lower()
            os.environ['NDK_PROJECT_PATH'] = os.environ['FROGLIBS'] + '/src/android'


        elif self._cli.get_target_platform() == 'Pi':
            sysroot = os.environ['SYSROOT']
            compiler_args =  "--sysroot=%s " % sysroot
            compiler_args += "-I%s/opt/vc/include " % sysroot
            compiler_args += "-I%s/usr/include " % sysroot
            compiler_args += "-I%s/opt/vc/include/interface/vcos/pthreads " % sysroot
            compiler_args += "-I%s/opt/vc/include/interface/vmcs_host/linux" % sysroot
            
            os.environ['CC'] = get_compiler( self._cli.get_target_platform() ) + ' %s' % compiler_args
            os.environ['CXX'] = get_compiler( self._cli.get_target_platform(), use_cpp ) + ' %s' % compiler_args
            os.environ['LDFLAGS'] = "-L%s/opt/vc/lib -L%s/lib" % (sysroot, self._outdir)
            os.environ['CFLAGS'] = "-I%s/include" % ( self._outdir )

            self._outdir = get_output_dir( code_root, arch, False )

        # Other
        else:
            raise BuildError("No environment to set for this platform.")



    def set_rootdir( self, rootdir ):
        """Set the root directory for all operations."""
        self._rootdir = rootdir
        os.chdir( self._rootdir )



    def shell( self, step, check_errorlevel=True ):
        """Run a shell command as a build step."""
        self._print_shell_cmd( step )

        if not globals['execute_shell_cmd']:
            return
        try:
            returncode = subprocess.check_call( ' '.join(step),
                                                shell=True )
        except subprocess.CalledProcessError as e:
            if check_errorlevel:
                raise BuildError( 'run_step("%s") returned %i' % (' '.join(step), e.returncode) )


    def configure( self, more_args=None, install_to_temp=False, \
                   universal_working_dir=False ):
        """Run a configure step.
        more_args is a list of args to append.

        setarch is run on Linux, which sets the architecture to the target arch settings in the
        build environment.

        install_to_temp makes subsequent make install install to a temp dir
        """

        cmd = ['sh', 'configure']
        if self._cli.get_target_platform() == 'Linux':
            cmd = decorate_cmd_with_setarch( cmd, self.get_arch() )

        if install_to_temp:
            self._tmpdir = tempfile.TemporaryDirectory(suffix="vendor_build")
            cmd.append( '--prefix=%s' % (self._tmpdir.name) )
        elif len(self._outdir):
            cmd.append('--prefix=%s' % (self._outdir))

        if more_args != None:
            cmd.extend( more_args )

        self.shell( cmd, check_errorlevel=True )

            
    def make( self, jobs=globals['default_parallel_jobs'] ):
        cmd = ['make', '-j'+str(jobs) ]
        
        print(os.environ['CC'])
        self.shell( cmd, check_errorlevel=True)


    def make_command( self, command, check_errorlevel=True ):
        """Run a command such as make install."""
        cmd = []
        if isinstance( command, str ):
            cmd = ['make', command]
        elif isinstance( command, list ):
            cmd = ['make'] + command

        self.shell( cmd, check_errorlevel=check_errorlevel )

    def make_optional_clean( self, check_errorlevel=True ):
        """Runs make clean if the user specified to clean
        before building from the command line."""
        if not self._cli.options.clean:
            return

        cmd = ['make', 'clean']
        self.shell( cmd, check_errorlevel )


    def nmake_build( self, makefile_path, check_errorlevel=True ):
        cmd = ['nmake', '/f', makefile_path ]
        self.shell( cmd, check_errorlevel=check_errorlevel )


    def nmake_command( self, makefile_path, command, check_errorlevel=True ):
        cmd = ['nmake', '/f', makefile_path, command]
        self.shell( cmd, check_errorlevel=check_errorlevel )


    def nmake_optional_clean( self, makefile_path, check_errorlevel=True ):
        """runs nmake makefile.mak /Clean if the user specified
        to clean before building from the command line."""
        if not self._cli.options.clean:
            return

        cmd = ['nmake', '/f', makefile_path, 'Clean']
        self.shell( cmd, check_errorlevel )


    def setup_universal_paths( self, code_root, subdirs=['lib','include'] ):
        """subdirs is a list of directories to create under universal."""
        universal_dir = self._get_universal_dir(code_root)

        for dir in subdirs:
            self.mkdir( "%s/%s" % (universal_dir, dir) )


    def lipo_create( self, code_root, archs, build_products, libdir='lib' ):
        """for directories out.$archs/$libdir, create a lipo binary for each of build_products.
        ex: out.x86_64/lib/foo.dylib and out.i386/lib/foo.dylib go to
            out.universal/lib/foo.dylib"""

        for product in build_products:
            src_lib_paths = []
            for arch in archs:
                src_lib_paths.append( "%s/%s/%s" % ( get_output_dir( code_root, arch, True ), libdir, product ) )

            cmd = ['lipo', '-create']
            cmd.extend( src_lib_paths )

            cmd.append( '-output' )
            
            universal_dir = self._get_universal_dir(code_root)
            cmd.append( '%s/%s/%s' % (universal_dir, libdir, product ) )
            
            self.shell( cmd, check_errorlevel=True )

    def _get_universal_dir(self, code_root):
        return path_join(code_root, 'vendors')

    def symlink_to_universal( self, code_root, long_lib_name, symlink_name, libdir='lib' ):
        """symlink long lib names (ex: libpng.15.15.dylib => libpng.dylib.
        This is done automatically in make install, but the lipo to universal step avoids that."""

        # Ensure the symlink is a relative path
        src = long_lib_name
        dst = '%s/%s/%s' % ( self._get_universal_dir(code_root), libdir, symlink_name )
        self._print_shell_cmd( ['os.symlink(', src, dst, ')'] )

        if not globals['execute_shell_cmd']:
            return

        if os.path.exists( dst ):
            os.unlink( dst )

        os.symlink( src, dst )


    def copy_build_products_subdir( self, code_root, source_arch, subdirs ):
        """Copy a build products subdir verbatim.  Useful for include, man, etc. in a 
        fat binary situation.  
        subdirs is a list. ex: ['bin', 'man']
        source_build_dir is one of the non-universal builds, ex: out.x86. 
        
        This is intended to be used to copy directories which are the same when
        built on every platform.
        """
        # todo: is_fat_binary()
        # build products subdirs on fat binary platforms 
        # automatically search for files in a different location -- the universal working dir
        universal_working_dir = self._is_target_platform_fat_binary()

        for subdir in subdirs:
            src_path = "%s/%s" % (get_output_dir(code_root, source_arch, \
                                                 universal_working_dir), subdir)
            dst_path = "%s/%s" % (self._get_universal_dir(code_root), subdir)
        
            self.mkdir( dst_path )

            args = '-r'
            if globals['print_shell_cmd']:
                args = '-rv'
            self.shell( ["cp", args, src_path, self._get_universal_dir(code_root)] )



    def replace_string_in_file( self, code_root, path_in_universal, old, new ):
        """replace a string in a file.  useful for rewriting lib-config scripts to point
        to the universal directory."""
        cmd = ['sed', '-i', '.untouched', '-e', 
               '"s/%s/%s/"' % ( old, new ),
               '"%s/%s"' % ( self._get_universal_dir(code_root), path_in_universal )]
        self.shell( cmd )

    def devenv_clean( self, 
                      sln_name, 
                      configuration, 
                      include_arch_in_configuration=True ):
        """Clean a project before building.  This is ran regardless of
        the cli options."""
        target_arch = self._cli.get_target_architecture()

        platform = ''
        if include_arch_in_configuration:
            if target_arch == arch_x86:
                platform = '|x86'
            elif target_arch == arch_x64:
                platform = '|x64'


        cmd = ['devenv.com',
               sln_name,
               '/Clean',
               '"%s%s"' % ( configuration, platform ) ]
        self.shell( cmd )


    def devenv_upgrade( self,
                        sln_name ):
        """Upgrade a .sln to the target version of visual studio"""
        cmd = ['devenv.com', sln_name, '/Upgrade']
        self.shell( cmd)


    def devenv_build( self, sln_name, configuration, project=None, 
                      include_arch_in_configuration=True, ignore_clean=False ):
        """Run Visual Studio devenv.com.

        sln_name: name of the .sln file
        
        configuration: A string that corresponds to a configuration type 
        in the sln.  'Debug' or 'Release', typcially.

        project: if not None, then a specific project to vcproj to build

        include_arch_in_configuration: Many Visual Studio projects add
        the architecture (ex: '|x64') to to the configuration to
        resolve ambiguous architectures.  Passing false avoids adding
        this inside devenv_build().

        If ignore_clean is set, don't clean the build even if -c is passed
        on the command line.  This is useful if the caller is building
        multiple projects in a solution and you don't want to clean after
        the first one.
        """

        target_arch = self._cli.get_target_architecture()

        platform = ''
        if include_arch_in_configuration:
            if target_arch == arch_x86:
                platform = '|Win32'
            elif target_arch == arch_x64:
                platform = '|x64'

        cmd = ['devenv.com', 
               sln_name,
               '/Build',
               '"%s%s"' % ( configuration, platform ) ]

        if project != None:
            cmd.extend( ['/project', project] )

        if self._cli.options.clean and not ignore_clean:
            clean_cmd = ['devenv.com',
                         sln_name]
            if project != None:
                clean_cmd.extend( ['/project', project] )
            clean_cmd.extend( ['/Clean'] )

            # clean a specific project
            clean_cmd.append( '"%s%s"' % ( configuration, platform ) ) 
            self.shell( clean_cmd )            

        self.shell( cmd )


    def install_file_in_bin_dir( self, src_path, bin_root ):
        """install a file in the arch and platform-specific bin dir.

        Used to copy compiled lib DLLs to PROJBIN/bin/win32_x86, for instance.
        """
        target_plat = self._cli.get_target_platform()        
        plat_str = _get_standardized_platform_name( target_plat )
        
        target_arch = self._cli.get_target_architecture()
        arch_str = _get_standardized_archstring_from_arch( target_arch )

        plat_arch = '%s_%s' % (plat_str, arch_str)
        
        dst_dir = path_join(bin_root, 'bin', plat_arch)
        dst_path = path_join(dst_dir, os.path.basename(src_path))

        self._print_shell_cmd( ['shutil.copyfile(', src_path, ', ', dst_path, ')'] )
        if not globals['execute_shell_cmd']:
            return

        self.mkdir(bin_root)
        self.mkdir(path_join(bin_root, 'bin'))
        self.mkdir(path_join(bin_root, 'bin', plat_arch))
        shutil.copyfile(src_path, dst_path)

        
    def copy_header_files(self, src_dir, dst_root, from_temp=False):
        """Copy library header files to dst_root/vendors/include.  Useful for platforms
        that do not have make install.

        from_temp: src_dir is located under the temp dir.  See configure's install_to_temp arg.
        """
        dst_path = path_join(dst_root, 'vendors', 'include')

        if from_temp:
            src_dir = path_join(self._tmpdir.name, src_dir)

        self._print_shell_cmd( ['shutil.copytree(', src_dir, ', ', dst_path, ')'] )
        if not globals['execute_shell_cmd']:
            return
        
        self.mkdir(dst_path)
        copyintotree(src_dir, dst_path)


    def copy_lib_file(self, lib_path, dst_root, from_temp=False):
        """Copy file to <dst_root>/vendors/lib/<target_arch>.  Used to create a directory
        of vendor libraries you can link to.

        from_temp means lib_path is relative to the temp path passed
        in to configure with install_to_temp=True.
        """
        target_arch = self._cli.get_target_architecture()
        arch_str = _get_standardized_archstring_from_arch( target_arch )

        if from_temp:
            lib_path = path_join(self._tmpdir.name, lib_path)
        
        dst_dir = path_join(dst_root, 'vendors', 'lib', arch_str)
        self._print_shell_cmd( ['shutil.copy(', lib_path, ', ', dst_dir, ')'] )
        if not globals['execute_shell_cmd']:
            return

        self.mkdir(path_join(dst_root, 'vendors', 'lib'))
        self.mkdir(path_join(dst_root, 'vendors', 'lib', arch_str))
        shutil.copy(lib_path, dst_dir)
                   


    def confirm_binary( self, binary ):
        """Runs "which binary" on the shell, confirming that the binary
        exists.  Throws BuildError if not."""
        try:
            output = subprocess.check_output( 'which ' + binary,
                                              shell=True )
        except subprocess.CalledProcessError:
            raise BuildError("%s binary not found in PATH." % binary )

    
    def ndk_optional_clean( self, check_errorlevel=True ):
        """Runs ndk-build clean if the user specified to clean 
        before building from the command line."""
        if not self._cli.options.clean:
            return

        # workaround: if APP_STL is set to an stlport variant,
        # ndk-build clean fails.  Forcing it to APP_STL (see the -e arg)
        # avoids this.
        os.environ['APP_STL'] = 'system'
        cmd = ['ndk-build', '-e', 'clean']

        self.shell( cmd, check_errorlevel )



    def ndk_build( self, args=[] ):
        """Run ndk-build, optionally accepting args.  
        Pass in buildhelp.ndk_debug_build_args to force full rebuilds and expose build commands."""
        cmd = ['ndk-build'] + args
        self.shell( cmd, check_errorlevel=True )


    def ndk_set_alt_toolchain( self, toolchain ):
        """Sets the NDK toolchain to one of a number of alternate values.  See
        NDK_TOOLCHAIN_VERSION in the Android docs, section
        Application.mk."""
        os.environ['NDK_TOOLCHAIN_VERSION'] = toolchain


    def copyfile( self, src, dst ):
        """Copy a file from src to dst using shutil.copyfile()"""
        self._print_shell_cmd( ["shutil.copyfile( \"%s\", \"%s\" )" % (src,dst)] )

        if not globals['execute_shell_cmd']:
            return 

        shutil.copyfile( src, dst )


    def _is_target_platform_fat_binary( self ):
        return self._cli.get_target_platform() == 'Darwin'

    
    def _take_from_environment( self, key, fallback ):
        if key in os.environ:
            return key
        return fallback


    def _print_shell_cmd( self, shellcmd ):
        if globals['print_shell_cmd']:
            print(' '.join( shellcmd ))

    def mkdir( self, path ):
        self._print_shell_cmd( ['os.mkdir(', path, ')'] )

        if not globals['execute_shell_cmd']:
            return

        try:
            os.mkdir( path )
        except OSError: # already exists
            pass

    def build_debug( self ):
        return self._cli.options.debug



class AppleBundle:
    def __init__(self, app_name, exe_path, icon_path, version_tuple=('1','0','0')):

        self.app_name = app_name
        self.exe_path = exe_path
        self.icon_path = icon_path

        app_name_nospaces = app_name[:]
        app_name_nospaces.replace(' ', '')
        
        exe_filename = os.path.basename(exe_path)

        version_string = '.'.join(version_tuple)

        self.info_plist = {
            'CFBundleDisplayName': app_name,
            'CFBundleExecutable': exe_filename,
            'CFBundleName': app_name,
            'CFBundleIdentifier': 'com.frogtoss.www.' + app_name_nospaces,
            'CFBundleVersion': version_string,
            'CFBundleShortVersionString': version_string,
            'CFBundleSignature': 'FROG',
            'CFBundleIconFile': os.path.basename(icon_path),

            # having this makes the app display properly on retina screens(huh?)
            'NSPrincipalClass': app_name, 
        }

        
    def write(self, out_root, rm_existing_root=False):
        if rm_existing_root and os.path.isdir(out_root):
            shutil.rmtree(out_root, ignore_errors=True)
        
        os.makedirs(out_root, exist_ok=True)

        app_root = os.path.join(out_root, '%s.app' % self.app_name)
        contents = os.path.join(app_root, 'Contents')
        macos    = os.path.join(contents, 'MacOS')
        resources= os.path.join(contents, 'Resources')

        os.mkdir(app_root)
        os.mkdir(contents)
        os.mkdir(macos)
        os.mkdir(resources)
        shutil.copy(self.exe_path, macos)
        shutil.copy(self.icon_path, resources)

        f = open(os.path.join(contents, 'Info.plist'), "wt", encoding='utf-8')
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n')
        f.write('<plist version="1.0">\n')
        f.write('\t<dict>\n')

        for key, value in self.info_plist.items():
            f.write('\t\t<key>%s</key>\n' % key)
            f.write('\t\t<string>%s</string>\n' % value)

        f.write('\t</dict>\n')
        f.write('</plist>\n')
        f.close()
                 
                
