@echo off
git pull origin main --rebase
git add .
git commit -m "Auto-update Búnker"
git push origin main
echo --- APP ACTUALIZADA Y BLINDADA ---
pause