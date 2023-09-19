
bl_info = {
    "name": "Addon Installer",
    "author": "JayReigns",
    "version": (1, 1, 0),
    "blender": (2, 80, 0),
    "location": "TopBar > Edit > Install Addon",
    "description": "Quickly install Blender addons from Github link",
    "category": "Development"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
}

UNSUPPORTED_FILE_EXCEPTION_MSG = "Not a .py or .zip file"

import bpy
import addon_utils
import os, shutil
import requests
from urllib.parse import urlparse
from io import BytesIO
from zipfile import ZipFile

from bpy.app.translations import pgettext_tip as tip_


def get_bl_info(text):

    bl_idx = text.index("bl_info") # raise ValueError
    s_idx  = text.index("{", bl_idx)
    e_idx  = text.index("}", s_idx)

    bl_info = text[s_idx : e_idx+1]
    bl_info = eval(bl_info)

    return bl_info


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


def remove_file(path_base, fname):
    f_full = os.path.join(path_base, fname)
    if os.path.exists(f_full):
        if os.path.isdir(f_full):
            shutil.rmtree(f_full)
        else:
            os.remove(f_full)


def filter_zipfile(zfile, zipname):
    
    # list .py files
    scripts = [zinfo for zinfo in zfile.filelist 
                if not zinfo.is_dir() and zinfo.filename.lower().endswith('.py')
    ]
    
    if not scripts:
        raise ValueError("No .py files in the Archive")

    # if contains only one file and not named '__init__.py'
    # rename it
    if len(scripts) == 1:
        zinfo = scripts[0]
        dirname, fname = os.path.split(zinfo.filename)

        if fname != "__init__.py":
            zinfo.filename = dirname + "/__init__.py"

    # find __init__.py files
    init_files = [zinfo.filename for zinfo in scripts \
                if os.path.basename(zinfo.filename) == "__init__.py"
    ]

    if not init_files:
        raise ValueError("Multiple '.py' files, but no '__init__.py' files in the Archive")
    
    hierarchially_sorted = sorted(init_files,
            key=lambda file: (os.path.dirname(file), os.path.basename(file))
    )
    # remove child files
    module_files = [hierarchially_sorted[0]]
    for file in hierarchially_sorted[1:]:
        if not file.startswith(os.path.dirname(module_files[-1])):
            module_files.append(file)

    base_dir = ""
    # get parent of first '__init__.py' in hierarchial order
    parent_dir = os.path.dirname(hierarchially_sorted[0])
    if parent_dir.strip("/") == "": # if __init__.py is in root
        # use 'zipname' without .zip extension
        base_dir = os.path.splitext(zipname)[0]
    
    file_to_extract = []
    # only extract the parent directory of modules
    for zinfo in zfile.filelist:
        # if zinfo.is_dir():
        #     continue
        for mod in module_files:
            if zinfo.filename.startswith(os.path.dirname(mod)):
                parent_dir = os.path.dirname(mod)
                # merge parent dir names for unique name
                parent_dir = parent_dir.strip("/").replace("/", "-")
                # blender doesn't like . in module name
                parent_dir = parent_dir.replace(".", "_")

                # weird bug using 'os.path.join' in windows if filename starts with '/'
                # like '/__init__.py', so use lstrip()
                filepath = zinfo.filename[len(os.path.dirname(mod)):].lstrip("/")
                zinfo.filename = os.path.join(base_dir, parent_dir, filepath).replace("\\", "/")
                file_to_extract.append(zinfo)
                break
    
    return file_to_extract


def install_addon(pyfile, path_addons, overwrite=False, smart_extract=False):
    content_types = ("text/plain", "application/zip",)
    file_types = (".py", ".zip",)

    if pyfile.startswith("http://") or pyfile.startswith("https://"): # URL

        url = resolve_url(pyfile)
        # also filters non .py or .zip files
        filename = get_filename_from_url(url,
                            req_headers=HEADERS,
                            content_types=content_types,
                            file_types=file_types)

        if not filename:
            raise ValueError(UNSUPPORTED_FILE_EXCEPTION_MSG)

        r = requests.get(url, allow_redirects=True, headers=HEADERS, stream=True)
        content = r.content
        
    else:   # file path
        pyfile = pyfile.replace("\\", os.path.sep).replace("/", os.path.sep)
        pyfile = os.path.abspath(os.path.expanduser(os.path.expandvars(pyfile)))

        # check extension
        if not any(pyfile.endswith(t) for t in file_types):
            raise ValueError(UNSUPPORTED_FILE_EXCEPTION_MSG)
        
        # Check if we are installing from a target path,
        # doing so causes 2+ addons of same name or when the same from/to
        # location is used, removal of the file!
        pyfile_dir = os.path.dirname(pyfile)
        for addon_path in addon_utils.paths():
            if os.path.samefile(pyfile_dir, addon_path):
                raise ValueError(("Source file is in the add-on search path: %r") % addon_path)
        # done checking for exceptional case

        filename = os.path.basename(pyfile)
        with open(pyfile, 'rb') as fp:
            content = fp.read()
    
    ext = os.path.splitext(filename)[1]
    addons_new = {}

    if ext == ".py":
        if smart_extract:
            if filename.startswith('__'):   # '__init__.py'
                bl_info = get_bl_info(str(content, "utf-8"))
                filename = bl_info['name'] + ".py"

        path_dest = os.path.join(path_addons, filename)

        if overwrite:
            remove_file(path_addons, filename)
        elif os.path.exists(path_dest):
            raise ValueError(("File already installed to %r\n") % path_dest)

        addons_old = {mod.__name__ for mod in addon_utils.modules()}
        
        with open(path_dest, 'wb') as fp:
            fp.write(content)

        addons_new = {mod.__name__ for mod in addon_utils.modules()} - addons_old

    elif ext == ".zip":
        with ZipFile(BytesIO(content)) as zfile:
            if smart_extract:
                file_to_extract = filter_zipfile(zfile, filename)
            else:
                file_to_extract = zfile.filelist

            if overwrite:
                for zinfo in file_to_extract:
                    remove_file(path_addons, zinfo.filename)
            else:
                for zinfo in file_to_extract:
                    path_dest = os.path.join(path_addons, zinfo.filename)
                    if os.path.exists(path_dest):
                        raise ValueError(("File already installed to %r\n") % path_dest)
            
            addons_old = {mod.__name__ for mod in addon_utils.modules()}

            for zinfo in file_to_extract:
                zfile.extract(zinfo, path_addons)
            
            addons_new = {mod.__name__ for mod in addon_utils.modules()} - addons_old

    addons_new.discard("modules")
    return addons_new


