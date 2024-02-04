# Copyright (c) 2024, Patricio Gonzalez Vivo
#
# Licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International Public License (the "License"). 
# You may not use this file except in compliance with the License. You may obtain a copy of the License at https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode
#

import os
import numpy as np
import argparse

from bands.common.io import get_image_size, get_video_data
from bands.common.meta import create_metadata, is_video, add_band, write_metadata, set_default_band, get_record3d_data, load_metadata

import warnings
warnings.filterwarnings("ignore")

# Default BANDS & MODELS
DEPTH_VIDEO_DEFAULT = "depth_anything"
DEPTH_IMAGE_DEFAULT = "depth_patchfusion"
DEPTH_BANDS = ["depth_midas", "depth_marigold", "depth_zoedepth", "depth_patchfusion", "depth_anything"]
DEPTH_OPTIONS = DEPTH_BANDS + ["all"]

FLOW_DEFAULT = "flow_gmflow"
FLOW_BANDS = ["flow_gmflow", "flow_raft"]
FLOW_OPTIONS = FLOW_BANDS + ["all"]

MASK_DEFAULT = "mask_mmdet"
MASK_BANDS = ["mask_mmdet"]
MASK_OPTIONS = MASK_BANDS + ["all"]

# Subfolders
SUBFOLDERS = {
    "rgba": "images",
    "mask_mmdet": "mask",
    "flow_raft": "flow_raft",
    "flow_gmflow": "flow_gmflow",
    "depth_zoedepth": "depth_zoedepth",
    "depth_midas": "depth_midas",
    "depth_marigold": "depth_marigold",
    "depth_patchfusion": "depth_patchfusion",
    "depth_anything": "depth_anything",
    "camera_colmap": "sparse"
}

# Extra args
EXTRA_ARGS = {
    "rgba": "",
    "mask_mmdet": "--sdf ",
    "depth_midas": " ",
    "depth_marigold": "",
    "depth_zoedepth": "",
    "depth_patchfusion": "",
    "depth_anything": "--metric outdoor ",
    "flow_raft": "",
    "flow_gmflow": ""
}


