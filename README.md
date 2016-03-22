# check_smartmon #

check_smartmon is a Nagios-Plugin that uses smartmontools
(http://smartmontools.sourceforge.net/) to check disk health status and temperature.


## Installation ##

### Dependencies ###
The script simply needs a Python interpreter with the psutil library.

### Configuration ###
Adjust the first line to your Python binary (e.g. `/usr/local/bin/python` or
`/usr/bin/python`) and the path to your smartctl binary (e.g.
`/usr/local/sbin/smartctl` or `/usr/sbin/smartctl`). 

### Unprivileged setup ###
If you intend to use this script as an unprivileged user, you need to run

    gcc -o check_smartmon scriptwrap.c

Then set check_smartmon as being owned by root, and set the execute and 
setuid bits.

IMPORTANT: if you do this, make sure unprivileged users can't replace or edit
check_smartmon.py ot they will be able to execute arbitrary code as root!

## Usage ##
Use `check_smartmon -h` to get a list of options. You will see the following
output:

        usage: check_smartmon(.py) [options]

        options:
          --version             show program's version number and exit
          -h, --help            show this help message and exit
          -d DEVICE, --device=DEVICE
                                device to check
          -a, --all-disks       Check all disks
          -v LEVEL, --verbosity=LEVEL
                                set verbosity level to LEVEL; defaults to 0 (quiet),
                                possible values go up to 3
          -w TEMP, --warning-threshold=TEMP
                                set temperature warning threshold to given temperature
                                (defaults to 55)
          -c TEMP, --critical-threshold=TEMP
                                set temperature critical threshold to given
                                temperature (defaults to 60)

## Monitor configuration ##
Read the Nagios documentation and create a command definition and service.like
Example:

        # 'check_smartmon' command definition
        define command{
                command_name    check_smartmon
                command_line    $USER1$/check_smartmon -d $ARG1$
                }

        ...

        # check local disk S.M.A.R.T. status
        define service{
                use                             generic-service
                host_name                       localhost
                service_description             Check local disk S.M.A.R.T. status
                is_volatile                     0
                check_period                    24x7
                max_check_attempts              4
                normal_check_interval           5
                retry_check_interval            1
                contact_groups                  admins
                notification_options            w,u,c,r
                notification_interval           960
                notification_period             24x7
                check_command                   check_smartmon!/dev/ad0
                }

The device `/dev/ad0` is used on FreeBSD systems, so if you run another system
you must set the appropriate name.

### Caveats ###
The -a option currently does not work when using software raid, lfs or encryption,
since psutil reports the /dev/mapper/* device rather than the actual physical
device.

## Contact ##
* Project Link: http://daemogorgon.net/check-smartmon
* Author: fuller <fuller@daemogorgon.net>
* Fork author: nihlaeth <info@nihlaeth.nl>


## License ##
Copyright (C) 2006  daemogorgon.net

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License along
with this program; if not, write to the Free Software Foundation, Inc.,
51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
