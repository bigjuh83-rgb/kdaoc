@echo off
chcp 65001 >nul
set "OUT=%TEMP%\db_dialogue_result.txt"
echo CHECKING... > "%OUT%"
C:\Windows\System32\wsl.exe -d Ubuntu -- bash -c "mariadb --protocol=tcp -h 127.0.0.1 -P 3306 -uroot -pzmstkfka83 opendaoc -e \"SELECT \`Key\`, Value FROM ServerProperty WHERE \`Key\` = 'dummy_companion_dialogue_enabled';\"" >> "%OUT%" 2>&1 || echo BEFORE_ROW_NOT_EXIST >> "%OUT%"
echo UPDATING... >> "%OUT%"
C:\Windows\System32\wsl.exe -d Ubuntu -- bash -c "mariadb --protocol=tcp -h 127.0.0.1 -P 3306 -uroot -pzmstkfka83 opendaoc -e \"UPDATE ServerProperty SET Value = 'True' WHERE \`Key\` = 'dummy_companion_dialogue_enabled';\"" >> "%OUT%" 2>&1 || echo UPDATE_FAILED >> "%OUT%"
echo VERIFYING... >> "%OUT%"
C:\Windows\System32\wsl.exe -d Ubuntu -- bash -c "mariadb --protocol=tcp -h 127.0.0.1 -P 3306 -uroot -pzmstkfka83 opendaoc -e \"SELECT \`Key\`, Value FROM ServerProperty WHERE \`Key\` = 'dummy_companion_dialogue_enabled';\"" >> "%OUT%" 2>&1 || echo VERIFY_FAILED >> "%OUT%"
echo DONE >> "%OUT%"
type "%OUT%"
