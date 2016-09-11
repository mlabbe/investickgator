#!/usr/bin/env python3

# -*- coding: utf-8 -*-

#
# Copyright (C) 2016 Frogtoss Games, Inc.
#

"""Generate an .ico or .icns file from a directory of square pngs.
Pngs are downsized to fit (never scaled up), so the largest should be
1024x1024.

You can get away with one image or include more than one if you want
to hand-manage the visuals at various resolutions.
"""

import sys
import glob
import os.path
import tempfile
import argparse
import subprocess
from PIL import Image, ImageFont, ImageDraw
from os.path import join as path_join

RESAMPLE_FILTER = Image.LANCZOS

def do_args():
    parser = argparse.ArgumentParser(description="generate icons and icon art")
    parser.add_argument('-o', '--output-file',
                        action='store',
                        help='.icns file to create')
    parser.add_argument('-i', '--input-dir',
                        action='store',
                        help='directory of .pngs')
    
    parser.add_argument('-g', '--generate-icon',
                        action='store_true', default=False,
                        help='generate the icon')
    parser.add_argument('--gen-fg-color',
                        help='generated fg color; 4 values comma separated',
                        default='147,199,246,255')
    parser.add_argument('--gen-bg-color',
                        help='generated bg color; 4 values comma separated',
                        default='18,21,92,255')
    parser.add_argument('--gen-font',
                        help='path to ttf font to use when generating icon images')
    parser.add_argument('--gen-initials',
                        help='Two initials to put on the icon')

    args = parser.parse_args()
    if args.input_dir and not os.path.isdir(args.input_dir):
        parser.error("%s does not exist" % args.input_dir)

    if (not args.generate_icon and not args.input_dir) or \
       (args.generate_icon and args.input_dir):
        parser.error("either -g/--generate-icon or -i/--input-dir must be used")

    if args.generate_icon:
        if not os.path.exists(args.gen_font):
            parser.error('--gen-font %s not found' % args.gen_font)

        if not _color_from_string(args.gen_bg_color) or not _color_from_string(args.gen_fg_color):
            parser.error('invalid color.  example of valid color: "255,128,128,255"')
        
    return args

def _validate_square(im):
    if im.size[0] != im.size[1]:
        print("%s is not a square image (%dx%d)" % \
              (src_img, im.size[0], im.size[1]))
        sys.exit(1)
    

def map_src_images_to_sizes(img_dir, size_map, verbose):
    for src_img in glob.iglob(path_join(img_dir, '*.png')):
        print(src_img)
        im = Image.open(src_img)
        dim = im.size[0]

        _validate_square(im)

        for size in size_map:
            if size <= dim:
                if size_map[size] == None or size_map[size][0] > dim:
                    size_map[size] = (dim, src_img)
                    
    # print the size map
    if verbose:
        bad_size = False
        print("using the images as follows:")
        for size in sorted(size_map):
            print("\t%s: " % size, end='')
            if size_map[size] == None:
                print("no match :(")
                bad_size = True
            else:
                filename = os.path.basename(size_map[size][1])
                print("%s" % filename)
                
        if bad_size:
            print("sizes had no match, need larger source image.\n",
                  file=sys.stderr)
            sys.exit(1)

    return size_map

def generate_images(size_map, tmp_dir):
    for size in size_map:
        dim            = size_map[size][0]
        src_image_path = size_map[size][1]

        # save full size
        if size != 1024:
            im = Image.open(src_image_path)                
            if size != dim:
                im.thumbnail((size,size), RESAMPLE_FILTER)
            filename = "icon_%dx%d.png" % (size, size)
            out_path = path_join(tmp_dir, filename)
            print("saving " + filename)
            im = im.convert("RGBA")
            im.save(out_path, "png")
                

        # save @2x size
        if size == 16 or size == 128: continue
        im = Image.open(src_image_path)
        hsize = int(size/2)
        im.thumbnail((size,size), RESAMPLE_FILTER)            
        filename = "icon_%dx%d@2x.png" % (hsize, hsize)
        out_path = path_join(tmp_dir, filename)
        print("saving " + filename)
        im = im.convert("RGBA")
        im.save(out_path, "png")
        

    # edge case: save out 32x32@2x from 128x128 icon
    dim            = size_map[128][0]
    src_image_path = size_map[128][1]

    im = Image.open(src_image_path)
    if 64 != dim:
        im.thumbnail((64,64), RESAMPLE_FILTER)
    filename = "icon_32x32@2x.png"
    out_path = path_join(tmp_dir, filename)
    print("saving " + filename)
    im = im.convert("RGBA")
    im.save(out_path, "png")

