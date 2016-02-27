#!/usr/bin/python2.7

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
from optparse import OptionParser

__author__ = "fuller <fuller@daemogorgon.net>"
__version__ = "$Revision$"


# path to smartctl
# TODO use which to fetch path
_smartctlPath = "/usr/sbin/smartctl"

# application wide verbosity (can be adjusted with -v [0-3])
_verbosity = 0

failedDisks = []


def parseCmdLine(args):
    """Commandline parsing."""

    usage = "usage: %prog [options] device"
    version = "%%prog %s" % (__version__)

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
        dest="warningThreshold",
        default=55,
        help="set temperature warning threshold to given temperature (default:55)")
    parser.add_option(
        "-c",
        "--critical-threshold",
        metavar="TEMP",
        action="store",
        type="int",
        dest="criticalThreshold",
        default="60",
        help="set temperature critical threshold to given temperature (default:60)")

    return parser.parse_args(args)


def checkDevice(path):
    """Check if device exists and permissions are ok.

    Returns:
        - 0 ok
        - 1 no such device
        - 2 no read permission given
    """
    vprint(3, "Check if %s does exist and can be read" % path)
    if not os.access(path, os.F_OK):
        return (1, "UNKNOWN: no such device found")
    elif not os.access(path, os.R_OK):
        return (2, "UNKNOWN: no read permission given")
    else:
        return (0, "")
    return (0, "")


def checkSmartMonTools(path):
    """Check if smartctl is available and can be executed.

    Returns:
        - 0 ok
        - 1 no such file
        - 2 cannot execute file
    """

    vprint(3, "Check if %s does exist and can be read" % path)
    if not os.access(path, os.F_OK):
        return (1, "UNKNOWN: cannot find %s" % path)
    elif not os.access(path, os.X_OK):
        return (2, "UNKNOWN: cannot execute %s" % path)
    else:
        return (0, "")


def callSmartMonTools(path, device):
    # get health status
    cmd = "%s -H %s" % (path, device)
    vprint(3, "Get device health status: %s" % cmd)
    # TODO start using subprocess - popen is deprecated as far as I know
    (child_stdin, child_stdout, child_stderr) = os.popen3(cmd)
    line = child_stderr.readline()
    if len(line):
        return (3, "UNKNOWN: call exits unexpectedly (%s)" % line, "",
                "")
    healthStatusOutput = ""
    for line in child_stdout:
        healthStatusOutput = healthStatusOutput + line

    # get temperature and sector status
    cmd = "%s -A %s" % (path, device)
    vprint(3, "Get device sector and temperature status: %s" % cmd)
    (child_stdin, child_stdout, child_stderr) = os.popen3(cmd)
    line = child_stderr.readline()
    if len(line):
        return (3, "UNKNOWN: call exits unexpectedly (%s)" % line, "", "")

    temperatureOutput = ""
    id5Output = ""
    id196Output = ""
    id197Output = ""
    id198Output = ""
    for line in child_stdout:
        id5Output = id5Output + line
        id196Output = id196Output + line
        id197Output = id197Output + line
        id198Output = id198Output + line
        temperatureOutput = temperatureOutput + line
    return (
        0,
        "",
        healthStatusOutput,
        temperatureOutput,
        id5Output,
        id196Output,
        id197Output,
        id198Output,
        device)

def parseOutput(
        healthMessage,
        temperatureMessage,
        id5Message,
        id196Message,
        id197Message,
        id198Message,
        device):
    """Parse smartctl output

    Returns (health status, temperature, sector status).
    """
    # parse health status
    #
    # look for line '=== START OF READ SMART DATA SECTION ==='
    statusLine = ""
    lines = healthMessage.split("\n")
    getNext = False
    for line in lines:
        if getNext:
            statusLine = line
            break
        elif "===" in line:
            getNext = True
    parts = statusLine.rstrip().split()
    healthStatus = parts[-1:]
    vprint(3, "Health status: %s" % healthStatus)

    # parse Reallocated_Sector_Ct
    id5Line = 0
    lines = id5Message.split("\n")
    for line in lines:
        parts = line.split()
        if len(parts):
            # 5 is the reallocated_sector_ct id
            if parts[0] == "5":
                id5Line = int(parts[9])
                break
    vprint(3, "Reallocated_Sector_Ct: %d" % id5Line)

    # parse temperature attribute line
    temperature = 0
    lines = temperatureMessage.split("\n")
    for line in lines:
        parts = line.split()
        if len(parts):
            # 194 is the temperature value id
            if parts[0] == "194":
                temperature = int(parts[9])
                break
    vprint(3, "Temperature: %d" % temperature)

    # parse Reallocated_Event_Count
    id196Line = 0
    lines = id196Message.split("\n")
    for line in lines:
        parts = line.split()
        if len(parts):
            # 196 is the reallocated_event_count id
            if parts[0] == "196":
                id196Line = int(parts[9])
                break
    vprint(3, "Reallocated_Event_Count: %d" % id196Line)

    # parse Current_Pending_Sector
    id197Line = 0
    lines = id197Message.split("\n")
    for line in lines:
        parts = line.split()
        if len(parts):
            # 197 is the current_pending_sector id
            if parts[0] == "197":
                id197Line = int(parts[9])
                break
    vprint(3, "Current_Pending_Sector: %d" % id197Line)

    # parse Offline_Uncorrectable
    id198Line = 0
    lines = id198Message.split("\n")
    for line in lines:
        parts = line.split()
        if len(parts):
            # 198 is the offline_uncorrectable id
            if parts[0] == "198":
                id198Line = int(parts[9])
                break
    vprint(3, "Offline_Uncorrectable: %d" % id198Line)
    return (
        healthStatus,
        temperature,
        id5Line,
        id196Line,
        id197Line,
        id198Line,
        device)


