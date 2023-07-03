#!/bin/bash

bash_file='.bashrc'

text='export ROS_MASTER_URI=http://'

# Get the IP address of the master
read -p "Enter the IP address of the master: " master_ip
ip=$(hostname -I)

# Create the new text to replace the old one
replaced_text=$text$master_ip':11311'

# Change the directory to the home directory
cd 

# Replace the IP address of the master
sed -i "s|$text.*|$replaced_text|" $bash_file
# Change the IP address in Rpi4
sed -i "s|export ROS_IP=.*|export ROS_IP=$ip|" $bash_file
sed -i "s|export ROS_HOSTNAME=.*|export ROS_HOSTNAME=$ip|" $bash_file

# Source the bashrc file
source ~/.bashrc

echo "Done!"
echo "The IP address of the master is changed to <$master_ip>."
echo "The hostname is <$ip>."

