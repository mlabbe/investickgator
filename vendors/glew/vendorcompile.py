import os
import sys

sys.path.append("../../tools/pylib")
import vendor_build
from vendor_build import BuildLib, BuildCLI
from os.path import join as path_join

xxxROOT = None
xxxBIN  = None

def build_windows(lib_name, builder):
    arch = builder.get_arch()
    builder.set_rootdir(path_join(xxxROOT, 'vendors', lib_name))

    sln_name = os.path.normpath("build/vc12/glew.sln")
    builder.devenv_upgrade(sln_name)

    if builder.build_debug():
        config = 'Debug'
        debug_ch = 'd'        
    else:
        config = 'Release'
        debug_ch = ''

    builder.devenv_build(sln_name, config, 'glew_static')

    if arch == vendor_build.arch_x64:
        arch_dir = 'x64'
    elif arch == vendor_build.arch_x86:
        arch_dir = 'Win32'

    # install header files and library
    builder.copy_header_files('include', xxxROOT)

    glew_filename = 'glew32s%s.lib' % debug_ch
    glew_path = path_join('lib', config, arch_dir, glew_filename)
    builder.copy_lib_file(glew_path, xxxROOT)

    
def build_linux_or_macos(lib_name, builder):
    builder.verify_environment()
    builder.set_rootdir(path_join(xxxROOT, 'vendors', lib_name))
    builder.set_arch_environment(xxxROOT)
    os.system("chmod +x ./config/config.guess")
    builder.make_command('clean')
    builder.make()
    builder.copy_header_files('include', xxxROOT)
    builder.copy_lib_file('lib/libGLEW.a', xxxROOT)

if __name__ == '__main__':
    lib_name = 'glew'
    cli = BuildCLI(sys.argv, lib_name)
    builder = BuildLib(cli)
    builder.verify_environment()

    xxxROOT = vendor_build.get_project_root_dir('IV')
    xxxBIN  = vendor_build.get_project_bin_dir('IV')
    
    try:
        if cli.get_target_platform() == 'Windows':
            build_windows(lib_name, builder)

        if cli.get_target_platform() == 'Darwin':
            build_linux_or_macos(lib_name, builder)            

        if cli.get_target_platform() == 'Linux':
            build_linux_or_macos(lib_name, builder)

    except vendor_build.BuildError as e:
        print("Failed building %s: %s" % (lib_name, e))
        sys.exit(1)

    print("Success.")
    sys.exit(0)