def createReturnInfo(
        healthStatus,
        temperature,
        id5Line,
        id196Line,
        id197Line,
        id198Line,
        warningThreshold,
        criticalThreshold,
        device):
    """Create return information according to given thresholds."""
    # this is absolutely critical!
    # print healthStatus
    if healthStatus[0] != "PASSED":
        return (2, "CRITICAL: device does not pass health status ", device)
    # check sectors
    # print "id5Line : %s, id196Line:%s, id197Line:%s, id198Line:%s, device:%s" % (id5Line, id196Line, id197Line, id198Line, device)
    if id5Line > 0 or id196Line > 0 or id197Line > 0 or id198Line > 0:
        return (2, "CRITICAL: there is a problem with bad sectors on the drive. Reallocated_Sector_Ct:%d,Reallocated_Event_Count:%d,Current_Pending_Sector:%d,Offline_Uncorrectable:%d" % ( id5Line, id196Line, id197Line, id198Line ) , device )
    if temperature > criticalThreshold:
        return (2, "CRITICAL: device temperature (%d) exceeds critical temperature threshold (%s) " % (temperature, criticalThreshold), device)
    elif temperature > warningThreshold:
        return (1, "WARNING: device temperature (%d) exceeds warning temperature threshold (%s) " % ( temperature, warningThreshold), device)
    else:
        return (0, "OK: device  is functional and stable (temperature: %d) " % ( temperature), device)


def exitWithMessage(value, message):
    """Exit with given value and status message."""
    vprint(1,message)
#    sys.exit(value)
    pass

def vprint(level, message):
    """Verbosity print.

    Decide according to the given verbosity level if the message will be
    printed to stdout.
    """
    if level <= verbosity:
        print message


validPartitions = []

#Regex for Valid device name
reValidDeviceName = '/dev/[hsv]da*'

for partition in psutil.disk_partitions():
    if re.search(reValidDeviceName, partition.device):
        validPartitions.append(partition.device.strip(partition.device[-1]))


if __name__ == "__main__":
    # pylint: disable=invalid-name
    (options, args) = parseCmdLine(sys.argv)
    verbosity = options.verbosity

    vprint(1, "Valid Partitions are %s" % validPartitions)
    (value, message) = checkSmartMonTools(_smartctlPath)
    if value != 0:
        exitWithMessage(3, message)

    vprint(2, "Get device name")

    if not options.alldisks:
        devices = list(options.device)
    else:
        devices = validPartitions

    for device in devices:
        vprint(1, "Device: %s" % device)

        # check if we can access 'path'
        vprint(2, "Check device")
        (value, message) = checkDevice(device)
        if value != 0:
            exitWithMessage(3, message)

        # call smartctl and parse output
        vprint(2, "Call smartctl")
        (
            value,
            message,
            healthStatusOutput,
            temperatureOutput,
            id5Output,
            id196Output,
            id197Output,
            id198Output,
            device) = callSmartMonTools(_smartctlPath, device)
        if value != 0:
            exitWithMessage(value, message)
        vprint(2, "Parse smartctl output")
        (
            healthStatus,
            temperature,
            id5Line,
            id196Line,
            id197Line,
            id198Line,
            device) = parseOutput(
                healthStatusOutput,
                temperatureOutput,
                id5Output,
                id196Output,
                id197Output,
                id198Output,
                device)
        vprint(2, "Generate return information")
        (value, message, device) = createReturnInfo(
            healthStatus,
            temperature,
            id5Line,
            id196Line,
            id197Line,
            id198Line,
            options.warningThreshold,
            options.criticalThreshold,
            device)
        if value == 2:
            failedDisks.append(device)

        exitWithMessage(value, message + device)

    if len(failedDisks) > 0:
        print "Critical. Following disks are in bad state : %s" % (failedDisks)
        exit(2)
    elif len(failedDisks) == 0:
        print "OK. All disks are fine."
        exit(0)