#########################################################################################
# NETWORK UTILITY FUNCTIONS
#########################################################################################


def get_filename_from_url(url, req_headers=None, content_types=None, file_types=None):

    r = requests.head(url, allow_redirects=True, headers=req_headers)
    r.raise_for_status()

    resp_headers = r.headers

    content_type = resp_headers["content-type"]
    if not content_types or any(t in content_type for t in content_types):

        if "content-disposition" in resp_headers:
            disp = resp_headers["content-disposition"]
            filename = disp.rsplit('filename=', 1)[-1].strip().strip('\"')
        
        else:
            filename = os.path.basename(urlparse(url).path)

        # check extension
        if not file_types or any(filename.endswith(t) for t in file_types):
            return filename


def download_temp(url, chunk_size=8192):
    import tempfile

    temp = tempfile.SpooledTemporaryFile(max_size=chunk_size, mode="w+b")

    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        for chunk in r.iter_content(chunk_size=chunk_size): 
            temp.write(chunk)
    
    temp.seek(0)

    return temp


#########################################################################################
# BLENDER UTILITY FUNCTIONS
#########################################################################################


def open_addon_window(name):
    bpy.ops.screen.userpref_show('INVOKE_DEFAULT')
    bpy.context.preferences.active_section = 'ADDONS'
    bpy.context.window_manager.addon_filter = 'All'
    bpy.context.window_manager.addon_search = name
    try: # for newer Blender versions
        bpy.context.preferences.view.show_addons_enabled_only = False
    except:
        pass


def get_addon_path(target):

    if target == 'DEFAULT':
        # don't use bpy.utils.script_paths("addons") because we may not be able to write to it.
        path_addons = bpy.utils.user_resource('SCRIPTS', path="addons", create=True)
    else:
        path_addons = bpy.context.preferences.filepaths.script_directory
        if path_addons:
            path_addons = os.path.join(path_addons, "addons")

    if not path_addons:
        if not path_addons:
            raise ValueError("Failed to get add-ons path")

    if not os.path.isdir(path_addons):
        os.makedirs(path_addons, exist_ok=True)
    
    return path_addons


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
    target: bpy.props.EnumProperty(
        name="Target Path",
        description="Choose where to install",
        items=(
            ('DEFAULT', "Default", ""),
            ('PREFS', "User Prefs", ""),
        ),
    )
    smart_extract: bpy.props.BoolProperty(
        name="Smart Extract",
        description="Organizes the files structure if enabled, otherwise extracts as is",
        default=True,
    )
    overwrite: bpy.props.BoolProperty(
        name="Overwrite",
        description="Remove existing add-ons with the same ID",
        default=False,
    )
    enable: bpy.props.BoolProperty(
        name="Enable Addon",
        description="Enable the Installed Addon",
        default=False,
    )


    def menu_func(self, context):
        self.layout.separator()
        self.layout.operator(ADI_OT_Addon_Installer.bl_idname, icon='IMPORT')

    def invoke(self, context, event):
        wm = context.window_manager
        self.filepath = wm.clipboard # copy link/path from clipboard
        return wm.invoke_props_dialog(self)

    def execute(self, context):

        try:
            pyfile = self.filepath.strip("\"").strip("\'").replace("\\", "/").rstrip("/")
            path_addons = get_addon_path(self.target).replace("\\", "/").rstrip("/")

            addons_new = install_addon(pyfile, path_addons, self.overwrite, self.smart_extract)

            # disable any addons we may have enabled previously and removed.
            # this is unlikely but do just in case. bug [#23978]
            # for new_addon in addons_new:
            #     addon_utils.disable(new_addon, default_set=True)

            # enable all installed addons
            if self.enable:
                for mod in addon_utils.modules(refresh=False):
                    if mod.__name__ in addons_new:
                        info = addon_utils.module_bl_info(mod)
                        bpy.ops.preferences.addon_enable(module=mod.__name__)
            else:
                # possible the zip contains multiple addons, we could disallow this
                # but for now just use the first
                for mod in addon_utils.modules(refresh=False):
                    if mod.__name__ in addons_new:
                        info = addon_utils.module_bl_info(mod)
                        open_addon_window(info["name"])
                        break
            
            # in case a new module path was created to install this addon.
            bpy.utils.refresh_script_paths()

            bpy.ops.preferences.addon_refresh()

            # print message
            msg = (
                tip_("Modules Installed (%s) from %r into %r") %
                (", ".join(sorted(addons_new)), pyfile, path_addons)
            )
            # print(msg)
            self.report({'INFO'}, msg)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({"ERROR"}, str(e))
            return {'CANCELLED'}


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


def unregister():

    bpy.types.TOPBAR_MT_edit.remove(ADI_OT_Addon_Installer.menu_func)

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
    # test call
    bpy.ops.adi.addon_installer('INVOKE_DEFAULT')
