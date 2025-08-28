# Blender Addon Installer
Quickly install Blender addons from Copied Github links or other links or filepath.

## Location
`TopBar > Edit > Install Addon`

## Features
- Smart Extraction Allows to install addons from ill-formatted files
- Automatically pastes copied link
- Auto enable installed addons
- Overwrite detection
- Quotations are allowed in path (eg. `"path"`)
- Install from local `.py` or `.zip` files
- Install from links of `.py` or `.zip` files
- Install from https://github.com/ links
- Github Branches are auto detected
- Auto detect single `.py` file from Github (No need to click `raw` button)


## Quick Installation

Run the following script from Blender.

```python
import os
import tempfile
import urllib.request

import bpy

url = "https://github.com/JayReigns/Blender_Addon_Installer/archive/refs/heads/main.zip"

# Download zip to temp file.
temp_zip = os.path.join(tempfile.gettempdir(), "Blender_Addon_Installer.zip")
urllib.request.urlretrieve(url, temp_zip)

# Install addon using Blender API.
bpy.ops.preferences.addon_install(filepath=temp_zip, overwrite=True)
bpy.ops.preferences.addon_enable(module="Blender_Addon_Installer-main")
```


## Other Addons
- [API Browser](https://github.com/JayReigns/API_Browser) : Browse through the python api via Blender user interface