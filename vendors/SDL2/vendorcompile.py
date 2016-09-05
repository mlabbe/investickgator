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

    sln_name = os.path.normpath("VisualC/SDL_VS2008.sln")
    builder.devenv_upgrade(sln_name)

    if builder.build_debug():
        config = 'Debug'
    else:
        config = 'Release'

    builder.devenv_build(sln_name, config, 'SDL2')
    builder.devenv_build(sln_name, config, 'SDL2main')

    if arch == vendor_build.arch_x64:
        arch_dir = 'x64'
    elif arch == vendor_build.arch_x86:
        arch_dir = 'win32'

    # install dll
    if xxxBIN != None:
        dll_path = path_join('VisualC', arch_dir, config, 'SDL2.dll')
        builder.install_file_in_bin_dir(os.path.normpath(dll_path), xxxBIN)

    # install header files and libary
    builder.copy_header_files('include', xxxROOT)

    lib_dir = path_join('VisualC', arch_dir, config)
    libsdl2_path     = path_join(lib_dir, 'SDL2.lib')
    libsdl2main_path = path_join(lib_dir, 'SDL2main.lib')
    builder.copy_lib_file(libsdl2_path, xxxROOT)
    builder.copy_lib_file(libsdl2main_path, xxxROOT)

    
def build_macos(libname, builder):
    # this code is not currently called, but is being left in so
    # universal binaries can be brought back if needed in the future.
    # currently, we only support macos x64
    supported_arch = [vendor_build.arch_x86, vendor_build.arch_x64]
    build_product_names = ['libSDL2-2.0.0.dylib', 'libSDL2.a']
    builder.verify_environment()
    builder.set_rootdir(path_join(xxxROOT, 'vendors', lib_name))

    # build
    for arch in supported_arch:
        builder.set_arch_environment( xxxROOT, arch, universal_working_dir=True )
        builder.configure( ['--disable-video-x11' ] ) 
        builder.make_command( 'clean' )
        builder.make()
        builder.make_command( 'install' )

    # combine
    if len( supported_arch ) > 1:
        builder.setup_universal_paths(xxxROOT)
        builder.lipo_create( xxxROOT, supported_arch, build_product_names )
        builder.symlink_to_universal(xxxROOT, build_product_names[0], 'libSDL2.dylib' )
        builder.copy_header_files('include', xxxROOT)
    

def build_linux_or_macos(lib_name, builder):
    builder.verify_environment()
    builder.set_rootdir(path_join(xxxROOT, 'vendors', lib_name))
    builder.set_arch_environment(xxxROOT)
    builder.verify_environment()
    builder.configure(install_to_temp=True)
    builder.make()
    builder.make_command('install')
    builder.copy_header_files('include/SDL2', xxxROOT, from_temp=True)
    builder.copy_lib_file('lib/libSDL2.a', xxxROOT, from_temp=True)
    builder.copy_lib_file('lib/libSDL2main.a', xxxROOT, from_temp=True)
        

if __name__ == '__main__':
    lib_name = 'SDL2'
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