def create_icns(in_dir, out_path):
    cmd = ['iconutil', '-c', 'icns', '-o', out_path, in_dir]
    print(' '.join(cmd))
    po = subprocess.Popen(cmd)
    po.wait()
    if po.returncode != 0:
        print("error running iconutil", file=sys.stderr)
        input("temp")
        sys.exit(1)

def create_ico(in_dir, size_map, out_path):
    # sadly, Pillow's .ico support doesn't support multiple src
    # images to produce a multi-size ico output file.
    # just take the largest one.
    CHOSEN_SZ = 256
    dim            = size_map[CHOSEN_SZ][0]
    src_image_path = size_map[CHOSEN_SZ][1]
    
    im = Image.open(src_image_path)
    _validate_square(im)
    if im.size[0] != CHOSEN_SZ:
        im.thumbnail((CHOSEN_SZ, CHOSEN_SZ), RESAMPLE_FILTER)

    # PIL has a bug wherein the max size is 255 instead of 256.
    # This creates a stride issue when viewing the image.
    # If set to 256, PIL just fails.
    # Workaround is to just not generate 256x256 icon.
    ico_sizes = []
    for size in size_map:
        if size == 256: continue
        ico_sizes.append((size,size))

    im.save(out_path, "ico", sizes=ico_sizes)
    
def action_build_icon(args):
    print("creating %s from %s" % (args.output_file, args.input_dir))
    output_file_ext = os.path.splitext(args.output_file)[1].lower()

    if output_file_ext == '.icns':
        # all image sizes are square
        # size_map is all sizes to tuple (pixels, img_path)
        size_map = {1024:None,
                    512:None,
                    256:None,
                    128:None,
                    32:None,
                    16:None}
        size_map = map_src_images_to_sizes(args.input_dir, size_map,
                                           verbose=True)
        with tempfile.TemporaryDirectory(suffix=".iconset") as tmp_dir:
            generate_images(size_map, tmp_dir)
            create_icns(tmp_dir, args.output_file)
            
    elif output_file_ext == '.ico':
        size_map = {256:None,
                    128:None,
                    64:None,
                    48:None,
                    32:None,
                    24:None,
                    16:None}
        size_map = map_src_images_to_sizes(args.input_dir, size_map,
                                           verbose=False)
        create_ico(args.input_dir, size_map, args.output_file)
    else:
        print("unknown extension " + output_file_ext, file=sys.stderr)
        sys.exit(1)
        
    print("wrote " + args.output_file)

def _color_from_string(s):
    l = (int(x) for x in s.split(','))
    t = tuple(l)
    if len(t) != 4:  return None
    return t
    
def action_generate_icon(args):
    DIMS = [(1024,1024), (32, 32)]

    fg_col = _color_from_string(args.gen_fg_color)
    bg_col = _color_from_string(args.gen_bg_color)
    msg = args.gen_initials

    for dims in DIMS:
        im_icon = Image.new('RGBA', dims, fg_col)
        
        font_height = dims[0]*0.625
        font = ImageFont.truetype(args.gen_font, int(dims[0]*0.625))
        
        dc = ImageDraw.Draw(im_icon)
        w,h = dc.textsize(msg, font=font)

        pos = ((dims[0]/2) - (w/2),
               (dims[1]/2) - (h/1.5))

        marg = int(dims[0]*0.0625)
        dc.rectangle([(marg,marg), (dims[0]-marg-1, dims[1]-marg-1)], fill=bg_col)
        dc.text(pos, msg, font=font, fill=fg_col)

        filename = '%s_%d.png' % (args.output_file, dims[0])
        im_icon.save(filename, "png")
        print("saved %s (%dx%d)" % (filename, dims[0], dims[1]))

    
if __name__ == '__main__':
    args = do_args()
    
    if args.input_dir:
        action_build_icon(args)
    elif args.generate_icon:
        action_generate_icon(args)
    
    sys.exit(0)
