#!/usr/bin/python3
"""Nagios plugin for monitoring S.M.A.R.T. status."""

# -*- coding: iso8859-1 -*-
#
# $Id: version.py 133 2006-03-24 10:30:20Z fuller $
#
# check_smartmon
# Copyright (C) 2006  daemogorgon.net
#
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 2 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License along
#   with this program; if not, write to the Free Software Foundation, Inc.,
#   51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
#
# Fork author: nihlaeth
#

import os.path
import sys
import re
import psutil
import subprocess
from optparse import OptionParser

__author__ = "fuller <fuller@daemogorgon.net>"
__version__ = "$Revision$"


# path to smartctl
# TODO use which to fetch path
_smartctl_path = "/usr/sbin/smartctl"

# application wide verbosity (can be adjusted with -v [0-3])
_verbosity = 0


def parse_cmd_line(arguments):
    """Commandline parsing."""
    usage = "usage: %prog [options] device"
    version = f"%%prog {__version__}"

    parser = OptionParser(usage=usage, version=version)
    parser.add_option(
        "-d",
        "--device",
        action="store",
        dest="device",
        default="",
        metavar="DEVICE",
        help="device to check")
    parser.add_option(
        "-a",
        "--all-disks",
        action="store_true",
        dest="alldisks",
        default="",
        help="Check all disks")
    parser.add_option(
        "-v",
        "--verbosity",
        action="store",
        dest="verbosity",
        type="int",
        default=0,
        metavar="LEVEL",
        help="set verbosity level to LEVEL; defaults to 0 (quiet), \
                    possible values go up to 3")
    parser.add_option(
        "-w",
        "--warning-threshold",
        metavar="TEMP",
        action="store",
        type="int",
        dest="warning_temp",
        default=55,
        help=("set temperature warning threshold to given temperature"
              " (default:55)"))
    parser.add_option(
        "-c",
        "--critical-threshold",
        metavar="TEMP",
        action="store",
        type="int",
        dest="critical_temp",
        default="60",
        help=("set temperature critical threshold to given temperature"
              " (default:60)"))

    return parser.parse_args(arguments)


def check_device_permissions(path):
    """Check if device exists and permissions are ok.

    Returns:
        - 0 ok
        - 1 no such device
        - 2 no read permission given
    """
    vprint(3, f"Check if {path} does exist and can be read")
    if not os.access(path, os.F_OK):
        return (3, "UNKNOWN: no such device found")
    elif not os.access(path, os.R_OK):
        return (3, "UNKNOWN: no read permission given")
    else:
        return (0, "")
    return (0, "")


def check_smartmontools(path):
    """Check if smartctl is available and can be executed.

    Returns:
        - 0 ok
        - 1 no such file
        - 2 cannot execute file
    """
    vprint(3, f"Check if {path} does exist and can be read")
    if not os.access(path, os.F_OK):
        print(f"UNKNOWN: cannot find {path}")
        sys.exit(3)
    elif not os.access(path, os.X_OK):
        print(f"UNKNOWN: cannot execute {path}")
        sys.exit(3)


