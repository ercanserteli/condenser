pyinstaller --add-data "config.json;." --add-data "README.txt;." --onedir -y -i "./condenser_icon.ico" "./condenser.py"
xcopy utils dist\condenser\utils /e /i /h
del dist\condenser\_bz2.pyd
del dist\condenser\_hashlib.pyd
del dist\condenser\_socket.pyd
del dist\condenser\_ssl.pyd
del dist\condenser\_lzma.pyd
del dist\condenser\unicodedata.pyd
del dist\condenser\libcrypto-1_1-x64.dll
del dist\condenser\libssl-1_1-x64.dll
del dist\condenser\ucrtbase.dll
del dist\condenser\api-ms-win-*