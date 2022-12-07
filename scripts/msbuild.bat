REM TODO: detect path to vcvars path instead of hardcoding a specific version
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64"
set PATH=%PATH%;%~dp0\..\pkgs\bin
set LIB=%LIB%;%~dp0\..\pkgs\lib
echo PATH = %PATH%
echo LIB = %LIB%
msbuild %*
