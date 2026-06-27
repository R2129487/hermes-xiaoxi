@echo off
chcp 65001 >nul
title CodeBuddy MESH Bridge

echo ============================================
echo  CodeBuddy MESH 桥接代理
echo  连接至: ws://101.37.231.143:8765
echo ============================================
echo.

set MESH_SERVER=ws://101.37.231.143:8765
set MESH_ADMIN_PASSWORD=840601
set MESH_AGENT_ID=codebuddy

cd /d "%~dp0"

echo [%date% %time%] 正在启动桥接代理...
python codebuddy_bridge.py --server %MESH_SERVER%

if %ERRORLEVEL% NEQ 0 (
    echo [%date% %time%] ❌ 桥接代理异常退出，错误码: %ERRORLEVEL%
    pause
)
