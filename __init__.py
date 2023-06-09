
bl_info = {
    "name": "Addon Installer",
    "author": "JayReigns",
    "version": (1, 0, 0),
    "blender": (2, 80, 0),
    "location": "TopBar > Edit > Install Addon",
    "description": "Quickly install Blender addons from Github link",
    "category": "Development"
}

MODULE_NAME = "module"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
}

HEADER_CONTENT_DISPOSITION = "Content-disposition"
HEADER_CONTENT_TYPE =  "Content-Type"

TEXT_CONTENT_TYPE =  "text/plain"
ZIP_CONTENT_TYPE =  "application/zip"

UNSUPPORTED_FILE_EXCEPTION_MSG = "Not a .py or .zip file"

import bpy
import os
import requests
from urllib.parse import urlparse
from io import BytesIO
from zipfile import ZipFile


def get_bl_info(filepath="", text=None):

    if not text:
        with open(filepath, encoding="utf-8") as f:
            text = f.read()

    bl_idx = text.index("bl_info") # raise ValueError
    s_idx  = text.index("{", bl_idx)
    e_idx  = text.index("}", s_idx)

    bl_info = text[s_idx : e_idx+1]
    bl_info = eval(bl_info)

    return bl_info


def open_addon(name):
    bpy.ops.screen.userpref_show(section='ADDONS')
    bpy.data.window_managers[0].addon_search = name
    bpy.ops.preferences.addon_refresh()


# EXAMPLE URLS

# https://github.com/JayReigns/Blender_Addon_Installer/blob/main/__init__.py
# https://github.com/JayReigns/Blender_Addon_Installer/raw/main/__init__.py

# https://github.com/JayReigns/Blender_Addon_Installer
# ['https:', '', 'github.com', 'JayReigns', 'Blender_Addon_Installer']

# https://github.com/JayReigns/Blender_Addon_Installer/tree/main
# https://github.com/JayReigns/Blender_Addon_Installer/archive/refs/heads/main.zip
# 'main' is branch name
# 'master' refers to default even if named 'main'
# ['https:', '', 'github.com', 'JayReigns', 'Blender_Addon_Installer', 'tree', 'main']

def resolve_url(url):

    p_url = urlparse(url)
    
    if p_url.netloc == 'github.com':
        
        path = p_url.path.strip("/")
        comps = path.split("/")
        
        if path.endswith('.py'):
            comps[2] = 'raw'
            return p_url._replace(path="/".join(comps)).geturl()
    
        branch = 'master'
        if "tree" in comps:
            idx = comps.index("tree")
            branch = comps[idx+1]
        
        path = "/".join(comps[:2]) + '/archive/refs/heads/' + branch + '.zip'
        return p_url._replace(path=path).geturl()
        
    # add other websites
    
    return url

def download(url):

    download_url = ""
    
    r = requests.head(url, allow_redirects=True, headers=HEADERS)
    header = r.headers

    if HEADER_CONTENT_DISPOSITION in header:
        cdisp = header[HEADER_CONTENT_DISPOSITION]
        filename = cdisp.rsplit('filename=', 1)[-1].strip().strip('\"')
        download_url = url
    
    else:
        ctype = header[HEADER_CONTENT_TYPE]
        if TEXT_CONTENT_TYPE in ctype or ZIP_CONTENT_TYPE in ctype:

            filename = urlparse(url).path.rsplit("/", 1)[-1]
            ext = filename.rsplit(".", 1)[-1]

            if ext.lower() in ("py", "zip",):
                download_url = url
    
    if download_url:
        r = requests.get(url, allow_redirects=True, headers=HEADERS)
        return filename, r.content
    else:
        raise ValueError(UNSUPPORTED_FILE_EXCEPTION_MSG)

def install_py(src_path, dst_path, filename, content=None):
    # src_path not used if content != None

    if not content:
        with open(src_path, 'rb') as fp:
            content = fp.read()

    bl_info = get_bl_info(text=str(content, "utf-8"))

    if filename == "__init__.py":
        filename = bl_info['name'] + ".py"

    out_path = dst_path + "/" + filename

    if not os.path.exists(dst_path):
        os.makedirs(dst_path)

    with open(out_path, 'wb') as fp:
        fp.write(content)

    bl_info[MODULE_NAME] = filename[:-len('.py')]
    return bl_info


