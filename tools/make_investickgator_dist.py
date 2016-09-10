#!/usr/bin/env python3

import sys
sys.path.append('./pylib')

import make_dist
from make_dist import Win32Icon, dist_cli, exe, read_version, build_all

if __name__ == '__main__':
    options = dist_cli(sys.argv)
    

    iv_def = make_dist.AppDefinition()
    iv_def.name = 'InveSTICKgator'
    iv_def.exe_name = exe('iv')
    iv_def.help_url = 'http://www.frogtoss.com'
    iv_def.version_str = read_version(options)
    iv_def.publisher_name = 'Frogtoss Games'

    if options['target_platform'] == 'win32':
        Win32Icon.add_std_icons(iv_def, options,
                                main_icon='{app}/investickgator.ico',
                                support_url_file='{app}/investickgator.url')
        
    db = build_all(iv_def, options)
    sys.exit(0)
        
