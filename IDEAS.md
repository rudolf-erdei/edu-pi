# Future ideas for the project

* Shutdown from the interface! IMPORTANT
* Break the scripts into multiple atomic ones: startup, install, update, start_captive_portal
  * Usually update.sh is the old version when running. Need to find a way to solve this and run the new script after pull.
* On boot, display the current status and eventual errors on the screen.
   - Maybe with a loading indicator and if everything is OK?
* Some issues need to be also displayed on the screen, to have a better view of what is happening.
* Optimize the PI for long term usage:
  * Remove GUI
  * Disable Swap (sudo swapoff -a) or `sudo dphys-swapfile swapoff || sudo dphys-swapfile uninstall || sudo systemctl disable dphys-swapfile`
  * `sudo apt install log2ram`
  * `sudo apt purge libreoffice* wolfram-engine scratch* geany thonny`
  * `sudo apt autoremove --purge`
  * `sudo apt clean`
  * `sudo systemctl disable cups`
  * `sudo systemctl disable cups-browsed`
  * `sudo apt purge modemmanager`
  * `sudo systemctl disable triggerhappy.service`
  * `sudo apt purge "x11-*" "wayfire" "lxde*" "pixel*" lightdm` 
  * `sudo apt autoremove`
  * remove swap from /etc/fstab - if exists
  * `sudo rm /swapfile`