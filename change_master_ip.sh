#!/bin/bash

bash_file='.bashrc'

text='export ROS_HOSTNAME=http://'

# Get the IP address of the master
read -p "Enter the IP address of the master: " ip

# Create the new text to replace the old one
replaced_text=$text$ip':11311'

# Change the directory to the home directory
cd 

# Replace the IP address of the master
sed -i "s|$text.*|$replaced_text|" ~/.bashrc

# Source the bashrc file
source ~/.bashrc

echo "Done! The IP address of the master is changed to <$ip>."

