
bl_info = {
    "name": "Addon Installer",
    "author": "JayReigns",
    "version": (1, 0, 0),
    "blender": (2, 80, 0),
    "location": "TopBar > Edit > Install Addon",
    "description": "Quickly install Blender addons from Github link",
    "category": "Development"
}

import bpy
import os
import requests
from io import BytesIO
from zipfile import ZipFile


def get_bl_info(text):

    bl_idx = text.index("bl_info") # raise ValueError
    s_idx  = text.index("{", bl_idx)
    e_idx  = text.index("}", s_idx)

    bl_info = text[s_idx : e_idx+1]
    bl_info = eval(bl_info)

    return bl_info


def open_addon(name):
    bpy.ops.screen.userpref_show(section='ADDONS')
    bpy.data.window_managers[0].addon_search = name


def list_py(zip_info):
    """lists only .py files"""
    return  list(info for info in zip_info 
                    if not info.is_dir() and info.filename.endswith('.py'))


def extract_zip(file, extract_path):
    """extracts zip and returns main .py file containing bl_info"""
    
    with ZipFile(file) as zip_file:
        scripts = list_py(zip_file.filelist)

        if not scripts:
            raise Exception("No .py files in the Archive")
        
        # main file that contains 'bl_info'
        main_file = ""

        if len(scripts) == 1:
            zip_info = scripts[0]
            zip_info.filename = zip_info.filename.rpartition("/")[-1]
            zip_file.extract(zip_info, extract_path)
            main_file = zip_info.filename
        
        else:
            # find shortest __init__.py
            main_file = min(zip_info.filename for zip_info in scripts \
                     if zip_info.filename.rsplit("/", 1)[-1] == "__init__.py")
            
            parent_file = main_file.rstrip("__init__.py")

            # only extract __init__.py and its sub files
            for zip_info in zip_file.filelist:
                if zip_info.filename.startswith(parent_file):
                    zip_file.extract(zip_info, extract_path)

        return extract_path + "/" + main_file


# EXAMPLE URLS

# https://github.com/JayReigns/Blender_Addon_Installer
# ['https:', '', 'github.com', 'JayReigns', 'Blender_Addon_Installer']

# https://github.com/JayReigns/Blender_Addon_Installer/tree/main
# https://github.com/JayReigns/Blender_Addon_Installer/archive/refs/heads/main.zip
# 'main' is branch name
# 'master' refers to default even if named 'main'
# ['https:', '', 'github.com', 'JayReigns', 'Blender_Addon_Installer', 'tree', 'main']

def resolve_url(url):

    ext = url.rsplit(".", 1)[-1].lower()
    if ext not in (".py", ".zip"):
        components = url.split("/")

        if components[2] == 'github.com':
        
            branch = 'master'
            if "tree" in components:
                idx = components.index("tree")
                branch = components[idx+1]
            url = "/".join(components[:5]) + '/archive/refs/heads/' + branch + '.zip'
        
        # add other websites
        else:
            raise Exception("Unsupported URL")
    
    return url


def install_addon(src_path, dst_path):

    if src_path.startswith("http"): # URL

        src_path = resolve_url(src_path)

        r = requests.get(src_path)
        file = BytesIO(r.content)
        main_file = extract_zip(file, dst_path)
    
    else:   # file path

        ext = src_path.rsplit(".", 1)[-1].lower()
        if ext not in (".py", ".zip"):
            raise Exception("Unsupported File type")

        fname = src_path.rsplit("/", 1)[-1]
        main_file = dst_path + "/" + fname

        with open(src_path, 'rb') as ifp:
            with open(main_file, 'wb') as ofp:
                ofp.write(ifp.read())
    

    with open(main_file, 'r') as fp:
        text = fp.read()
        bl_info = get_bl_info(text)
    
    return bl_info


##############################################################################
# OPERATORS
##############################################################################


class ADI_OT_Addon_Installer(bpy.types.Operator):
    """Install Addon from URL/Filepath"""
    bl_idname = "adi.addon_installer"
    bl_label = "Install Addon"

    zippath: bpy.props.StringProperty(
        name="URL/FIlepath",
        # subtype="FILE_PATH",
    )
    dir_type: bpy.props.EnumProperty(
        name="Install Directory",
        items=(
            ('USER', "User", ""),
            ('PREFERENCE', "Preference", ""),
            ('LOCAL', "Local", ""),
            ('SYSTEM', "System", ""),
        ),
    )

    def menu_func(self, context):
        self.layout.operator(ADI_OT_Addon_Installer.bl_idname, icon='IMPORT')

    def invoke(self, context, event):
        wm = context.window_manager
        self.zippath = wm.clipboard # copy link/path from clipboard
        return wm.invoke_props_dialog(self)

    def get_addon_path(self):
        dtype = self.dir_type

        if self.dir_type == 'PREFERENCE':
            pref_dir = bpy.context.preferences.filepaths.script_directory
            if pref_dir:
                return pref_dir + "/addons"
        
        return bpy.utils.resource_path(dtype) + "/scripts/addons"

    def execute(self, context):

        src_path = self.zippath.strip('\"').replace("\\", "/").rstrip("/")
        dst_path = self.get_addon_path().replace("\\", "/").rstrip("/")

        if not os.path.exists(dst_path):
            os.makedirs(dst_path)

        bl_info = install_addon(src_path, dst_path)
        addon_name = bl_info['name']
        open_addon(addon_name)

        self.report({"INFO"}, f'"{addon_name}" Installed!')
        return {'FINISHED'}


##############################################################################
# REGISTER/UNREGISTER
##############################################################################


classes = (
    ADI_OT_Addon_Installer,
)


def register():

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.TOPBAR_MT_edit.append(ADI_OT_Addon_Installer.menu_func)

    # test call
    # bpy.ops.adi.addon_installer('INVOKE_DEFAULT')

def unregister():

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