def call_smartmontools(path, device):
    """Get smartmontool output."""
    cmd = f"{path} -d sat -a {device}"
    vprint(3, f"Get device health status: {cmd}")
    result = ""
    message = ""
    code_to_return = 0
    try:
        result = subprocess.check_output(cmd, shell=True)
    except subprocess.CalledProcessError as error:
        # smartctl passes a lot of information via the return code
        return_code = error.returncode
        if return_code % 2**1 > 0:
            # bit 0 is set - command line did not parse
            # output is not useful now, simply return
            message += "UNKNOWN: smartctl parsing error "
            return_code -= 2**0
            code_to_return = 3
        if return_code % 2**2 > 0:
            # bit 1 is set - device open failed
            # output is not useful now, simply return
            message += "UNKNOWN: could not open device "
            return_code -= 2**1
            code_to_return = 3
        if return_code % 2**3 > 0:
            # bit 2 is set - some smart or ata command failed
            # we still want to see what the output says
            result = error.output
            message += "CRITICAL: some SMART or ATA command to disk failed "
            return_code -= 2**2
            code_to_return = 2
        if return_code % 2**4 > 0:
            # bit 3 is set - smart status returned DISK FAILING
            # we still want to see what the output says
            result = error.output
            message += "CRITICAL: SMART statis is DISK FAILING "
            return_code -= 2**3
            code_to_return = 2
        if return_code % 2**5 > 0:
            # bit 4 is set - prefail attributes found
            result = error.output
            message += "CRITICAL: prefail attributes found "
            return_code -= 2**4
            code_to_return = 2
        if return_code % 2**6 > 0:
            # bit 5 is set - disk ok, but prefail attributes in the past
            result = error.output
            # this should be a warning, but that's too much hasle
            message += "WARNING: some prefail attributes were critical "
            message += "in the past "
            return_code -= 2**5
            code_to_return = 1
        if return_code % 2**7 > 0:
            # bit 6 is set - errors recorded in error log
            result = error.output
            message += "WARNING: errors recorded in error log "
            return_code -= 2**6
            code_to_return = 1
        if return_code % 2**8 > 0:
            # bit 7 is set - device self-test log contains errors
            result = error.output
            message += "CRITICAL: self-test log contains errors "
            return_code -= 2**7
            code_to_return = 2
    except OSError as error:
        code_to_return = 3
        message = f"UNKNOWN: call exits unexpectedly ({error})"

    return (code_to_return, result, message)


def parse_output(output, warning_temp, critical_temp):
    """
    Parse smartctl output.

    Returns status of device.
    """
    # parse health status
    #
    # look for line '=== START OF READ SMART DATA SECTION ==='
    status_line = ""
    health_status = ""
    reallocated_sector_ct = 0
    temperature = 0
    reallocated_event_count = 0
    current_pending_sector = 0
    offline_uncorrectable = 0
    error_count = 0

    lines = output.decode(sys.getdefaultencoding()).split("\n")
    for line in lines:
        # extract status line
        if "overall-health self-assessment test result" in line:
            status_line = line
            parts = status_line.rstrip().split()
            health_status = parts[-1:][0]
            vprint(3, f"Health status: {health_status}")
        # extract status line (compatibility with all smartctl versions)
        if "Health Status" in line:
            status_line = line
            parts = status_line.rstrip().split()
            health_status = parts[-1:][0]
            vprint(3, f"Health status: {health_status}")

        parts = line.split()
        if len(parts) > 0:
            # self test spans can also start with 5, so we
            # need a tighter check here than elsewhere
            if parts[0] == "5" and \
                    parts[1] == "Reallocated_Sector_Ct" and \
                    reallocated_sector_ct == 0:
                # extract reallocated_sector_ct
                # 5 is the reallocated_sector_ct id
                reallocated_sector_ct = int(parts[9])
                vprint(3, f"Reallocated_Sector_Ct: {reallocated_sector_ct}")
            elif parts[0] == "190" and temperature == 0:
                # extract temperature
                # 190 can be temperature value id too
                temperature = int(parts[9])
                vprint(3, f"Temperature: {temperature}")
            elif parts[0] == "194" and temperature == 0:
                # extract temperature
                # 194 is the temperature value id
                temperature = int(parts[9])
                vprint(3, f"Temperature: {temperature}")
            elif parts[0] == "196" and reallocated_event_count == 0:
                # extract reallocated_event_count
                # 196 is the reallocated_event_count id
                reallocated_event_count = int(parts[9])
                vprint(
                    3, f"Reallocated_Event_Count: {reallocated_event_count}")
            elif parts[0] == "197" and current_pending_sector == 0:
                # extract current_pending_sector
                # 197 is the current_pending_sector id
                current_pending_sector = int(parts[9])
                vprint(3, f"Current_Pending_Sector: {current_pending_sector}")
            elif parts[0] == "198" and offline_uncorrectable == 0:
                # extract offline_uncorrectable
                # 198 is the offline_uncorrectable id
                offline_uncorrectable = int(parts[9])
                vprint(3, f"Offline_Uncorrectable: {offline_uncorrectable}")
            elif "ATA Error Count" in line:
                error_count = int(parts[3])
                vprint(3, f"ATA error count: {error_count}")
            elif "No Errors Logged" in line:
                error_count = 0
                vprint(3, "ATA error count: 0")

    # now create the return information for this device
    return_status = 0
    device_status = ""

    # check if smartmon could read device
    if health_status == "":
        return (3, "UNKNOWN: could not parse output")

    # check health status
    while health_status not in ["PASSED", "OK"]:
        return_status = 2
        device_status += "CRITICAL: device does not pass health status "

    # check sectors
    if reallocated_sector_ct > 0 or \
            reallocated_event_count > 0 or \
            current_pending_sector > 0 or \
            offline_uncorrectable > 0:
        return_status = 2
        device_status += "CRITICAL: there is a problem with bad sectors "
        device_status += "on the drive. "
        device_status += f"Reallocated_Sector_Ct:{reallocated_sector_ct}"
        device_status += f"Reallocated_Event_Count:{reallocated_event_count}"
        device_status += f"Current_Pending_Sector:{current_pending_sector}"
        device_status += f"Offline_Uncorrectable:{offline_uncorrectable}"

    # check temperature
    if temperature > critical_temp:
        return_status = 2
        device_status += f"CRITICAL: device temperature ({temperature})"
        device_status += f"exceeds critical temperature "
        device_status += f"threshold ({critical_temp})"
    elif temperature > warning_temp:
        # don't downgrade return status!
        if return_status < 2:
            return_status = 1
        device_status += f"WARNING: device temperature ({temperature})"
        device_status += f"exceeds warning temperature "
        device_status += f"threshold ({warning_temp})"

    # check error count
    if error_count > 0:
        if return_status < 2:
            return_status = 1
        device_status += f"WARNING: error count {error_count}"

    if return_status == 0:
        # no warnings or errors, report everything is ok
        device_status = "OK: device is functional and stable"
        device_status += f" (temperature: {temperature})"

    return (return_status, device_status)


