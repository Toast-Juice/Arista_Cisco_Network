Developed By: Toast Juice
# Arista_Cisco_Network
This program allows the user to make small, minimally invasive configuration changes to a Cisco or Arista switch as long as the user has an account available by the switch.

The program utilizes a Python Source Code. In order to make changes to the source code, the user must have netmiko installed, otherwise you will get an error anytime a function is called.

The program also utilizes a JSON file to hold the devices list with a category for "Name", "IP", "Site", and "State". The Name, Site, and State categories can be used when selecting the 
scope of devices. The function will have a different window for each device within the scope when done using the "Multiple Devices", "State", or "Site" scopes.
