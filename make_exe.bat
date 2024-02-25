pyinstaller --exclude-module PIL --onedir -y -i "./condenser_icon.png" "./condenser.py"
xcopy utils dist\condenser\utils /e /i /h
copy config.json dist\condenser\config.json
findstr /v /r "^!\[Condenser\].*" README.md | findstr /v /r "^\[!\[codecov\].*" > dist\condenser\README.txt
del dist\condenser\_internal\_bz2.pyd
del dist\condenser\_internal\_hashlib.pyd
del dist\condenser\_internal\_socket.pyd
del dist\condenser\_internal\_lzma.pyd
del dist\condenser\_internal\unicodedata.pyd
del dist\condenser\_internal\libcrypto-3.dll
del dist\condenser\_internal\ucrtbase.dll
del dist\condenser\_internal\api-ms-win-*