# Run band model
def run(band, input_folder, output_file="", subpath=False, extra_args = ""):
    print("\n# ", band.upper())
    cmd = "python3 bands/" + band + ".py -i " + input_folder
    if output_file != "":
        cmd += " --output " + output_file

    if extra_args != "":
        cmd += " " + extra_args

    if subpath:
        cmd += " --subpath " + SUBFOLDERS[band] + " "

    print(cmd,"\n")
    os.system(cmd)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', '-i', help="input file", type=str, required=True)
    parser.add_argument('--output', help="folder name", type=str, default='')
    parser.add_argument('--record3d', help="Record3D video", action='store_true')

    # global video properties
    parser.add_argument('--fps', '-r', help='fix framerate', type=float, default=24)
    parser.add_argument('--extra', '-e', help='Save extra data [>0 frames|PLYs; >1 FLOs; >2 NPY]', type=int, default=0)

    # Depth
    parser.add_argument('--rgbd', help='Where the depth is', type=str, default=None)
    parser.add_argument('--depth', '-d', help='Depth bands', type=str, default=None, choices=DEPTH_OPTIONS)
    parser.add_argument('--ply', '-p', help='Save ply for images', action='store_true')
    parser.add_argument('--npy', '-n', help='Save npy version of files', action='store_true')

    # Flow
    parser.add_argument('--flow', '-f', help='Flow bands', type=str, default=None, choices=FLOW_OPTIONS)
    parser.add_argument('--flo', help='Save flo files for raft', action='store_true')
    parser.add_argument('--flow_backwards', '-b',  help="Save backwards video", action='store_true')
    parser.add_argument('--flow_mask', '-m',  help="Save mask of videos", action='store_true')


    args = parser.parse_args()

    # 1. Get input basic parameters
    input_path = args.input
    input_folder = os.path.dirname(input_path)
    input_filename = os.path.basename(input_path)
    input_basename = input_filename.rsplit( ".", 1 )[ 0 ]
    input_extension = input_filename.rsplit( ".", 1 )[ 1 ]
        
    # 2. Create folder
    folder_name = os.path.join(input_folder, input_basename)
    if args.output:
        folder_name = args.output

    data = create_metadata(folder_name)

    if is_video(input_path):
        extension = "mp4"
    else:
        extension = "png"

    name_rgba = "rgba." + extension
    path_rgba = os.path.join(folder_name, name_rgba)
    extra_rgba_args = EXTRA_ARGS["rgba"]
    # 
    if args.record3d:
        args.rgbd = "right"
        name_depth = "depth." + extension

        if is_video(input_path):
            _,  height, _, _ = get_video_data(args.input)
        else:
            _, height = get_image_size(args.input)

        record3d_info = get_record3d_data(args.input)
        print(record3d_info)

        camera = record3d_info["intrinsicMatrix"]
        fx = camera[0]
        fy = camera[4]
        cx = camera[6]
        cy = camera[7]

        depth_range = record3d_info["rangeOfEncodedDepth"]
        
        data["focal_length"] = max(fx, fy)
        data["principal_point"] = [cx, cy]
        data["field_of_view"] = 2 * np.arctan(0.5 * height / data["focal_length"]) * 180 / np.pi

        extra_rgba_args += "--encoding_depth hue "

        add_band(data, "depth", url=name_depth)
        data["bands"]["depth"]["values"] = {
                "min": {
                    "type": "float",
                    "value": depth_range[0]
                },
                "max": {
                    "type": "float",
                    "value": depth_range[1]
                }
            }
    
    # 3. Extract RGBA (only if doesn't exist)
    add_band(data, "rgba", url=name_rgba)

    if args.rgbd:
        extra_rgba_args += "--rgbd " + args.rgbd

    if is_video(input_path):
        extra_rgba_args += " --fps " + str(args.fps)

    write_metadata(folder_name, data)
    run("rgba", input_path, path_rgba, subpath=True, extra_args=extra_rgba_args)
    data = load_metadata(folder_name)

    # 4. Add metadata
    if is_video(input_path):
        data["width"],  data["height"], data["fps"], data["frames"] = get_video_data(path_rgba)
        data["duration"] = float(data["frames"]) / float(data["fps"])

    else:
        data["width"], data["height"] = get_image_size(path_rgba)

    # Attempt to reconstruct camera intrinsics 
    if "principal_point" not in data:
        data["principal_point"] = [float(data["width"] / 2), float(data["height"] / 2)]
    if "focal_length" not in data:
        data["focal_length"] = float(data["height"] * data["width"]) ** 0.5
    if "field_of_view" not in data:
        data["field_of_view"] = 2 * np.arctan(0.5 * data["height"] / data["focal_length"]) * 180 / np.pi

    write_metadata(folder_name, data)
    
    # 5. Extract bands
    # 

    # Set some global properties
    if args.extra > 0:
        args.ply = True

    if args.extra > 1:
        args.flo = True

    if args.extra > 2:
        args.npy = True

    # 5.a EXTRACT MASK (mmdet)
    run("mask_mmdet", folder_name, subpath=True, extra_args=EXTRA_ARGS["mask_mmdet"])

    # 5.b EXTRACT DEPTH
    depth_args = ""
    if args.ply:
        depth_args = "--ply "

    if args.npy:
        depth_args += "--npy "

    # Choose defualt depth band
    if args.depth == None:
        if is_video(input_path):
            args.depth = DEPTH_VIDEO_DEFAULT
        else:
            args.depth = DEPTH_IMAGE_DEFAULT

    # Process depth
    if args.depth == "all":
        for band in DEPTH_BANDS:
            extra_args = depth_args
            if band in EXTRA_ARGS:
                extra_args += EXTRA_ARGS[band]
            if band == "depth_patchfusion" and is_video(input_path):
                extra_args += "--mode=p49 "
            run(band, folder_name, subpath=args.extra, extra_args=extra_args)
    else:
        extra_args = depth_args
        if args.depth in EXTRA_ARGS:
                extra_args += EXTRA_ARGS[args.depth]
        if args.depth == "depth_patchfusion" and is_video(input_path):
            extra_args += "--mode=p49 "

        run(args.depth, folder_name, subpath=args.extra, extra_args=extra_args)

    # Add a default depth band
    if args.rgbd is None:
        if args.depth == "all":
            if is_video(input_path):
                set_default_band(folder_name, "depth", DEPTH_VIDEO_DEFAULT)
            else:
                set_default_band(folder_name, "depth", DEPTH_IMAGE_DEFAULT)
        else:
            set_default_band(folder_name, "depth", args.depth)
    
    if is_video(input_path):

        # 5.c EXTRACT optical FLOW
        if args.flow == None:
            args.flow = FLOW_DEFAULT

        flow_args = ""
        if args.flow_backwards:
            flow_args += "--backwards "

        if args.flow_mask:
            flow_args += "--mask "

        if args.flow == "all":
            for band in FLOW_BANDS:
                extra_args = flow_args
                if band in EXTRA_ARGS:
                    extra_args += EXTRA_ARGS[band]
                run(band, folder_name, subpath=args.flo, extra_args=extra_args)
        else:
            extra_args = flow_args
            if args.flow in EXTRA_ARGS:
                extra_args += EXTRA_ARGS[args.flow]
            run(args.flow, folder_name, subpath=args.flo, extra_args=extra_args)

        # Add a default flow band
        if args.flow == "all":
            set_default_band(folder_name, "flow", FLOW_DEFAULT)
            set_default_band(folder_name, "flow_bwd", FLOW_DEFAULT + "_bwd")
            set_default_band(folder_name, "flow_mask", FLOW_DEFAULT + "_mask")
            set_default_band(folder_name, "flow_mask_bwd", FLOW_DEFAULT + "_mask_bwd")
        else:
            set_default_band(folder_name, "flow", args.flow)
            set_default_band(folder_name, "flow_bwd", args.flow + "_bwd")
            set_default_band(folder_name, "flow_mask", args.flow + "_mask")
            set_default_band(folder_name, "flow_mask_bwd", args.flow + "_mask_bwd")

        # 5.d EXTRACT camera
        run("camera_colmap", folder_name, subpath=True)


        