def extract_zip(src_path, dst_path, filename, content=None):
    """extracts zip and returns main .py file containing bl_info"""
    
    file = BytesIO(content) if content else src_path
    with ZipFile(file) as zip_file:

        # list .py files
        scripts = list(info
                       for info in zip_file.filelist 
                            if not info.is_dir()
                                and info.filename.lower().endswith('.py')
        )

        if not scripts:
            raise ValueError("No .py files in the Archive")


        if len(scripts) == 1:
            zip_info = scripts[0]
            filename = zip_info.filename.rsplit("/", 1)[-1]

            if not filename.startswith('__'):   # '__init__.py'
                content = zip_file.read(zip_info)
                return install_py(src_path, dst_path, filename, content)
        

        # find shortest __init__.py
        main_file = min(zip_info.filename
                        for zip_info in scripts
                    if zip_info.filename.rsplit("/", 1)[-1] == "__init__.py"
        )
        
        parent_file, main_file, _ = main_file.rpartition("__init__.py")

        if parent_file.strip("/") == "":    # __init__.py is in root
            dst_path += "/" + filename
        else:   # not necessary but incase of /src/...
            filename = parent_file.strip("/").replace("/", "-")
            dst_path += "/" + filename
        
        if not os.path.exists(dst_path):
            os.makedirs(dst_path)

        # only extract __init__.py and its sub files
        for zip_info in zip_file.filelist:  # scripts[] not used
            if zip_info.is_dir():
                continue
            if zip_info.filename.startswith(parent_file):
                zip_info.filename = zip_info.filename[len(parent_file):]
                zip_file.extract(zip_info, dst_path)
        
        bl_info = get_bl_info(filepath= dst_path + "/" + main_file)
        bl_info[MODULE_NAME] = filename
        return bl_info


def install_addon(src_path, dst_path):

    if src_path.startswith("http"): # URL
        try:
            error = None
            filename, content = download(src_path)
        except ValueError as e:
            error = e

        if error:
            url = resolve_url(src_path)
            filename, content = download(url)
        
    else:   # file path
        filename = src_path.rsplit("/", 1)[-1]
        content = None
    
    ext = filename.rsplit(".", 1)[-1].lower()

    if ext == "py":
        return install_py(src_path, dst_path, filename, content)

    if ext == "zip":
        return extract_zip(src_path, dst_path, filename, content)

    raise ValueError(UNSUPPORTED_FILE_EXCEPTION_MSG)
    return


##############################################################################
# OPERATORS
##############################################################################


class ADI_OT_Addon_Installer(bpy.types.Operator):
    """Install Addon from URL/Filepath"""
    bl_idname = "adi.addon_installer"
    bl_label = "Install Addon"

    filepath: bpy.props.StringProperty(
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
    enable: bpy.props.BoolProperty(
        name="Enable Addon",
    )


    def menu_func(self, context):
        self.layout.separator()
        self.layout.operator(ADI_OT_Addon_Installer.bl_idname, icon='IMPORT')

    def invoke(self, context, event):
        wm = context.window_manager
        self.filepath = wm.clipboard # copy link/path from clipboard
        return wm.invoke_props_dialog(self)

    def get_addon_path(self):
        dtype = self.dir_type

        if self.dir_type == 'PREFERENCE':
            pref_dir = bpy.context.preferences.filepaths.script_directory
            if pref_dir:
                return pref_dir + "/addons"
        
        return bpy.utils.resource_path(dtype) + "/scripts/addons"

    def execute(self, context):

        src_path = self.filepath.strip('\"').replace("\\", "/").rstrip("/")
        dst_path = self.get_addon_path().replace("\\", "/").rstrip("/")

        try:
            bl_info = install_addon(src_path, dst_path)
            addon_name = bl_info['name']

            if self.enable:
                prefs = context.preferences
                used_ext = {ext.module for ext in prefs.addons}
                module_name = bl_info[MODULE_NAME]
                is_enabled = module_name in used_ext
                if not is_enabled:
                    bpy.ops.preferences.addon_enable(module=module_name)
            else:
                open_addon(addon_name)
            
            self.report({"INFO"}, f'"{addon_name}" Installed!')
            # self.report({"WARNING"},
            #             f"Name: {bl_info['name']} \n" +
            #             f"Location: {bl_info['location']} \n" +
            #             f"Description: {bl_info['description']} \n"
            # )
        except Exception as e:
            self.report({"ERROR"}, str(e))
            # self.report({"INFO"}, str(e))


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

    bpy.types.TOPBAR_MT_edit.remove(ADI_OT_Addon_Installer.menu_func)

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
