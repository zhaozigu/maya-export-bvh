import os
import math

import maya.cmds as cmds
import maya.api.OpenMaya as om


def get_bone_rotation(bone):
    cur_mat = om.MMatrix(cmds.xform(bone, q=True, ws=True, m=True))
    parent = cmds.listRelatives(bone, p=True)[0]
    parent_mat = om.MMatrix(cmds.xform(parent, q=True, ws=True, m=True))

    local_mat = cur_mat * parent_mat.inverse()
    cur_xfo_mat = om.MTransformationMatrix(local_mat)
    rotation = [math.degrees(x) for x in cur_xfo_mat.rotation().asVector()]
    return rotation


def export_motion(joints, start_frame, end_frame, rot_order: tuple):
    motion_str = ""

    root_joint = joints[0]

    for frame in range(start_frame, end_frame + 1):
        cmds.currentTime(frame)
        for joint in joints:
            joint_name = cmds.ls(joint, long=True)[0]
            rot = get_bone_rotation(joint_name)

            if joint == root_joint:
                loc = cmds.xform(joint_name, q=True, translation=True)
                motion_str += "%.6f %.6f %.6f " % (loc[0], loc[1], loc[2])
            motion_str += "%.6f %.6f %.6f " % (
                rot[rot_order[0]], rot[rot_order[1]], rot[rot_order[2]])

        motion_str += "\n"

    return motion_str


def export_hierarchy(joints, rot_order: str):
    hierarchy_str = "HIERARCHY\n"

    def _process_joint(joint, indent):
        nonlocal hierarchy_str
        joint_name_raw = cmds.ls(joint, long=True)[0]
        joint_name = joint_name_raw.split("|")[-1].split(":")[-1]

        if indent == 0:
            hierarchy_str += "{}ROOT {}\n".format('\t' * indent, joint_name)
        else:
            hierarchy_str += "{}JOINT {}\n".format('\t' * indent, joint_name)

        loc = cmds.xform(joint_name_raw, q=True, translation=True)
        hierarchy_str += "{}{{\n".format('\t' * indent)
        hierarchy_str += "{}OFFSET {:.6f} {:.6f} {:.6f}\n".format(
            '\t' * (indent + 1), loc[0], loc[1], loc[2])

        if indent == 0:
            hierarchy_str += "{}CHANNELS 6 Xposition Yposition Zposition {}rotation {}rotation {}rotation\n".format(
                '\t' * (indent + 1), rot_order[0], rot_order[1], rot_order[2])
        else:
            hierarchy_str += "{}CHANNELS 3 {}rotation {}rotation {}rotation\n".format(
                '\t' * (indent + 1), rot_order[0], rot_order[1], rot_order[2])

        children = cmds.listRelatives(joint, children=True, type="joint")
        if children:
            for child in children:
                _process_joint(child, indent + 1)
        else:
            hierarchy_str += "{}End Site\n".format('\t' * (indent + 1))
            hierarchy_str += "{}{{\n".format('\t' * (indent + 1))
            hierarchy_str += "{}OFFSET 0.0 0.0 0.0\n".format(
                '\t' * (indent + 2))
            hierarchy_str += "{}}}\n".format('\t' * (indent + 1))

        hierarchy_str += "{}}}\n".format('\t' * indent)

    root_joint = joints[0]
    _process_joint(root_joint, 0)
    return hierarchy_str


def export_bvh(joints, output_file_path, start_frame, end_frame, rot_order="ZXY"):
    _order = {
        "XYZ": (0, 1, 2),
        "XZY": (0, 2, 1),
        "YXZ": (1, 0, 2),
        "YZX": (1, 2, 0),
        "ZXY": (2, 0, 1),
        "ZYX": (2, 1, 0),
    }
    assert rot_order in _order, "The parameters of the rotation order are incorrect"

    hierarchy = export_hierarchy(joints, rot_order)
    motion = export_motion(joints, start_frame, end_frame, _order[rot_order])
    num_frames = end_frame - start_frame + 1
    frame_rate = cmds.playbackOptions(query=True, framesPerSecond=True)
    if frame_rate == 0:
        frame_rate = 24.0
    frame_time = 1.0 / frame_rate

    with open(output_file_path, "w") as output_file:
        output_file.write(hierarchy)
        output_file.write(
            f"MOTION\nFrames: {num_frames}\nFrame Time: {frame_time:.6f}\n")
        output_file.write(motion)


def get_ordered_joints(joint):
    ordered_joints = [joint]

    children = cmds.listRelatives(joint, children=True, type="joint")
    if children:
        for child in children:
            ordered_joints.extend(get_ordered_joints(child))

    return ordered_joints


if __name__ == "__main__":
    root_joint_name = "root"
    root_joint = None
    children = cmds.listRelatives(
        root_joint_name, children=True, type="joint")
    if children:
        root_joint = children[0]
    else:
        raise ValueError(f"No joint found under {root_joint_name}")

    joints = get_ordered_joints(root_joint)
    print(joints)

    start_frame = int(cmds.playbackOptions(query=True, minTime=True))
    end_frame = int(cmds.playbackOptions(query=True, maxTime=True))

    # Set the output file path
    output_file_path = os.path.join(
        os.path.expanduser("~"), "maya_body_test.bvh")

    export_bvh(joints, output_file_path, start_frame, end_frame, "ZYX")
