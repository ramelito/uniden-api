#!/usr/bin/python


import yaml
import argparse

from scanner.uniden import *

#sys_index=15817 # change to option
#grp_index=15822 # change to option

parser = argparse.ArgumentParser()
parser.add_argument('--dev', type=str, default='/dev/ttyUSB0')
parser.add_argument('--speed', type=str, default='57600')
parser.add_argument('--sys-index', type=str, required=True)
parser.add_argument('--grp-index', type=str)
parser.add_argument('--grp-config', type=str, default='examples/grp_conv.yml')
parser.add_argument('--chn-config', type=str, default='examples/chn.yml')
args=parser.parse_args()

s=scanner.UnidenScanner(args.dev,args.speed)
if not s.get_scan_settings(): print "get_scan_settings() returned 0"
sd=s.systems[args.sys_index].dump() #dump data to temp var
sd['groups']=[] # zeroize group list, now this list for new grp only
groups=yaml.load(file(args.grp_config,'r'))
sd['groups']=groups # assign new groups
s.enter_program_mode() # do not forget to enter program mode
s.systems[args.sys_index].load(**sd) # update data in memory
s.systems[args.sys_index].set_data() # commit data to scanner
s.systems[args.sys_index].get_data() # update data from scanner

if args.grp_index and args.chn_config:
	gd=s.systems[args.sys_index].groups[args.grp_index].dump() #dump data to temp var
	gd['channels']=[] # zeroize channel list, now this list for new chn only
	channels=yaml.load(file(args.chn_config,'r')) 
	gd['channels']=channels # assign new channels
	s.systems[args.sys_index].groups[args.grp_index].load(**gd) # update data in memory
	s.systems[args.sys_index].groups[args.grp_index].set_data() # commit data to scanner
	s.systems[args.sys_index].groups[args.grp_index].get_data() # update data from scanner

s.exit_program_mode()
