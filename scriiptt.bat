@echo off
setlocal enabledelayedexpansion

rem Start nodes from port 5000 to 5030
for /l %%x in (5000,1,5030) do (
    start cmd /k python poch.py %%x
)

endlocal