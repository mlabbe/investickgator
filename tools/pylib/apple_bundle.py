# -*- coding: utf-8 -*-

#
# Copyright (C) 2013-2016 Frogtoss Games, Inc.
#
# Usage rights granted under repo license
#

import os
import shutil

class AppleBundle:
    def __init__(self, app_name, exe_path, icon_path, version_str):
        """
        app_name: The user-visible name of the app.
        exe_path: The src path to the executable.
        icon_path: Location of .icns file.
        version_str: Version as a string, dot-separated integers
        """

        self.app_name = app_name
        self.exe_path = exe_path
        self.icon_path = icon_path

        app_name_nospaces = app_name[:]
        app_name_nospaces.replace(' ', '')
        
        exe_filename = os.path.basename(exe_path)

        self.info_plist = {
            'CFBundleDisplayName': app_name,
            'CFBundleExecutable': exe_filename,
            'CFBundleName': app_name,
            'CFBundleIdentifier': 'com.frogtoss.www.' + app_name_nospaces,
            'CFBundleVersion': version_str,
            'CFBundleShortVersionString': version_str,
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
                 
                
