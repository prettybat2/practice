@echo off
rem PC 본 렌더: 장면 클립을 차례로 만듦 (Eevee, 1080x1920). Blender 경로는 설치 버전에 맞게 고치세요.
set BLENDER="C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"
cd /d %~dp0
for %%s in (scene01 scene02 scene03 scene04 scene05 scene06 scene07) do (
  %BLENDER% -b -P make_clips.py -- %%s
)
pause