def vprint(level, text):
    """Verbosity print.

    Decide according to the given verbosity level if the message will be
    printed to stdout.
    """
    if level <= verbosity:
        print(text)


if __name__ == "__main__":
    # pylint: disable=invalid-name
    (options, args) = parse_cmd_line(sys.argv)
    verbosity = options.verbosity

    check_smartmontools(_smartctl_path)

    vprint(2, "Get device name")
    # assemble device list to be monitored
    if not options.alldisks:
        devices = [options.device]
    else:
        devices = []
        # Regex for Valid device name
        valid_device_name = '/dev/[ahsv]d.*'
        for partition in psutil.disk_partitions():
            if re.search(valid_device_name, partition.device):
                devices.append(partition.device.strip(partition.device[-1]))
        vprint(1, f"Devices: {devices}")

    return_text = ""
    exit_status = 0
    for device in devices:
        vprint(1, f"Device: {device}")
        return_text += f"{device}: "

        # check if we can access 'path'
        vprint(2, "Check device")
        (return_status, message) = check_device_permissions(device)
        if return_status != 0:
            if exit_status < return_status:
                exit_status = return_status
                return_text += message
            continue

        # call smartctl and parse output
        vprint(2, "Call smartctl")
        return_status, output, message = call_smartmontools(
            _smartctl_path,
            device)
        if return_status != 0:
            if exit_status < return_status:
                exit_status = return_status
            return_text += message
        if output != "":
            vprint(2, "Parse smartctl output")
            return_status, device_status = parse_output(
                output,
                options.warning_temp,
                options.critical_temp)
            if exit_status < return_status:
                exit_status = return_status
            return_text += device_status

    print(return_text)
    sys.exit(exit_status)

