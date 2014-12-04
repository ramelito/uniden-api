#!/usr/bin/python
# -*- coding: utf-8 -*-
#
#
# Uniden Scanner Python API
# Copyright (C) 2014-2015 Anton Komarov
#
# This program is free software; you can redistribute it and/or modify it under the terms of the GNU General Public License 
# as published by the Free Software Foundation; either version 2 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty 
# of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with this program; 
# if not, write to the Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA

import yaml
import time
import serial
import logging
from constants import *

# create logger
module_logger = logging.getLogger('uniden_api')
	
def zero_to_head(t):

	l=list(t)
	if len(l)<>10: return tuple(l)
	l.insert(0,l[9])
	l.pop(10)
		
	return tuple(l)

def zero_to_tail(t):

	l=list(t)
	if len(l)<>10: return tuple(l)
	l.insert(9,l[0])
	l.pop(0)
		
	return tuple(l)

def frq_to_scanner(f):

	module_logger.debug('frq_to_scanner(): f=%s' % f)
	if f=='' or f==0: return f

	l,r=str(f).split('.')
	l=l.rjust(4,'0')
	r=r.ljust(4,'0')
	module_logger.debug('frq_to_scanner(): l=%s,r=%s' % (l,r))
	
	return ''.join([l,r])

def frq_from_scanner(f):

	f=str(float(f)/10000)
	l,r=f.split('.')
	r=r.ljust(4,'0')

	return '.'.join([l,r])
	

class UnidenScanner:

	err_list=('NG','ORER','FER','ERR','')

	def __init__(self, port, speed="115200"):

		self.logger = logging.getLogger('uniden_api.UnidenScanner')
		self.logger.info('initialiazing with port=%(port)s and speed=%(speed)s' % locals())		

		self.serial=None
		self.model=None
		self.version=None
		self.isProgramMode=False
		self.system_index_head=None
		self.system_index_tail=None
		self.settings=Settings(self)
		self.quick_lockout=()
		self.systems={}
		self.searches=Search(self)
		self.free_memory_block=None
		self.used_memory_block={}
		self.default_band_coverage = ()

		self.open(port, speed)
		#self.exit_program_mode()
		#self.get_model()
		#self.get_version()

	def open(self, port, speed):

		"""Open scanner method, accepts port and speed, timeout is set for 100ms"""
		
		try:
			self.serial=serial.Serial(port,speed,timeout=0.1)

		except serial.SerialException:
			self.logger.error('Error opening serial port %s!' % port)

	def close(self):

		if self.serial.isOpen():
			self.serial.close()

	def __del__(self):

		self.close()


	def raw(self, cmd):

		"""Wrapper for raw scanner command"""

		f2='OK'

		self.logger.debug('raw(): cmd %s' % cmd)
		self.serial.write("".join([cmd,'\r']))

		res = (self.serial.readall()).strip('\r')
		self.logger.debug('raw(): res %s' % res)

		if res.count(',') == 1: 
			f2=res.split(',')[1]
		else:
			f2=res
	
		if f2 in self.err_list:
			raise CommandError
		else:
			return res

	def get_model(self):

		"""Returns Model Information."""

		try:
			res = self.raw('MDL')
		
		except CommandError:
			self.logger.error('get_model()')
			return 0

		(cmd,self.model)=res.split(",")

			
	def get_version(self):

		"""Returns Firmware Version."""

		try:
			res = self.raw('VER')

		except CommandError:
			self.logger.error('get_version()')
			return 0
		
		(cmd,self.version)=res.split(",")

	def get_rssi_power(self):

		"""Returns current RSSI level and its frequency.
		The order of the frequency digits is from 1 GHz digit to 100 Hz digit.
		
		RSSI		RSSI A/D Value (0-1023)
		FRQ		The order of the frequency digits is from 1 GHz digit to 100 Hz digit."""
	
		dict={}
	
		try:
			res = self.raw('PWR')

		except CommandError:
			self.logger.error('get_rssi_power()')
			return 0

		(cmd,rssi,frq)=res.split(",")
		dict={'rssi':rssi, 'frq':frq}

		return dict

	def get_reception_status(self):

		"""Get reception status.
		The Scanner returns GLG,,,,,,,,,[\r] until it detects a frequency or a TGID.
		FRQ/TGID	Frequency or TGID
		MOD		Modulation (AM/FM/NFM/WFM/FMB)
		ATT		Attenuation (0:OFF / 1:ON)
		CTCSS/DCS	CTCSS/DCS Status (0-231)
		NAME1		System, Site or Search Name
		NAME2		Group Name
		NAME3		Channel Name
		SQL		Squelch Status (0:CLOSE / 1:OPEN)
		MUT		Mute Status (0:OFF / 1:ON)
		SYS_TAG		Current system number tag (0-999/NONE)
		CHAN_TAG	Current channel number tag (0-999/NONE)
		P25NAC		P25 NAC Status ( 0-FFF: 0-FFF / NONE: Nac None)"""

		dict={}

		try:
			res = self.raw('GLG')
		
		except CommandError:
			self.logger.error('get_reception_status()')
			return 0

		(cmd,frq_tgid,mod,att,ctcss_dcs,name1,name2,name3,
	 	sql,mut,sys_tag,chan_tag,p25nac)=res.split(",")

		dict={'frq_tgid':frq_tgid, 'mod':mod, 'att':att,
			'ctcss_dcs':ctcss_dcs, 'name1':name1, 'name2':name2, 
			'name3':name3, 'sql':sql, 'mute':mut, 'sys_tag':sys_tag,
			'chan_tag':chan_tag, 'p25nac':p25nac}
			
		return dict

	def get_current_status(self):

		"""Returns current scanner status.
		DSP_FORM	Display Form (4 - 8dight:########) (each # is 0 or 1) 0 means Small Font / 1 means Large Font.
		Lx_CHAR		Linex Characters 16char (fixed length)
		Lx_MODE		Linex Display Mode 16char
		SQL 		Squelch Status (0:CLOSE / 1:OPEN)
		MUT 		Mute Status (0:OFF / 1:ON)
		BAT 		Battery Low Status (0:No Alert / 1:Alert)
		WAT		Weather Alert Status (0:No Alert / 1: Alert / $$$: Alert SAME CODE)
		SIG_LVL		Signal Level (0–5)
		BK_COLOR	Backlight Color (OFF,BLUE,RED,MAGENTA,GREEN,CYAN,YELLOW,WHITE)
		BK_DIMMER	Backlight Dimmer (0:OFF / 1:Low / 2:Middle / 3:High )"""

		dict={}

		try:
			res = self.raw('STS')
			
		except CommandError:
			self.logger.error('get_current_status()')
			return 0

		l=res.split(",")
		n=len(l[1])

		cm=l[2:n*2+1]
		while (len(cm)<17): cm.append('')

		dict={'dsp_form':l[0], 'char': tuple(cm[0::2]), 'mode': tuple(cm[1::2]), 
			'sql':l[-9], 'mut':l[-8], 'bat':l[-7], 'wat':l[-6], 'rsv1':l[-5],
			'rsv2':l[-4], 'sig_lvl':l[-3], 'bk_color':l[-2], 'bk_dimmer':l[-1]}

		return dict

	def push_key(self, mode, key):
	
		"""push_key method is used to push keys on the scanner
		
		Keys:
		 M : menu 
		 F : func 
		 H : hold 
		 S : scan/srch 
		 L : lo 
		 1 : 1 
		 2 : 2 
		 3 : 3 
		 4 : 4 
		 5 : 5 
		 6 : 6 
		 7 : 7 
		 8 : 8 
		 9 : 9 
		 0 : 0 
		 .(dot) : dot/no/pri 
		 E : E/yes/gps 
		 > : vright * Set "P" to KEY_MODE. 
		 < : vleft * Set "P" to KEY_MODE. 
		 ^ : vpush 
		 P : pwr/light/lock

		Modes:
		 P : press 
		 L : long (press)
		 H : hold (Press and Hold until Release receive) 
		 R : release (Cancel Hold state)"""

		keys = { "menu":"M", "func":"F", "hold":"H", "scan":"S", "srch":"S", 
			 "lo":"L", "1":"1", "2":"2", "3":"3", "4":"4", "5":"5",
			 "6":"6", "7":"7", "8":"8", "9":"9", "0":"0", "dot":".",
			 "no":".", "pri":".", "E":"E", "yes":"E", "gps":"E", "pwr":"P",
			 "vright":">", "vleft":"<", "vpush":"^", "lock":"P", "light":"P" }

		modes = { "press":"P", "long":"L", "hold":"H", "release":"R" }

		try:
			cmd = ",".join(['KEY',keys[key],modes[mode]])
		except KeyError:
			self.logger.error('Wrong key %(key)s or mode %(mode)s' % locals())
			return 0

		try:
			res = self.raw(cmd)
		
		except CommandError:
			self.logger.error('push_key(): %s' % cmd)
			return 0

	def set_quick_search_hold(self, frq, mod="AUTO", att=0, dly=2,
					code_srch=0, bsc="0000000000000000",
					rep=0, agc_analog=0, agc_digital=0,
					p25waiting=200):

		"""This command is invalid when the scanner is in Menu Mode, during Direct Entry operation,
		during Quick Save operation.
		FUNCTION
		UASD specifies arbitrary frequency and changes to Quick Search Hold (VFO) mode.
		Parameter, such as STP, changes the contents of Srch/CloCall option.
		Note: Even when only [FRQ] parameter is set, this command will work.

		FRQ		Frequency (The right frequency)
		MOD		Modulation (AUTO/AM/FM/NFM/WFM/FMB)
		ATT		Attenuation (0:OFF / 1:ON)
		DLY		Delay Time (-10,-5,-2,0,1,2,5,10,30)
		CODE_SRCH	CTCSS/DCS/P25 NAC Search (0:OFF / 1: CTCSS/DCS / 2: P25 NAC Search)
		BSC		Broadcast Screen (16digit: ########・・#)
		(each # is 0 or 1)                         ||||||||・・+- Band10
		0 means OFF				   ||||||||       :
		1 means ON 				   |||||||+---- Band 2
		                                           ||||||+----- Band 1
		                                           |||||+------ Reserve
		                                           ||||+------- NOAA WX
		                                           |||+-------- VHF TV
		                                           ||+--------- UHF TV
		                                           |+---------- FM
		                                           +----------- Pager
		REP		Repeater Find (0:OFF / 1:ON)
		AGC_ANALOG	AGC Setting for Analog Audio (0:OFF / 1:ON)
		AGC_DIGITAL	AGC Setting for Digital Audio (0:OFF / 1:ON)
		P25WAITING	P25 Waiting time (0,100,200,300, .... , 900,1000) ms"""

		rsv=''

		frq=''.join([frq.split('.')[0].rjust(4,'0'),
			 frq.split('.')[1].ljust(4,'0')])

		if mod not in mod_values:
			raise ModulationError

		if (len(bsc)<>16 or len(bsc.replace('0','').replace('1',''))):
			raise BScreenError

		cmd=",".join(['QSH',frq,rsv,mod,str(att),str(dly),rsv,str(code_srch),bsc,str(rep),
					rsv,str(agc_analog),str(agc_digital),str(p25waiting)])

		try:
			res = self.raw(cmd)

		except CommandError:
			self.logger.error('set_quick_search_hold(): %s' % cmd)
			return 0

		return 1

	def set_curfrq_reception_status(self, frq, mod="AUTO", att=0, dly=2,
					code_srch=0, bsc="0000000000000000",
					rep=0, agc_analog=0, agc_digital=0,
					p25waiting=200):

		"""Set current frequency and get reception status.
		see set_quick_search_hold() for vars value descriptions."""

		rsv=''

		frq=''.join([frq.split('.')[0].rjust(4,'0'),
			 frq.split('.')[1].ljust(4,'0')])

		if mod not in mod_values:
			raise ModulationError

		if (len(bsc)<>16 or len(bsc.replace('0','').replace('1',''))):
			raise BScreenError

		cmd=",".join(['QSC',frq,rsv,mod,str(att),str(dly),rsv,str(code_srch),bsc,str(rep),
					rsv,str(agc_analog),str(agc_digital),str(p25waiting)])

		try:
			res = self.raw(cmd)

		except CommandError:
			self.logger.error('set_curfrq_reception_status(): %s' % cmd)
			return 0

		(cmd,rssi,frq,sql) = res.split(",")

		return (rssi,frq,sql)

	def get_volume(self):

		"""Get Volume Level Settings

		LEVEL		Volume Level ( 0 - 15 )"""

		try:
			res = self.raw('VOL')

		except CommandError:
			self.logger.error('get_volume()')
			return 0

		(cmd,vol) = res.split(",")
		return vol

	def set_volume(self, vol):

		"""Set Volume Level Settings

		LEVEL		Volume Level ( 0 - 15 )"""

		cmd=",".join(['VOL',str(vol)])

		try:
			res = self.raw(cmd)

		except CommandError:
			self.logger.error('set_volume(): cmd %s' % cmd)
			return 0

		return 1 
			
	def get_squelch(self):

		"""Get Squelch Level Settings

		LEVEL	Squelch Level (0:OPEN / 1-14 / 15:CLOSE)"""

		try:
			res = self.raw('SQL')

		except CommandError:
			self.logger.error('get_squelch()')
			return 0

		(cmd,sql) = res.split(",")

		return sql

	def set_squelch(self, sql):

		"""Set Squelch Level Settings

		LEVEL	Squelch Level (0:OPEN / 1-14 / 15:CLOSE)"""

		cmd=",".join(['SQL',str(sql)])

		try:
			res = self.raw(cmd)

		except CommandError:
			self.logger.error('set_squelch(): cmd %s' % cmd)
			return 0

		return 1

	def get_apco_data_settings(self):

		"""Get APCO Data Settings
		
		ERR_RATE		Error Rate (from 0 to 99)"""

		try:
			res = self.raw('P25')

		except CommandError:
			self.logger.error('get_apco_data_settings()')
			return 0

		(cmd,rsv1,rsv2,err_rate) = res.split(",")

		return err_rate

	def set_apco_data_settings(self, p25):

		"""Set APCO Data Settings
		
		ERR_RATE		Error Rate (from 0 to 99)"""

		rsv=''
		cmd=",".join(['P25',rsv,rsv,str(p25)])

		try:
			res = self.raw(cmd)

		except CommandError:
			self.logger.error('set_apco_data_settings(): %s' % cmd)
			return 0

		return 1

	def jump_number_tag(self, sys_tag='NONE', chan_tag='NONE'):

		"""When both [SYS_TAG] and [CHAN_TAG] are set as blank, scanner returns error.
		When [SYS_TAG] is set as blank, [CHAN_TAG] is set with a number tag, scanner jump to
		the channel number tag in current system.
		When [SYS_TAG] is set with a number tag, [CHAN_TAG] is set as blank, scanner jump to
		the first channel of the system number tag.

		SYS_TAG		System Number Tag (0-999/NONE)
		CHAN_TAG	Channel Number Tag (0-999/NONE)"""

		cmd=",".join(['JNT',str(sys_tag),str(chan_tag)])

		try:
			res = self.raw(cmd)

		except CommandError:
			self.logger.error('jump_number_tag(): %s' % cmd)
			return 0

		return 1

	def get_battery_voltage(self):

		"""A/D Value (0-1023)
		Battery Level[V] = (3.2[V] * #### * 2 )/1023"""

		try:
			res = self.raw('BAV')

		except CommandError:
			self.logger.error('get_battery_voltage()')
			return 0

		(bav,ad_value) = res.split(',')

		return 3.2*float(ad_value)*2/1023

	def get_window_voltage(self):

		"""A/D Value (0-255)
		Returns current window voltage and its frequency.
		The order of the frequency digits is from 1 GHz digit to 100 Hz digit."""

		try:
			res = self.raw('WIN')

		except CommandError:
			self.logger.error('get_window_voltage()')
			return 0

		(win,ad_value,frq) = res.split(',')

		return (ad_value,frq)

	def enter_program_mode(self):

		"""This command is invalid when the scanner is in Menu Mode, during Direct Entry operation,
		during Quick Save operation.

		The scanner goes to Program Mode.
		The scanner displays "Remote Mode" on first line and "Keypad Lock" on second line in
		Program Mode."""

		try:
			res = self.raw('PRG')

		except CommandError:
			self.logger.error('enter_program_mode()')
			return 0

		self.isProgramMode=True

		return 1


	def exit_program_mode(self):

		"""The scanner exits from Program Mode.
		Then the scanner goes to Scan Hold Mode."""

		try:
			res = self.raw('EPG')

		except CommandError:
			self.logger.error('exit_program_mode()')
			return 0

		self.isProgramMode=False

		return 1

	def get_free_memory_blocks(self):

		"""Returns the number of idle(free) memory block.
		##### (not zero-padding)"""

		try:
			res = self.raw('RMB')

		except CommandError:
			self.logger.error('get_free_memory_blocks()')
			return 0

		(rmb,self.free_memory_blocks) = res.split(',')

		return 1

	def get_used_memory_blocks(self):

		"""MEMORY_USED		The percent of memory that is used (0 - 100)
		SYS			The number of systems that is created (0 - 500)
		SITE			The number of sites that is created (0 - 1000)
		CHN			The number of channels that is created (0 – 25000)
		LOC			The number of location system that is created (0 – 1000)"""

		try:
			res = self.raw('MEM')

		except CommandError:
			self.logger.error('get_used_memory_blocks()')
			return 0

		(rmb,memory_used,sys,site,chn,loc) = res.split(',')

		self.used_memory_blocks={'memory used':memory_used,
			'systems':sys, 'sites':site, 'channels':chn, 
			'locations':loc}

		return 1

	def get_default_band_coverage(self):

		"""BNAD_NO		Band No (1-31) Band number of band coverage
		STP			Search Step
		                        500: 5k 625: 6.25k 750: 7.5 k
		                        833: 8.33k 1000 : 10k 1250 : 12.5k
		                        1500 : 15k 2000 : 20k 2500 : 25k
		                        5000 : 50k 10000 : 100k
		MOD			Modulation (AM / NFM / FM / WFM / FMB)"""

		dfb = [0]

		for no in range(1,32):
			try:
				res = self.raw(','.join(['DBC',str(no)]))

			except CommandError:
				self.logger.error('get_default_band_coverage()')
				return 0
		
			(dbc,step,mod) = res.split(',')

			dfb.append({'step':step, 'mod':mod})

		self.default_band_coverage = tuple(dfb)

		return 1

	def get_system_settings(self):

		"""Enters program mode and gets scanner settings data."""

		if not self.isProgramMode: self.enter_program_mode()

		self.settings.get_data()

		self.exit_program_mode()

		return 1

	def get_scan_settings(self):

		"""Enters program mode and gets scanner scan settings data recursively.""" 

		if not self.isProgramMode: self.enter_program_mode()

		try:
			sih = self.raw('SIH')
			sit = self.raw('SIT')

		except CommandError:
			self.logger.error('get_scan_settings(): failed to get head/tail.')
			return 0

		(sih,self.system_index_head) = sih.split(',')
		(sit,self.system_index_tail) = sit.split(',')

		sys_index = self.system_index_head

		while int(sys_index) <> -1:

			s=System(self,sys_index)
			s.get_data()
			self.systems[sys_index]=s
			sys_index=s.fwd_index

		try:
			res = self.raw('QSL')

		except CommandError:
			self.logger.error('get_scan_settings(): failed to get quick system lockout list.')
			return 0

		(qsl,p0,p1,p2,p3,p4,p5,p6,p7,p8,p9) = res.split(',')
	
		l=[tuple(p0),tuple(p1),tuple(p2),tuple(p3),
		   tuple(p4),tuple(p5),tuple(p6),tuple(p7),
		   tuple(p8),tuple(p9)]

		self.quick_lockout=tuple(map(zero_to_head,l))

		if not self.exit_program_mode(): return 0

		return 1

	def set_scan_settings(self):

		"""Enters program mode and sets scan settigns to scanner recursively."""

		if not self.isProgramMode: self.enter_program_mode()

		l=list(self.quick_lockout)
		l=(map(zero_to_tail,l))
		l=[''.join(t) for t in l]
		pages=','.join(l)
		cmd=','.join(['QSL',pages])
	
		try:
			res = self.raw(cmd)

		except CommandError:
			self.logger.error('set_scan_settings(): failed to set quick system lockout list.')
			return 0

		for system in self.systems.values(): system.set_data()

		if not self.exit_program_mode(): return 0

		return 1

	def dump_system_settings(self):

		"""Returns YAML formatted text of scanner settings."""

		return yaml.dump(self.settings.dump())

	def load_system_settings(self,fname):

		"""Load YAML formatted text to memory.
		It is up to user to set data into scanner.
		See sample YAML file in examples."""

		settings=yaml.load(file(fname, 'r'))

		self.settings.load(**settings)

		return 1

	def dump_scan_settings(self):

		"""Returns YAML formatted text of scanner scan settings."""

		systems=[]
		for i in self.systems: systems.append(self.systems[i].dump())

		s=yaml.dump(systems)

		return s

	def load_scan_settings(self,fname):

		"""Load YAML formatted text to memory.
		It is up to user to set data into scanner.
		See sample YAML file in examples."""

		stream = file(fname, 'r')
		systems=yaml.load(stream)
	
		for sys in systems:

			try:
                		sys_type = scanner_sys_type[sys['type']]
				protected = scanner_onoff[sys['protected']]

			except KeyError:
				self.logger.error('load_scan_settings(): type or protect flag are missing.')
				continue

			i=self.create_system(sys_type,protected)
			if i==0: continue
			self.systems[i].load(**sys)		
		
	def create_system(self, sys_type='CNV', protect=0):

		"""Creates system instance in scanner memory and returns system index."""

		cmd = ','.join(['CSY',sys_type,str(protect)])

		try:
			res = self.raw(cmd)

		except CommandError:
			self.logger.error('create_system(): %s' % cmd)
			return 0

		(csy,sys_index) = res.split(',')
		if sys_index == -1: return 0
		s=System(self,sys_index)
		self.systems[sys_index]=s
		
		return sys_index

	def delete_system(self, sys_index):

		"""Deletes system in scanner memory by system index."""
		
		cmd = ','.join(['DSY',sys_index])

		try:
			res = self.raw(cmd)

		except CommandError:
			self.logger.error('delete_system(): %s' % cmd)
			return 0

		self.systems.pop(sys_index)

		return 1

	def get_search_settings(self):

		"""Enters program mode and gets scanner search settings data recursively.""" 

		if not self.isProgramMode: self.enter_program_mode()

		self.searches.get_data()

		self.exit_program_mode()

		return 1

	def set_search_settings(self):

		"""Enters program mode and gets scanner search settings data recursively.""" 

		if not self.isProgramMode: self.enter_program_mode()

		self.searches.set_data()

		self.exit_program_mode()

		return 1

	def dump_search_settings(self):

                """Returns YAML formatted text of scanner settings."""

                return yaml.dump(self.searches.dump())

	def load_search_settings(self, fname):

                """Load YAML formatted text to memory.
                It is up to user to set data into scanner.
                See sample YAML file in examples."""

                searches=yaml.load(file(fname, 'r'))

                self.searches.load(**searches)

                return 1

	#TODO 2nd queue
	def get_localtion_settings(self):pass
	def get_weather_settings(self):pass
	

class UnidenScannerError(Exception): pass

class CommandError(UnidenScannerError): pass

class ModulationError(UnidenScannerError): pass

class BScreenError(UnidenScannerError): pass

class Settings:

	"""Scanner Settings class."""

	def __init__(self, scanner):
	
		self.logger = logging.getLogger('uniden_api.Settings')

		self.scanner = scanner
		self.backlight={}
		self.battery_info={}
		self.com_port={}
		self.key_beep={}
		self.opening_message=[]
		self.priority_mode={}
		self.auto_gain_control={}
		self.system_count={}
		self.lcd_contrast={}
		self.scanner_option={} 

	def get_data(self):

		"""Get following scanner settings:

		Backlight		EVENT IF=INFINITE,10=10sec,30=30sec,KY=KEYPRESS,SQ=SQUELCH
		                        COLOR BLUE,RED,MAGENTA,GREEN,CYAN,YELLOW,WHITE
		                        DIMMER Backlight Dimmer (1:Low / 2:Middle / 3:High)
		Battery Info		BAT_SAVE Battery Save (0:OFF / 1:ON)
		           		CHARGE_TIME Battery Charge Time (1-16)
		COM port		BAUDRATE OFF,4800,9600,19200,38400,57600,115200
		                        When receive “COM,OK”, next command should not be send in 2 second.
		                        Only PC Control (Baud Rate) does not become an initial-setting value.
		Key Beep		LEVEL Beep Level (0:Auto / 1-15 / 99:OFF)
					LOCK Key Lock status (0:OFF / 1:ON)
		                        SAFE Key Safe status (0:OFF / 1:ON)
		Opening Message		Lx_CHAR LineX Characters (max.16char), X=1..4
		Priority Mode		PRI_MODE Priority Setting (0:OFF / 1:ON / 2:PLUS ON)
		                        MAX_CHAN Priority Scan max channels at once (1-100)
		                        INTERVAL Priority Scan Interval time (1-10)
		Auto Gain Control	A_RES Analog Response Time (-4 - +6)
		                        A_REF Analog Reference Gain (-5 - +5)
		                        A_GAIN Analog Gain Range ( 0 - 15)
		                        D_RES Digital Response Time (-8 - +8)
		                        D_GAIN Digital Reference Gain (-5 - +5)
		System Count		### (0 - 500)
		LCD Contrast		CONTRAST LCD Contrast (1 - 15)
		Scanner Option		DISP_MODE DISPPALY MODE ( 1:MODE1 / 2:MODE2 / 3:MODE3 )
		                        CH_LOG Control Channel Logging ( 0:OFF / 1:ON / 2:Extend )
		                        G_ATT Global attenuator ( 0: OFF / 1: ON )
		                        P25_LPF P25 Low Pass Filter ( 0: OFF / 1: ON )
		                        DISP_UID Display Unit ID ( 0: OFF / 1: ON )"""

		try:
			blt = self.scanner.raw('BLT')
			bsv = self.scanner.raw('BSV')
			com = self.scanner.raw('COM')
			kbp = self.scanner.raw('KBP')
			oms = self.scanner.raw('OMS')
			pri = self.scanner.raw('PRI')
			agv = self.scanner.raw('AGV')
			sct = self.scanner.raw('SCT')
			cnt = self.scanner.raw('CNT')
			scn = self.scanner.raw('SCN')

		except CommandError:
			self.logger.error('get_data()')
			return 0

		(blt,event,color,dimmer) = blt.split(',')
		self.backlight = {'event':event, 'color':color, 
							'dimmer':dimmer}
		(bsv,bat_save,charge_time) = bsv.split(',')
		self.battery_info = {'bat_save':bat_save, 
						'charge_time':charge_time}
		(com,baudrate,csv) = com.split(',')
		self.com_port = {'baudrate':baudrate}
		(kbp,level,lock,safe) = kbp.split(',')
		self.key_beep = {'level':level, 'lock':lock, 'safe':safe}
		(oms,l1_char,l2_char,l3_char,l4_char) = oms.split(',')
		self.opening_message = [0, l1_char, l2_char, l3_char, l4_char]
		(pri,pri_mode,max_chan,interval) = pri.split(',')
		self.priority_mode = {'pri_mode':pri_mode, 'max_chan':max_chan, 
								'interval':interval}
		(agv,rsv1,rsv2,a_res,a_ref,a_gain,d_res,d_gain) = agv.split(',')
		self.auto_gain_control={'a_res':a_res, 'a_ref':a_ref, 'a_gain':a_gain,
								'd_res':d_res, 'd_gain':d_gain}
		(sct,n) = sct.split(',')
		self.system_count={'n':n}
		(cnt,contrast) = cnt.split(',')
		self.lcd_contrast={'contrast':contrast}
		(scn,disp_mode,rsv1,ch_log,g_att,rsv2,p25_lpf,disp_uid,rsv3,rsv4,rsv5,
			rsv6,rsv7,rsv8,rsv9,rsv10,rsv11,rsv12,rsv13,rsv14,rsv15,rsv16) = scn.split(',')
		self.scanner_option={'disp_mode':disp_mode, 'ch_log':ch_log, 
						'g_att':g_att, 'p25_lpf':p25_lpf, 'disp_uid':disp_uid}

		return 1

	def set_data(self):

		"""Set scanner settings data to device."""

		rsv = ''
		if self.backlight: blt = ','.join(['BLT',str(self.backlight['event']),self.backlight['color'],
				str(self.backlight['dimmer'])])
		if self.battery_info: bsv = ','.join(['BSV',str(self.battery_info['bat_save']), 
				str(self.battery_info['charge_time'])])
		if self.com_port: com = ','.join(['COM',self.com_port['baudrate'],rsv])
		if self.key_beep: kbp = ','.join(['KBP',str(self.key_beep['level']),str(self.key_beep['lock']),
						str(self.key_beep['safe'])])
		if self.opening_message: oms = ','.join(['OMS',self.opening_message[1],self.opening_message[2],
						self.opening_message[3],self.opening_message[4]])
		if self.priority_mode: pri = ','.join(['PRI',str(self.priority_mode['pri_mode']), 
						str(self.priority_mode['max_chan']),
						str(self.priority_mode['interval'])])
		if self.auto_gain_control: agv = ','.join(['AGV',rsv,rsv,str(self.auto_gain_control['a_res']),
							str(self.auto_gain_control['a_ref']),
							str(self.auto_gain_control['a_gain']),
							str(self.auto_gain_control['d_res']),
							str(self.auto_gain_control['d_gain'])])
		if self.lcd_contrast: cnt = ','.join(['CNT', str(self.lcd_contrast['contrast'])])
		if self.scanner_option: scn = ','.join(['SCN', str(self.scanner_option['disp_mode']),rsv,
				str(self.scanner_option['ch_log']),str(self.scanner_option['g_att']),
				rsv,str(self.scanner_option['p25_lpf']),str(self.scanner_option['disp_uid']),
				rsv,rsv,rsv,rsv,rsv,rsv,rsv,rsv,rsv,rsv,rsv,rsv,rsv,rsv])

		try:
			if self.backlight: blt = self.scanner.raw(blt)
			if self.battery_info: bsv = self.scanner.raw(bsv)
			if self.key_beep: kbp = self.scanner.raw(kbp)
			if self.opening_message: oms = self.scanner.raw(oms)
			if self.priority_mode: pri = self.scanner.raw(pri)
			if self.auto_gain_control: agv = self.scanner.raw(agv)
			if self.lcd_contrast: cnt = self.scanner.raw(cnt)
			if self.scanner_option: scn = self.scanner.raw(scn)
			if self.com_port: 
				com = self.scanner.raw(com)
				time.sleep(3)

		except CommandError, e:
			self.logger.error('set_data(): %s' % str(e))
			return 0

		return 1

	def dump(self):

		"""Dump scanner settings to dictionary."""

		bl=self.backlight
		bl['event']=human_events[bl['event']]
		bl['dimmer']=human_dimmers[bl['dimmer']]
		bi=self.battery_info
		bi['bat_save']=human_onoff[bi['bat_save']]
		cp=self.com_port
		kb=self.key_beep
		kb['lock']=human_onoff[kb['lock']]
		kb['safe']=human_onoff[kb['safe']]
		om=self.opening_message
		pm=self.priority_mode
		pm['pri_mode']=human_pri_modes[pm['pri_mode']]
		agc=self.auto_gain_control
		lc=self.lcd_contrast
		so=self.scanner_option
		so['ch_log']=human_ch_logs[so['ch_log']]
		so['disp_uid']=human_onoff[so['disp_uid']]
		so['g_att']=human_onoff[so['g_att']]
		so['p25_lpf']=human_onoff[so['p25_lpf']]
		

		d={'backlight':bl, 'battery_info':bi, 'com_port':cp, 'key_beep':kb, 'opening_message':om,
			'priority_mode':pm, 'auto_gain_control':agc, 'lcd_contrast':lc, 'scanner_option':so}

		return d

	def load(self, backlight={}, battery_info={}, com_port={}, key_beep={}, opening_message=[],
			priority_mode={}, auto_gain_control={}, lcd_contrast={}, scanner_option={}):

		"""Load scanner settings from dictionary."""

		try:

			if backlight: backlight['event']=scanner_events[backlight['event']]
			if backlight: backlight['dimmer']=scanner_dimmers[backlight['dimmer']]
			if battery_info: battery_info['bat_save']=scanner_onoff[battery_info['bat_save']]
			if key_beep: key_beep['lock']=scanner_onoff[key_beep['lock']]
			if key_beep: key_beep['safe']=scanner_onoff[key_beep['safe']]
			if priority_mode: priority_mode['pri_mode']=scanner_pri_modes[priority_mode['pri_mode']]
			if scanner_option: scanner_option['ch_log']=scanner_ch_logs[scanner_option['ch_log']]
			if scanner_option: scanner_option['disp_uid']=scanner_onoff[scanner_option['disp_uid']]
			if scanner_option: scanner_option['g_att']=scanner_onoff[scanner_option['g_att']]
			if scanner_option: scanner_option['p25_lpf']=scanner_onoff[scanner_option['p25_lpf']]

		except KeyError, e:
			self.logger.error('load(): %s' % str(e))
			return 0

		if backlight: self.backlight=backlight
		if battery_info: self.battery_info=battery_info
		if com_port: self.com_port=com_port
		if key_beep: self.key_beep=key_beep
		if opening_message: self.opening_message=opening_message
		if priority_mode: self.priority_mode=priority_mode
		if auto_gain_control: self.auto_gain_control=auto_gain_control
		if lcd_contrast: self.lcd_contrast=lcd_contrast
		if scanner_option: self.scanner_option=scanner_option

		return 1

class System:

	"""Scanner System class."""

	def __init__(self, scanner, sys_index):

		self.logger = logging.getLogger('uniden_api.System')

		self.scanner = scanner
		self.sys_index = sys_index
                self.sys_type = 'CNV'
                self.name = 'NONAME'
                self.quick_key = '.'
                self.hld = '0'
                self.lout = '0'
                self.dly = '0'
                self.rev_index = None
                self.fwd_index = None
                self.chn_grp_head = None
                self.chn_grp_tail = None
                self.seq_no = None
                self.start_key = '.'
                self.number_tag = 'NONE'
                self.agc_analog = '0'
                self.agc_digital = '0'
                self.p25waiting = '200'
                self.protect = '0'

		self.id_search='0'
		self.s_bit='0'
		self.end_code='0'
		self.afs='0'
		self.emg='0'
		self.emgl='0'
		self.fmap='0'
		self.ctm_fmap=''
		self.tgid_grp_head=None
		self.tgid_grp_tail=None
		self.id_lout_grp_head=None
		self.id_lout_grp_tail=None
		self.mot_id='0'
		self.emg_color='OFF'
		self.emg_pattern='0'
		self.p25nac='search'
		self.pri_id_scan='0'

		self.quick_lockout=()

		self.groups={}
		self.sites={}

		self.lout_tgids=()
		self.srch_lout_tgids=()

	def get_data(self):

		"""Get System Information.
		When the system protect bit is ON, except [SYS_TYPE], [NAME], [REV_INDEX],
		[FWD_INDEX], [CHN_GRP_HEAD], [CHN_GRP_TAIL], other parameters will be send as a
		reserve parameter in the Radio -> Controller command.
		
		INDEX		System Index
		SYS_TYPE	System Type
				CNV CONVENTIONAL
				MOT MOTOROLA TYPE
				EDC EDACS Narrow / Wide
				EDS EDACS SCAT
				LTR LTR
				P25S P25 STANDARD
				P25F P25 One Frequency TRUNK
		NAME		Name (max.16char)
		QUICK_KEY	Quick Key (0-99/.(dot) means none)
		HLD		System Hold Time (0-255)
		LOUT		Lockout (0:Unlocked / 1:Lockout)
		DLY		Delay Time (-10,-5,-2,0,1,2,5,10,30)
		REV_INDEX	Reverse System Index of the Scan Setting
		FWD_INDEX	Forward System Index of the Scan Setting
		CHN_GRP_HEAD	Channel Group Index Head of the conventional system or Site Index
				Head of the Trunked System
		CHN_GRP_TAIL	Channel Group Index Tail of the conventional system or Site
				Index Tail of the Trunked System
		SEQ_NO 		System Sequence Number (1 - 500)
		START_KEY 	Startup Configuration Key (0-9/.(dot) means none)
		NUMBER_TAG 	Number tag (0-999 / NONE)
		AGC_ANALOG 	AGC Setting for Analog Audio (0:OFF / 1:ON)
		AGC_DIGITAL 	AGC Setting for Digital Audio (0:OFF / 1:ON)
		P25WAITING 	P25 Waiting time (0,100,200, .... , 900,1000)
		PROTECT 	Protect bit Status (0:OFF / 1:ON)

		Get Trunked System Information.

		ID_SEARCH		ID Search/Scan (0:ID Scan mode / 1: Search Mode)
		S_BIT			Motorola Status Bit (0:Ignore, 1:Yes)
		END_CODE		Motorola End Code (0:Ignore, 1:Analog, 2:Analog and Digital)
		AFS			EDACS ID Format(0:Decimal / 1:AFS)
		EMG			Emergency Alert (0:Ignore / 1-9:Alert)
		EMGL			Emergency Alert Level (0:OFF / 1 - 15)
		FMAP			Fleet Map (0-16, 0-15:Preset, 16:Custom)
		CTM_FMAP		Custom Fleet Map Setting (######## : # is 0-E)
					# means Size Code of each BLOCK (from 0 to 7)
					0 : Size Code 0 5 : Size Code 5 A : Size Code 10
					1 : Size Code 1 6 : Size Code 6 B : Size Code 11
					2 : Size Code 2 7 : Size Code 7 C : Size Code 12
					3 : Size Code 3 8 : Size Code 8 D : Size Code 13
					4 : Size Code 4 9 : Size Code 9 E : Size Code 14
		TGID_GRP_HEAD		TGID Index Head of the System
		TGID_GRP_TAIL		TGID Index Tail of the System
		ID_LOUT_GRP_HEAD	L/O TGID Group Index Head of the System
		ID_LOUT_GRP_TAIL	L/O TGID Group Index Tail of the System
		MOT_ID			Motorola/P25 ID Format (0:Decimal / 1:HEX )
		EMG_COLOR		Emergency Alert Light color (OFF,BLUE,RED,MAGENTA,GREEN,CYAN,YELLOW,WHITE)
		EMG_PATTERN		Emergency Alert Light Pattern(0:ON / 1:SLow / 2:Fast)
		P25NAC			P25 NAC Status ( 0-FFF: 0-FFF / SRCH: Nac Search)
		PRI_ID_SCAN		Priority ID Scan ( 0:OFF / 1: ON)

		Group Quick Lockout
		The Order of Quick Key is as same as LCD Icon (1 – 9, 0).
		It cannot turn on/off the Quick Key that has no Group.

		########## (each # is 0 - 2)	Group Quick Key status of [SYS_INDEX].
		0 Not assigned (Displayed as “-“ on the scanner.)
		1 On (Displayed as each number on the scanner.)
		2 Off (Displayed as “*” on the scanner.)"""

		cmd = ','.join(['SIN',self.sys_index])

                try:
			res = self.scanner.raw(cmd)

		except CommandError:
			self.logger.error('get_data(): cmd %s' % cmd)
			return 0

		(sin,self.sys_type,self.name,self.quick_key,self.hld,self.lout,
			self.dly,rsv1,rsv2,rsv3,rsv4,rsv5,self.rev_index,self.fwd_index,
			self.chn_grp_head,self.chn_grp_tail,self.seq_no,self.start_key,
			rsv6,rsv7,rsv8,rsv9,rsv10,self.number_tag,self.agc_analog,
			self.agc_digital,self.p25waiting,self.protect,rsv11) = res.split(',')

		grp_index = self.chn_grp_head

		while int(grp_index) <> -1:

			if self.sys_type == 'CNV':
				g=Group(self.scanner,grp_index,self.sys_type)
				g.get_data()
				self.groups[grp_index]=g
				grp_index=g.fwd_index
			else:
				s=Site(self.scanner,grp_index)
				s.get_data()
				self.sites[grp_index]=s
				grp_index=s.fwd_index

		if self.sys_type <> 'CNV':

			cmd = ','.join(['TRN',self.sys_index])

        	        try:
				res = self.scanner.raw(cmd)

			except CommandError:
				self.logger.error('get_data(): cmd %s' % cmd)
				return 0

			(trn,self.id_search,self.s_bit,self.end_code,self.afs,rsv1,rsv2,
				self.emg,self.emgl,self.fmap,self.ctm_fmap,rsv3,rsv4,rsv5,
				rsv6,rsv7,rsv8,rsv9,rsv10,rsv11,rsv12,self.tgid_grp_head,
				self.tgid_grp_tail,self.id_lout_grp_head,self.id_lout_grp_tail,
				self.mot_id,self.emg_color,self.emg_pattern,self.p25nac,
				self.pri_id_scan) = res.split(',')
			
			tgid_grp_index = self.tgid_grp_head

			while int(tgid_grp_index) <> -1:

				g=Group(self.scanner,tgid_grp_index,self.sys_type)
				g.get_data()
				self.groups[tgid_grp_index]=g
				tgid_grp_index=g.fwd_index

		cmd = ','.join(['QGL',self.sys_index])

                try:
			res = self.scanner.raw(cmd)

		except CommandError:
			self.logger.error('get_data(): cmd %s' % cmd)
			return 0
		
		(qgl,s) = res.split(',')
		self.quick_lockout=zero_to_head(tuple(s))

		self.get_lockout_tgids()

		return 1

	def set_data(self):

                """Set scanner system data to device."""

		rsv = ''
		res = ''
		cmd = ','.join(['SIN',str(self.sys_index),self.name,str(self.quick_key),
				str(self.hld),str(self.lout),str(self.dly),rsv,rsv,
				rsv,rsv,rsv,str(self.start_key),rsv,rsv,rsv,rsv,rsv,
				rsv,str(self.number_tag),str(self.agc_analog),
				str(self.agc_digital),str(self.p25waiting)])

                try:
			res = self.scanner.raw(cmd)

		except CommandError:
			self.logger.error('set_data(): cmd %s' % cmd)
			return 0

		for g in self.groups.values(): g.set_data()

		if self.sys_type <> 'CNV':

			rsv = ''
			cmd = ','.join(['TRN',str(self.sys_index),str(self.id_search),
					str(self.s_bit),str(self.end_code),str(self.afs),
					rsv,rsv,str(self.emg),str(self.emgl),str(self.fmap),
					self.ctm_fmap,rsv,rsv,rsv,rsv,rsv,rsv,rsv,rsv,rsv,rsv,
					str(self.mot_id),self.emg_color,str(self.emg_pattern),
					self.p25nac,str(self.pri_id_scan)])

        	        try:
				res = self.scanner.raw(cmd)

			except CommandError:
				self.logger.error('set_data(): cmd %s' % cmd)
				return 0

			for s in self.sites.values(): s.set_data() 

		t=zero_to_tail(self.quick_lockout)
		s=''.join(t)
		cmd = ','.join(['QGL',self.sys_index,s])

                try:
			res = self.scanner.raw(cmd)

		except CommandError:
			self.logger.error('set_data(): cmd %s' % cmd)
			return 0

		return 1

	def show(self):

		"""Shows system data. Not descending to groups and sites."""

		print ('--------SYSTEM-------')
		print ('System Index:\t\t\t%s') % self.sys_index
		print ('System Type:\t\t\t%s') % self.sys_type
		print ('Name:\t\t\t\t%s') % self.name
		print ('Quick Key:\t\t\t%s') % self.quick_key
		print ('System Hold Time:\t\t%s') % self.hld
		print ('Lockout:\t\t\t%s') % self.lout
		print ('Delay:\t\t\t\t%s s') % self.dly
		print ('Reverse System Index:\t\t%s') % self.rev_index
		print ('Forward System Index:\t\t%s') % self.fwd_index
		print ('Group Index Head:\t\t%s') % self.chn_grp_head
		print ('Group Index Tail:\t\t%s') % self.chn_grp_tail
		print ('System Sequence Number:\t\t%s') % self.seq_no
		print ('Startup Configuration Key:\t%s') % self.start_key
		print ('Number tag:\t\t\t%s') % self.number_tag
		print ('AGC Setting for Analog Audio:\t%s') % self.agc_analog
		print ('AGC Setting for Digital Audio:\t%s') % self.agc_digital
		print ('P25 Waiting time:\t\t%s') % self.p25waiting
		print ('Protect:\t\t\t%s') % human_onoff[self.protect]
	

		if self.sys_type <> 'CNV':

			print ('ID Search/Scan:\t\t\t%s') % self.id_search
			print ('Motorola Status Bit:\t\t\t%s') % self.s_bit
			print ('Motorola End Code:\t\t\t%s') % self.end_code
			print ('EDACS ID Format:\t\t\t%s') % self.afs
			print ('Emergency Alert:\t\t\t%s') % self.emg
			print ('Emergency Alert Level:\t\t\t%s') % self.emgl
			print ('Fleet Map:\t\t\t%s') % self.fmap
			print ('Custom Fleet Map Setting:\t\t%s') % self.ctm_fmap
			print ('TGID Index Head:\t\t\t%s') % self.tgid_grp_head
			print ('TGID Index Tail:\t\t\t%s') % self.tgid_grp_tail
			print ('L/O TGID Group Index Head:\t\t%s') % self.id_lout_grp_head
			print ('L/O TGID Group Index Tail:\t\t%s') % self.id_lout_grp_tail
			print ('Motorola/P25 ID Format:\t\t\t%s') % self.mot_id
			print ('Emergency Alert Light Color:\t\t%s') % self.emg_color
			print ('Emergency Alert Light Pattern:\t\t%s') % self.emg_pattern
			print ('P25 NAC Status:\t\t\t%s') % self.p25nac
			print ('Priority ID Scan:\t\t\t%s') % self.pri_id_scan
			
	def show_brief(self):

		"""Shows brief system data: name, type, groups and sites."""

		print ('Index: %s\tName: %s\tType: %s\tLockout: %s') % (self.sys_index,self.name,self.sys_type,human_lout[self.lout])
		for i in sorted(self.groups): self.groups[i].show_brief()
		for i in sorted(self.sites): self.sites[i].show_brief()


	def dump(self):

		"""Dumps system data to dictionary."""

		lout='unlock'
		level='auto'
		sb='ignore'
		ec='ignore'
		afs='decimal'
		mi='decimal'
		ep='on'
		pis='off'
                stype=human_sys_type[self.sys_type]
                qk=self.quick_key
                if self.lout: lout=human_lout[self.lout]
		if self.emgl: level=human_alert_tlevels[self.emgl]
                sk=self.start_key
                tag=self.number_tag
                if self.agc_analog!='': agca=human_onoff[self.agc_analog]
		else: agca=''
                if self.agc_digital!='': agcd=human_onoff[self.agc_digital]
		else: agcd=''
                pw=self.p25waiting
                pr=human_onoff[self.protect]

		ids=human_id_search[self.id_search]
		if self.s_bit: sb=human_sbit[self.s_bit]
		if self.end_code: ec=human_end_code[self.end_code]
		if self.afs: afs=human_afs[self.afs]
		if self.mot_id: mi=human_mot_id[self.mot_id]
		if self.emg_pattern: ep=human_altp[self.emg_pattern]
		if self.pri_id_scan: pis=human_onoff[self.pri_id_scan]

		ql=list(self.quick_lockout)
		lt=list(self.lout_tgids)
		slt=list(self.srch_lout_tgids)

		groups=[]
		sites=[]

		for i in sorted(self.groups): groups.append(self.groups[i].dump())
		for i in sorted(self.sites): sites.append(self.sites[i].dump())

		d={'type':stype, 'name':self.name, 'quick_key':qk, 'hold':self.hld, 'delay':self.dly, 'lockout':lout,
			'start_key':sk, 'tag':tag, 'agc_analog':agca, 'agc_digital':agcd, 'p25_waiting':pw,
			'protected':pr, 'groups':groups, 'grp_lockout':ql}

		if self.sys_type <> 'CNV':
			d1={'id_mode':ids, 'status':sb, 'end_code':ec, 'edacs_format':afs, 'alert':self.emg, 
				'alert_lvl':level, 'grp_lockout':ql, 'fleet_map':self.fmap, 
				'custom_fmap':self.ctm_fmap, 'id_format':mi, 'alert_color':self.emg_color, 
				'pattern':ep, 'nac':self.p25nac, 'priority':pis, 'sites':sites,
				'tgids_lockout':lt, 'search_lockout':slt}
			d.update(d1)	

		return d

	def load(self, type='conventional', name='NONAME', quick_key='.', hold='0', lockout='unlock', delay='0',
			start_key='.', tag='NONE', agc_analog='off', agc_digital='off', p25_waiting='200',
			protected='off', id_mode='scan', status='ignore', end_code='ignore', 
			edacs_format='decimal', alert='0', alert_lvl='auto', grp_lockout=[], 
			fleet_map='0', custom_fmap='', id_format='decimal', alert_color='off', pattern='on',
			nac='', priority='off', groups=[], sites=[], tgids_lockout=[], search_lockout=[]):

		"""Loads dictionary to system class."""

                self.name = name
                self.quick_key = str(quick_key)
                self.hld = str(hold)
		self.dly = str(delay)
                self.start_key = str(start_key)
                self.number_tag = str(tag)
                self.p25waiting = str(p25_waiting)
		self.quick_lockout = tuple(grp_lockout)

		self.emg=str(alert)
		self.fmap=str(fleet_map)
		self.ctm_fmap=str(custom_fmap)
		self.emg_color=alert_color.upper()
		self.p25nac=str(nac)
			
		try:
                	self.sys_type = scanner_sys_type[type]
                	self.lout = scanner_lout[lockout]
                	self.agc_analog = scanner_onoff[agc_analog]
	                self.agc_digital = scanner_onoff[agc_digital]
			self.protected = scanner_onoff[protected]
			self.id_search=scanner_id_search[id_mode]
			self.s_bit=scanner_sbit[status]
			self.end_code=scanner_end_code[end_code]
			self.afs=scanner_afs[edacs_format]
			self.emgl=scanner_alert_tlevels[alert_lvl]
			self.mot_id=scanner_mot_id[id_format]
			self.emg_pattern=scanner_altp[pattern]
			self.pri_id_scan=scanner_onoff[priority]

		except KeyError, e:
			self.logger.error('load(): keyerror %s' % str(e))
			return 0

		for grp in groups:
			# append grp
			i=self.append_group(grp['type'])
			if i==0: continue
			# load dict for grp
			self.groups[i].load(**grp)
			# set data ? up to this time data not in scanner!

		for site in sites:
			# append site
			i=self.append_site()
			if i==0: continue
			# load dict for site
			self.sites[i].load(**site)
			# set data ? up to this time data not in scanner!
			
		return 1

	def append_site(self):

		"""Appends site to system. Returns site index."""

		cmd = ','.join(['AST',self.sys_index,''])

		try:
			res = self.scanner.raw(cmd)

		except CommandError:
			self.logger.error('append_site(): cmd %s' % cmd)
			return 0

		(ast,site_index) = res.split(',')
		if site_index == -1: return 0
		s=Site(self.scanner,site_index)
		self.sites[site_index]=s

		return site_index

	def delete_site(self, site_index):

		"""Deletes site from system by index."""

		cmd = ','.join(['DGR',str(site_index)])

		try:
			res = self.scanner.raw(cmd)

		except CommandError:
			self.logger.error('delete_site(): cmd %s' % cmd)
			return 0

		self.sites.pop(site_index)

		return 1

	def append_group(self, gtype='C'):

		"""Appends group to system. Returns group index."""

		cmd=''

		if gtype == 'C': cmd = ','.join(['AGC',self.sys_index])
		if gtype == 'T': cmd = ','.join(['AGT',self.sys_index])

		try:
			res = self.scanner.raw(cmd)

		except CommandError:
			self.logger.error('append_group(): cmd %s' % cmd)
			return 0

		(ag,grp_index) = res.split(',')
		if grp_index == -1: return 0
		g=Group(self.scanner,grp_index,self.sys_type)
		self.groups[grp_index]=g

		return grp_index

	def delete_group(self, grp_index):

		"""Deletes group from system."""

		cmd = ','.join(['DGR',str(grp_index)])

		try:
			res = self.scanner.raw(cmd)

		except CommandError:
			self.logger.error('delete_group(): cmd %s' % cmd)
			return 0

		self.groups.pop(grp_index)

		return 1

	def get_lockout_tgids(self):

		"""Returns tuple of locked out TGIDs and SRCH TGIDs."""

		cmd = ','.join(['GLI',self.sys_index])

		tgid=0
		l=[]		

                try:
			while int(tgid) <> -1:
				res = self.scanner.raw(cmd)
				(gli,tgid) = res.split(',')
				l.append(tgid)

		except CommandError:
			self.logger.error('get_lockout_tgids(): cmd %s' % cmd)
			return 0

		self.lout_tgids=tuple(l)
		
		cmd = ','.join(['SLI',self.sys_index])

		tgid=0
		l=[]		

                try:
			while int(tgid) <> -1:
				res = self.scanner.raw(cmd)
				(sli,tgid) = res.split(',')
				l.append(tgid)

		except CommandError:
			self.logger.error('get_lockout_tgids(): cmd %s' % cmd)
			return 0

		self.srch_lout_tgids=tuple(l)

		return 1

	def unlock_tgid(self, tgid):

		"""Unlock TGID."""

		cmd = ','.join(['ULI',self.sys_index,str(tgid)])

		try:
			res = self.scanner.raw(cmd)

		except CommandError:
			self.logger.error('unlock_tgid(): cmd %s' % cmd)
			return 0

		self.srch_lout_tgids=()
		self.get_lockout_tgids()

		return 1

	def lockout_tgid(self, tgid):

		"""Lock out TGID."""

		cmd = ','.join(['LOI',self.sys_index,str(tgid)])

		try:
			res = self.scanner.raw(cmd)

		except CommandError:
			self.logger.error('lockout_tgid(): cmd %s' % cmd)
			return 0

		self.srch_lout_tgids=()
		self.get_lockout_tgids()

		return 1

class Group:

        """Scanner Group class."""

	def __init__(self, scanner, grp_index, sys_type):

		self.logger = logging.getLogger('uniden_api.Group')
		
		self.scanner = scanner
		self.grp_index = grp_index
		self.sys_type = sys_type
		self.grp_type='C'
		self.name='NONAME'
		self.quick_key='.'
		self.lout='0'
		self.rev_index=None
		self.fwd_index=None
		self.sys_index=None
		self.chn_head=None
		self.chn_tail=None
		self.seq_no=None
		self.latitude='0'
		self.longitude='0'
		self.grp_range='0'
		self.gps_enable='0'

		self.channels={}
		self.tgids={}

	def get_data(self):

		"""Get Group Information.
		In set command, only "," parameters are not changed.
		The set command is aborted if any format error is detected.
		When the system protect bit is ON, except [NAME], [REV_INDEX], [FWD_INDEX],
		[SYS_INDEX], [CHN_HEAD], [CHN_TAIL], other parameters will be send as a reserve
		parameter in the Radio -> Controller command.
		
		GRP_INDEX		Group Index
		GRP_TYPE		Group Type (C: Channel Group / T: TGID Group)
		NAME			Name (max.16char)
		QUICK_KEY		Lockout (0:Unlocked / 1:Lockout)
		REV_INDEX		Reverse Group Index of the System
		FWD_INDEX		Forward Group Index of the System
		SYS_INDEX		System Index
		CHN_HEAD		Channel Index Head of the Group List
		CHN_TAIL		Channel Index Tail of the Group List
		SEQ_NO			Group Sequence Number of the System
		LATITUDE		North or South Latitude
		LONGITUDE		West or East Longitude
		RANGE			Range (1-250 : 1= 0.5 mile or km)
		GPS ENABLE		GPS Location detection (0:OFF/1:ON)"""

		cmd = ','.join(['GIN',self.grp_index])

                try:
			res = self.scanner.raw(cmd)

		except CommandError:
			self.logger.error('get_data(): %s' % cmd)
			return 0
		
		(gin,self.grp_type,self.name,self.quick_key,self.lout,
			self.rev_index,self.fwd_index,self.sys_index,self.chn_head,
			self.chn_tail,self.seq_no,self.latitude,self.longitude,
			self.grp_range,self.gps_enable) = res.split(',')

		chn_index = self.chn_head

		while int(chn_index) <> -1:

			if self.sys_type == 'CNV':
				c=Channel(self.scanner,chn_index)
				c.get_data()
				self.channels[chn_index]=c
				chn_index=c.fwd_index
			else:
				t=TalkGroupID(self.scanner,chn_index)
				t.get_data()
				self.tgids[chn_index]=t
				chn_index=t.fwd_index

		return 1

	def set_data(self):

                """Set scanner group data to device."""

		rsv = ''
		cmd = ','.join(['GIN',str(self.grp_index),self.name,str(self.quick_key),
				str(self.lout),str(self.latitude),str(self.longitude),
				str(self.grp_range),str(self.gps_enable)])

                try:
			res = self.scanner.raw(cmd)

		except CommandError:
			self.logger.error('set_data(): %s' % cmd)
			return 0

		for c in self.channels.values(): c.set_data()

		for t in self.tgids.values(): t.set_data()

		return 1

	def show(self):

                """Shows group data. Not descending to channels and tgids."""

		print ('--------GROUP-------')
		print ('Group Index:\t\t\t%s') % self.grp_index
		print ('Group Type:\t\t\t%s') % self.grp_type
		print ('Name:\t\t\t\t%s') % self.name
		print ('Quick Key:\t\t\t%s') % self.quick_key
		print ('Reverse Channel Index:\t\t%s') % self.rev_index
		print ('Forward Channel Index:\t\t%s') % self.fwd_index
		print ('System Index:\t\t\t%s') % self.sys_index
		print ('Channel Index Head:\t\t%s') % self.chn_head
		print ('Channel Index Tail:\t\t%s') % self.chn_tail
		print ('Group Sequence Number:\t\t%s') % self.seq_no
		print ('North or South Latitude:\t\%s') % self.latitude
		print ('West or East Longitude:\t\t%s') % self.longitude
		print ('Range:\t\t\t\t%s') % self.grp_range
		print ('GPS Location detection:\t\t%s') % human_onoff[self.gps_enable]

	def show_brief(self):

                """Shows brief group data: index, name, channels or tgids."""

		print ('\tIndex: %s\tName: %s\tLockout: %s') % (self.grp_index,self.name,human_lout[self.lout])
		for i in sorted(self.channels): self.channels[i].show_brief()
		for i in sorted(self.tgids): self.tgids[i].show_brief()

	def dump(self):

                """Dumps group data to dictionary."""

		gt=self.grp_type
		qk=self.quick_key
		lout=human_lout[self.lout]
		lat=self.latitude
		lon=self.longitude
		gr=self.grp_range
		gps=human_onoff[self.gps_enable]

		channels=[]
		for i in sorted(self.channels): channels.append(self.channels[i].dump())

		tgids=[]
		for i in sorted(self.tgids): tgids.append(self.tgids[i].dump())

		d={'name':self.name,'quick_key':qk, 'lockout':lout, 'latitude':lat, 'longitude':lon, 
				'range':gr, 'gps':gps, 'type':gt}

		if gt == 'C': d['channels']=channels
		if gt == 'T': d['tgids']=tgids

		return d

	def load(self, name='NONAME', quick_key='.', lockout='unlock', latitude='00000000N', type='C',
			longitude='000000000W', range='0', gps='off', tgids=[], channels=[]):

                """Loads dictionary to group class."""

		self.name=name
		self.latitude=latitude
		self.longitude=longitude
		self.grp_range=str(range)
		self.quick_key=str(quick_key)
		self.grp_type=type.upper()
			
		try:
			self.lout=scanner_lout[lockout]
			self.gps_enable=scanner_onoff[gps]

		except KeyError, e:
			self.logger.error('load(): keyerror %s' % str(e))
			return 0

		for tgid in tgids:
			# append tgid
			i=self.append_tgid()
			# load dict for tgid
			self.tgids[i].load(**tgid)
			# set data ? up to this time data not in scanner!

		for chn in channels:
			# append channel
			i=self.append_channel()
			# load dict for tgid
			self.channels[i].load(**chn)
			# set data ? up to this time data not in scanner!

		return 1

	def append_channel(self):

		"""Appends channel to group. Returns channel index."""

		cmd = ','.join(['ACC',self.grp_index])

		try:
			res = self.scanner.raw(cmd)

		except CommandError:
			self.logger.error('append_channel(): %s' % cmd)
			return 0

		(acc,chn_index) = res.split(',')
		if chn_index == -1: return 0
		c=Channel(self.scanner,chn_index)
		self.channels[chn_index]=c

		return chn_index 

	def append_tgid(self):

		"""Appends TGID to group. Returns TGID index."""

		cmd = ','.join(['ACT',self.grp_index])

		try:
			res = self.scanner.raw(cmd)

		except CommandError:
			self.logger.error('append_tgid(): %s' % cmd)
			return 0

		(act,chn_index) = res.split(',')
		if chn_index == -1: return 0 
		t=TalkGroupID(self.scanner,chn_index)
		self.tgids[chn_index]=t

		return chn_index

	def delete_channel(self, chn_index):

		"""Deletes channel from group."""

		cmd = ','.join(['DCH',str(chn_index)])

		try:
			res = self.scanner.raw(cmd)

		except CommandError:
			self.logger.error('delete_channel(): %s' % cmd)
			return 0

		self.channels.pop(chn_index)

		return 1

	def delete_tgid(self, chn_index):

		"""Deletes TGID from group."""

		cmd = ','.join(['DCH',str(chn_index)])

		try:
			res = self.scanner.raw(cmd)

		except CommandError:
			self.logger.error('delete_tgid(): %s' % cmd)
			return 0

		self.tgids.pop(chn_index)

		return 1

class Site:

        """Scanner Site class."""

	def __init__(self, scanner, sit_index):

		self.logger = logging.getLogger('uniden_api.Site')
		
		self.scanner = scanner
		self.sit_index = sit_index
		self.name='NONAME'
		self.quick_key='.'
		self.hld='0'
		self.lout='0'
		self.mod='AUTO'
		self.att='0'
		self.c_ch='1'
		self.rev_index=None
		self.fwd_index=None
		self.sys_index=None
		self.chn_head=None
		self.chn_tail=None
		self.seq_no=None
		self.start_key='.'
		self.latitude='0'
		self.longitude='0'
		self.sit_range='1'
		self.gps_enable='0'
		self.mot_type=''
		self.edacs_type=''
		self.p25waiting=''

		self.trunk_frqs={}

		self.motorola_custom_band_plan={}

		self.p25_band_plan={}

	def get_data(self):

		"""Get Site Information.
                In set command, only "," parameters are not changed.
                The set command is aborted if any format error is detected.
                When the system protect bit is ON, except [NAME], [REV_INDEX], [FWD_INDEX],
                [SYS_INDEX], [CHN_HEAD], [CHN_TAIL], other parameters will be send as a reserve
                parameter in the Radio -> Controller command.

		INDEX			Site Index
		NAME			Name (max.16char)
		QUICK_KEY		Quick Key (0-99/.(dot) means none)
		HLD			Site Hold Time (0-255)
		LOUT			Lockout (0:Unlocked / 1:Lockout)
		MOD			Modulation (AUTO/FM/NFM)
		ATT			Attenuation (0:OFF/1:ON)
		C-CH			Control Channel Only * This is always only 1:ON
		REV_INDEX		Reverse Site Index of the Scan Setting
		FWD_INDEX		Forward Site Index of the Scan Setting
		SYS_INDEX		System Index
		CHN_HEAD		Channel Index Head of the Group List
		CHN_TAIL		Channel Index Tail of the Group List
		SEQ_NO			Site Sequence Number (1-256)
		START_KEY		Startup Configuration (0-9/.(dot) means none)
		LATITUDE		North or South Latitude
		LONGITUDE		West or East Longitude
		RANGE			Range (1-250 : 1= 0.5 mile or km)
		GPS_ENABLE		GPS Location detection (0:OFF/1:ON)
		MOT_TYPE		Band type for MOT/EDACS(STD/ SPL/CUSTOM)
		EDACS_TYPE		EDACS (WIDE/NARROW)
		P25WAITING		P25 Waiting time (0,100,200,300, .... , 900,1000)"""

		cmd = ','.join(['SIF',self.sit_index])

                try:
			res = self.scanner.raw(cmd)

		except CommandError:
                        self.logger.error('get_data(): %s' % cmd)
			return 0

		(sif,rsv1,self.name,self.quick_key,self.hld,self.lout,
			self.mod,self.att,self.c_ch,rsv2,rsv3,self.rev_index,
			self.fwd_index,self.sys_index,self.chn_head,self.chn_tail,
			self.seq_no,self.start_key,self.latitude,self.longitude,
			self.sit_range,self.gps_enable,rsv4,self.mot_type,
			self.edacs_type,self.p25waiting,rsv5) = res.split(',')

		chn_index = self.chn_head

		while int(chn_index) <> -1:
			t=TrunkFrequency(self.scanner,chn_index)
			t.get_data()
			self.trunk_frqs[chn_index]=t
			chn_index=t.fwd_index

		cmd = ','.join(['MCP',self.sit_index])

                try:
			res = self.scanner.raw(cmd)

		except CommandError:
                        self.logger.error('get_data(): %s' % cmd)
			return 0

		(mcp,lower1,upper1,step1,offset1,lower2,upper2,step2,offset2,
			lower3,upper3,step3,offset3,lower4,upper4,step4,offset4,
			lower5,upper5,step5,offset5,lower6,upper6,step6,offset6) = res.split(',')

		self.motorola_custom_band_plan={'lower': (0,lower1,lower2,lower3,lower4,lower5,lower6),
						'upper': (0,upper1,upper2,upper3,upper4,upper5,upper6),
						'step': (0,step1,step2,step3,step4,step5,step6),
						'offset': (0,offset1,offset2,offset3,offset4,offset5,offset6)}

		cmd = ','.join(['ABP',self.sit_index])

                try:
			res = self.scanner.raw(cmd)

		except CommandError:
                        self.logger.error('get_data(): %s' % cmd)
			return 0

		(abp,bf_0,sf_0,bf_1,sf_1,bf_2,sf_2,bf_3,sf_3,bf_4,sf_4,bf_5,sf_5,
			bf_6,sf_6,bf_7,sf_7,bf_8,sf_8,bf_9,sf_9,bf_A,sf_A,bf_B,sf_B,
			bf_C,sf_C,bf_D,sf_D,bf_E,sf_E,bf_F,sf_F) = res.split(',')

		self.p25_band_plan = {'base_freq': [bf_0,bf_1,bf_2,bf_3,bf_4,bf_5,
					bf_6,bf_7,bf_8,bf_9,bf_A,bf_B,bf_C,bf_D,bf_E,bf_F],
				'spacing_freq': [sf_0,sf_1,sf_2,sf_3,sf_4,sf_5,
					sf_6,sf_7,sf_8,sf_9,sf_A,sf_B,sf_C,sf_D,sf_E,sf_F]}

		return 1

	def set_data(self):

                """Set scanner site data to device."""

		rsv = ''
		cmd = ','.join(['SIF',str(self.sit_index),self.name,str(self.quick_key),
				str(self.hld),str(self.lout),self.mod,str(self.att),str(self.c_ch),
				rsv,rsv,str(self.start_key),str(self.latitude),str(self.longitude),
				str(self.sit_range),str(self.gps_enable),rsv,self.mot_type,
				self.edacs_type,str(self.p25waiting),rsv])

                try:
			res = self.scanner.raw(cmd)

		except CommandError:
                        self.logger.error('set_data(): %s' % cmd)
			return 0

		for t in self.trunk_frqs.values(): t.set_data()

		# TODO implement MCP/ABP set

		return 1

	def  show(self):

		"""Shows site data. Not descending to trunk frequency."""

		print ('--------SITE-------')
		print ('Site Index:\t\t\t%s') % self.sit_index
		print ('Name:\t\t\t\t%s') % self.name
		print ('Quick Key:\t\t\t%s') % self.quick_key
		print ('Site Hold Time:\t\t\t%s') % self.hld
		print ('Lockout:\t\t\t%s') % human_lout[self.lout]
		print ('Modulation:\t\t\t%s') % self.mod
		print ('Attenuation:\t\t\t%s') % human_onoff[self.att]
		print ('Control Channel Only:\t\t%s') % self.c_ch
		print ('Reverse Site Index:\t\t%s') % self.rev_index
		print ('Forward Site Index:\t\t%s') % self.fwd_index
		print ('System Index:\t\t\t%s') % self.sys_index
		print ('Channel Index Head:\t\t%s') % self.chn_head
		print ('Channel Index Tail:\t\t%s') % self.chn_tail
		print ('Site Sequence Number:\t\t\t%s') % self.seq_no
		print ('Start Key:\t\t\t%s') % self.start_key
		print ('North or South Latitude:\t%s') % self.latitude
		print ('West or East Longitude:\t\t%s') % self.longitude
		print ('Range:\t\t\t\t%s') % self.sit_range
		print ('GPS Location detection:\t\t%s') % human_onoff[self.gps_enable]
		print ('Band type for MOT/EDACS:\t\t%s') % self.mot_type
		print ('EDACS:\t\t\t\t%s') % self.edacs_type
		print ('P25 Waiting time:\t\t\t%s') % self.p25waiting

	def show_brief(self):

		"""Shows brief site data: index, name and trunk frequencies."""

		print ('\tIndex: %s\tName: %s\t Lockout: %s') % (self.sit_index,self.name,human_lout[self.lout])
		for i in sorted(self.trunk_frqs): self.trunk_frqs[i].show_brief()


	def append_trunk_frq(self):

		"""Appends trunk frequency to site. Returns trunk frequency index."""

		cmd = ','.join(['ACC',self.sit_index])

		try:
			res = self.scanner.raw(cmd)

		except CommandError:
			self.logger.error('append_trunk_frq(): %s' % cmd)
			return 0

		(acc,chn_index) = res.split(',')
		if chn_index == -1: return 0
		t=TrunkFrequency(self.scanner,chn_index)
		self.trunk_frqs[chn_index]=t

		return chn_index

	def delete_trunk_frq(self, chn_index):

		"""Deletes trunk frequency from group."""

		cmd = ','.join(['DCH',str(chn_index)])

		try:
			res = self.scanner.raw(cmd)

		except CommandError:
			self.logger.error('delete_trunk_frq(): %s' % cmd)
			return 0

		self.trunk_frqs.pop(chn_index)

		return 1

	def dump(self):

		"""Dumps group data to dictionary."""

		cch='on'
		qk=self.quick_key
		lout=human_lout[self.lout]
		att=human_onoff[self.att]
		if self.c_ch: cch=human_onoff[self.c_ch]
		sk=self.start_key
		lat=self.latitude
		lon=self.longitude
		sr=self.sit_range
		gps=human_onoff[self.gps_enable]
		mt=self.mot_type
		et=self.edacs_type
		pw=self.p25waiting
		mbp=self.motorola_custom_band_plan
		for key in mbp.keys(): mbp[key]=list(mbp[key])
		pbp=self.p25_band_plan

		tfqs=[]
		for i in sorted(self.trunk_frqs): tfqs.append(self.trunk_frqs[i].dump())

		d={'name':self.name, 'quick_key':qk, 'hold':self.hld, 'lockout':lout, 'modulation':self.mod,
			'attenuation':att, 'start_key':sk, 'latitude':self.latitude, 'longitude':self.longitude,
			'range':sr, 'gps':gps, 'band_type':mt, 'edacs':et, 'p25_waiting':pw, 'trunk_frqs':tfqs,
			'motorola_bp':mbp, 'p25_bp':pbp, 'cch':cch}
		
		return d

	def load(self, name='NONAME', quick_key='.', hold='0', lockout='unlock', modulation='', attenuation='off',
			start_key='.', latitude='00000000N', longitude='000000000W', range='0', gps='off', cch='on', 
			band_type='', edacs='', p25_waiting='', trunk_frqs=[], motorola_bp={}, p25_bp={}):

		"""Loads dictionary to group class."""

		self.name=name
		self.mod=modulation.upper()
		self.latitude=latitude
		self.longitude=longitude
		self.mot_type=band_type
		self.edacs_type=edacs
		for key in motorola_bp.keys():
			self.motorola_custom_band_plan[key]=tuple(motorola_bp[key])
		self.p25_band_plan=p25_bp
		self.hld=str(hold)
		self.sit_range=str(range)
		self.p25waiting=str(p25_waiting)
		self.quick_key=str(quick_key)
		self.start_key=str(start_key)
			
		try:
			self.c_ch=scanner_onoff[cch]
			self.lout=scanner_lout[lockout]
			self.att=scanner_onoff[attenuation]
			self.gps_enable=scanner_onoff[gps]

		except KeyError:
			self.logger.error('load(): keyerror %s' % str(e))
			return 0

		for tf in trunk_frqs:
			# append trunk frequency
			i=self.append_trunk_frq()
			# load dict for tf
			self.trunk_frqs[i].load(**tf)
			# set data ? up to this time data not in scanner!

		return 1

class Channel:

	"""Scanner Channel class."""

	def __init__(self, scanner, chn_index):

		self.logger = logging.getLogger('uniden_api.Channel')
		
		self.scanner = scanner
		self.chn_index = chn_index
		self.name='NONAME'
		self.frq='00000000'
		self.mod='AM'
		self.dcs='0'
		self.tlock='0'
		self.lout='0'
		self.pri='0'
		self.att='0'
		self.alt='0'
		self.altl='0'
		self.rev_index=None
		self.fwd_index=None
		self.sys_index=None
		self.grp_index=None
		self.audio_type='0'
		self.p25nac=''
		self.number_tag='NONE'
		self.alt_color='YELLOW'
		self.alt_pattern='0'
		self.vol_offset='0'

	def get_data(self):

		"""Get Channel Information.
		In set command, only "," parameters are not changed.
                The set command is aborted if any format error is detected.
                When the system protect bit is ON, except [NAME], [REV_INDEX], [FWD_INDEX],
                [SYS_INDEX], [CHN_HEAD], [CHN_TAIL], other parameters will be send as a reserve
                parameter in the Radio -> Controller command.

		INDEX			Channel Index
		NAME			Name (max.16char)
		FRQ			Channel Frequency
		MOD			Modulation (AUTO/AM/FM/NFM/WFM/FMB)
		ATT			Attenuation (0:OFF / 1:ON)
		CTCSS/DCS		CTCSS/DCS Status (0-231)
		TLOCK			CTCSS/DCS Tone Lockout(0:OFF / 1:ON)
		LOUT			Lockout (0:Unlocked / 1:Lockout)
		PRI			Priority (0:OFF / 1:ON)
		ALT			Alert Tone (0:OFF / 1-9:Tone No)
		ALTL			Alert Tone Level (0:AUTO/ 1-15)
		REV_INDEX		Reverse Channel Index of the Chan0nel Group
		FWD_INDEX		Forward Channel Index of the Channel Group
		SYS_INDEX		System Index of the Channel
		GRP_INDEX		Group Index of the Channel
		AUDIO_TYPE		Audio Type ( 0:All / 1:Analog Only / 2: Digital Only )
		P25NAC			P25 NAC Status ( 0-FFF: 0-FFF / SRCH: Nac Search)
		NUMBER_TAG 		Number tag (0-999 / NONE)
		ALT_COLOR 		Alert Light color (OFF,BLUE,RED,MAGENTA,GREEN,CYAN,YELLOW,WHITE)
		ALT_PATTERN		Alert Light Pattern(0:ON / 1:SLow / 2:Fast)
		VOL_OFFSET		Volume Offset (-3 - +3)"""

		cmd = ','.join(['CIN',self.chn_index])

                try:
			res = self.scanner.raw(cmd)

		except CommandError:
			self.logger.error('get_data(): %s' % cmd)
			return 0

		(cin,self.name,self.frq,self.mod,self.dcs,self.tlock,
			self.lout,self.pri,self.att,self.alt,self.altl,
			self.rev_index,self.fwd_index,self.sys_index,
			self.grp_index,rsv1,self.audio_type,self.p25nac,
			self.number_tag,self.alt_color,self.alt_pattern,
			self.vol_offset) = res.split(',')

		return 1

	def set_data(self):

		"""Set scanner channel data to device."""

		rsv = ''
		cmd = ','.join(['CIN',self.chn_index,self.name,self.frq,self.mod,
				str(self.dcs),str(self.tlock),str(self.lout),str(self.pri),
				str(self.att),str(self.alt),str(self.altl),rsv,str(self.audio_type),
				self.p25nac,str(self.number_tag),self.alt_color,str(self.alt_pattern),
				str(self.vol_offset)])

                try:
			res = self.scanner.raw(cmd)

		except CommandError:
			self.logger.error('set_data(): %s' % cmd)
			return 0

		return 1

	def show(self):

		"""Shows channel data."""

		print ('--------CHANNEL-------')
		print ('Channel Index:\t\t\t%s') % self.chn_index
		print ('Name:\t\t\t\t%s') % self.name
		print ('Channel Frequency:\t\t%s MHz') % frq_from_scanner(self.frq)
		print ('Modulation:\t\t\t%s') % self.mod
		print ('Attenuation:\t\t\t%s') % human_onoff[self.att]
		print ('CTCSS/DCS Status:\t\t%s') % human_ctcss_dscs[self.dcs]
		print ('CTCSS/DCS Tone Lockout:\t\t%s') % human_onoff[self.tlock]
		print ('Lockout:\t\t\t%s') % human_lout[self.lout]
		print ('Priority:\t\t\t%s') % human_onoff[self.pri]
		print ('Alert Tone:\t\t\t%s') % human_alert_tones[self.alt]
		print ('Alert Tone Level:\t\t%s') % human_alert_tlevels[self.altl]
		print ('Reverse Channel Index:\t\t%s') % self.rev_index
		print ('Forward Channel Index:\t\t%s') % self.fwd_index
		print ('System Index:\t\t\t%s') % self.sys_index
		print ('Group Index:\t\t\t%s') % self.grp_index
		print ('Audio Type:\t\t\t%s') % human_audiot[self.audio_type]
		print ('P25 NAC Status:\t\t\t%s') % self.p25nac
		print ('Number tag:\t\t\t%s') % self.number_tag
		print ('Alert Light color:\t\t%s') % self.alt_color
		print ('Alert Light Pattern:\t\t%s') % human_altp[self.alt_pattern]
		print ('Volume Offset:\t\t\t%s') % self.vol_offset

	def show_brief(self):

		"""Shows brief channel data: index, name and frequency."""

		print ('\t\tIndex: %s\tName: %s\tFrequency: %s\t Lockout: %s') % (self.chn_index,self.name,
								frq_from_scanner(self.frq),human_lout[self.lout])

	def dump(self):

		"""Dumps group data to dictionary."""

		frq=frq_from_scanner(self.frq)
		dcs=human_ctcss_dcs[self.dcs]
		tlock=human_lout[self.tlock]
		lout=human_lout[self.lout]
		pri=human_onoff[self.pri]
		att=human_onoff[self.att]
		if self.audio_type!='': audiot=human_audiot[self.audio_type]
		else: audiot=''
		altp=human_altp[self.alt_pattern]
		vol=self.vol_offset
		level=human_alert_tlevels[self.altl]
		tone=human_alert_tones[self.alt]

		d={'name':self.name, 'frequency':frq, 'modulation':self.mod, 'dcs':dcs, 'tone_lockout':tlock,
			'lockout':lout, 'priority':pri, 'attenuate':att, 'alert_tone':tone,
			'alert_level':level, 'audio_type':audiot, 'p25nac':self.p25nac,
			'tag':self.number_tag, 'alert_color':self.alt_color, 'pattern':altp, 'vol_offset':vol}

		return d

	def load(self, name='NONAME', frequency='0', modulation='AM', dcs='all', tone_lockout='unlock',
			lockout='unlock', priority='off', attenuate='off', alert_tone='off',
			alert_level='auto', audio_type='all', p25nac='', tag='NONE', alert_color='off', 
			pattern='on', vol_offset='0'):

		"""Loads dictionary to group class."""

		self.name=name
		self.frq=frq_to_scanner(frequency)
		self.mod=modulation
		self.number_tag=str(tag)
		self.vol_offset=str(vol_offset)
		self.alt_color=alert_color.upper()
		self.p25nac=p25nac

		try:
			self.dcs=scanner_ctcss_dcs[dcs]
			self.lout=scanner_lout[lockout]
			self.tlock=scanner_lout[tone_lockout]
			self.pri=scanner_onoff[priority]
			self.alt=scanner_alert_tones[alert_tone]
			self.altl=scanner_alert_tlevels[alert_level]
			self.audio_type=scanner_audiot[audio_type]
			self.alt_pattern=scanner_altp[pattern]

		except KeyError, e:
			self.logger.error('load(): keyerror %s' % str(e))
			return 0

		return 1

class TrunkFrequency():

	"""Scanner Trunk Frequency class."""

	def __init__(self, scanner, chn_index):

		self.logger = logging.getLogger('uniden_api.TrunkFrequency')

		self.scanner = scanner
		self.chn_index = chn_index
		self.frq='00000000'
		self.lcn=''
		self.lout='0'
		self.rev_index=None
		self.fwd_index=None
		self.sys_index=None
		self.grp_index=None
		self.number_tag='NONE'
		self.vol_offset='0'

	def get_data(self):

		"""Get Trunk Frequency Info
		In set command, only "," parameters are not changed.
                The set command is aborted if any format error is detected.
		For Motorola or EDACS SCAT System, [LCN] is ignored.
		When the system protect bit is ON, except [NAME], [REV_INDEX], [FWD_INDEX],
                [SYS_INDEX], [CHN_HEAD], [CHN_TAIL], other parameters will be send as a reserve
                parameter in the Radio -> Controller command.

		CHN_INDEX		Trunk Frequency Index
		FRQ			Trunk Frequency
		LCN			LCN EDACS (WIDE/NARROW system: 1 to 30, LTR system: 1 to 20)
		LOUT			Lockout (0:Unlocked / 1:Lockout)
		REV_INDEX		Reverse Frequency Index of the Site
		FWD_INDEX		Forward Frequency Index of the Site
		SYS_INDEX		System Index of the Frequency
		GRP_INDEX		Index of the Site
		NUMBER_TAG		Number tag (0-999 / NONE)
		VOL_OFFSET		Volume Offset (-3 - +3)"""

		cmd = ','.join(['TFQ',self.chn_index])

                try:
			res = self.scanner.raw(cmd)

		except CommandError:
			self.logger.error('get_data(): %s' % cmd)
			return 0

		(tfq,self.frq,self.lcn,self.lout,self.rev_index,self.fwd_index,
			self.sys_index,self.grp_index,rsv1,self.number_tag,
			self.vol_offset,rsv2) = res.split(',')

		return 1

	def set_data(self):

		"""Set scanner trunk frequency data to device."""

		rsv = ''
		cmd = ','.join(['TFQ',self.chn_index,self.frq,str(self.lcn),
				str(self.lout),rsv,str(self.number_tag),
				str(self.vol_offset),rsv])
                try:
			res = self.scanner.raw(cmd)

		except CommandError:
			self.logger.error('set_data(): %s' % cmd)
			return 0

		return 1

	def show(self):

		"""Shows trunk frequency data."""

		print ('--------TRUNK FREQ-------')
		print ('Trunk Frequency Index:\t\t%s') % self.chn_index
		print ('Trunk Frequency:\t\t%s MHz') % frq_from_scanner(self.frq)
		print ('LCN:\t\t\t\t%s') % self.lcn
		print ('Lockout:\t\t\t%s') % human_lout[self.lout]
		print ('Reverse Frequency Index:\t%s') % self.rev_index
		print ('Forward Frequency Index:\t%s') % self.fwd_index
		print ('System Index:\t\t\t%s') % self.sys_index
		print ('Site Index:\t\t\t%s') % self.grp_index
		print ('Number tag:\t\t\t%s') % self.number_tag
		print ('Volume Offset:\t\t\t%s') % self.vol_offset

	def show_brief(self):

		"""Shows brief group data: index, frequency."""

		print ('\t\tIndex: %s\tFrequency: %s') % (self.chn_index, frq_from_scanner(self.frq))

	def dump(self):

		"""Dumps group data to dictionary."""

		frq=frq_from_scanner(self.frq)
		lout=human_lout[self.lout]
		vol=self.vol_offset

		d={'frequency':frq, 'lcn':self.lcn, 'lockout':lout, 'tag':self.number_tag, 'vol_offset':vol}
		
		return d

	def load(self, frequency='0', lcn='0', lockout='unlock', tag='NONE', vol_offset='0'):

		"""Loads dictionary to group class."""

		self.frq=frq_to_scanner(frequency)
		self.number_tag=str(tag)
		self.vol_offset=str(vol_offset)

		try:
			self.lout=scanner_lout[lockout]

		except KeyError:
			self.logger.error('load(): keyerror %s' % str(e))
			return 0

		return 1

class TalkGroupID():

	"""Scanner TalkGroupID class."""

	def __init__(self, scanner, chn_index):

		self.logger = logging.getLogger('uniden_api.TalkGroupID')

		self.scanner = scanner
		self.chn_index = chn_index
		self.name='NONAME'
		self.tgid='0'
		self.lout='0'
		self.pri='0'
		self.alt='0'
		self.altl='0'
		self.rev_index=None
		self.fwd_index=None
		self.sys_index=None
		self.grp_index=None
		self.audio_type='0'
		self.number_tag='NONE'
		self.alt_color='OFF'
		self.alt_pattern='0'
		self.vol_offset='0'
		
	def get_data(self):

		"""Get TGID Information
		In set command, only "," parameters are not changed.
                The set command is aborted if any format error is detected.
                When the system protect bit is ON, except [NAME], [REV_INDEX], [FWD_INDEX],
                [SYS_INDEX], [CHN_HEAD], [CHN_TAIL], other parameters will be send as a reserve
                parameter in the Radio -> Controller command.

		INDEX		TGID Index
		NAME		Name (max.16char)
		TGID		TGID
		LOUT		Lockout (0:Unlocked / 1:Lockout)
		PRI		Priority (0:OFF / 1:ON)
		ALT		Alert Tone (0:OFF / 1-9:Tone No)
		ALTL		Alert Tone Level (0:AUTO/ 1-15)
		REV_INDEX	Reverse TGID Index of the Group
		FWD_INDEX	Forward TGID Index of the Group
		SYS_INDEX	System Index of the TGID
		GRP_INDEX	Group Index of the TGID
		AUDIO_TYPE	Audio Type ( 0:All / 1:Analog Only / 2: Digital Only )
		NUMBER_TAG 	Number tag (0-999 / NONE)
		ALT_COLOR 	Alert Light color (OFF,BLUE,RED,MAGENTA,GREEN,CYAN,YELLOW,WHITE)
		ALT_PATTERN	Alert Light Pattern(0:ON / 1:SLow / 2:Fast)
		VOL_OFFSET	Volume Offset (-3 - +3)"""

		cmd = ','.join(['TIN',self.chn_index])

                try:
			res = self.scanner.raw(cmd)

		except CommandError:
			self.logger.error('get_data(): %s' % cmd)
			return 0

		(tin,self.name,self.tgid,self.lout,self.pri,self.alt,self.altl,
			self.rev_index,self.fwd_index,self.sys_index,self.grp_index,
			rsv1,self.audio_type,self.number_tag,self.alt_color,
			self.alt_pattern,self.vol_offset) = res.split(',')

		return 1

	def set_data(self):

		"""Set scanner TGID data to device."""

		rsv = ''
		cmd = ','.join(['TIN',self.chn_index,self.name,str(self.tgid),str(self.lout),
				str(self.pri),str(self.alt),str(self.altl),rsv,str(self.audio_type),
				str(self.number_tag),self.alt_color,str(self.alt_pattern),
				str(self.vol_offset)])

                try:
			res = self.scanner.raw(cmd)

		except CommandError:
			self.logger.error('set_data(): %s' % cmd)
			return 0

		return 1

	def show(self):

		"""Shows TGID data."""

		print ('--------TGID-------')
		print ('TGID Index:\t\t\t%s') % self.chn_index
		print ('Name:\t\t\t\t%s') % self.name
		print ('TGID:\t\t\t\t%s') % self.tgid
		print ('Lockout:\t\t\t%s') % human_lout[self.lout]
		print ('Priority:\t\t\t%s') % human_onoff[self.pri]
		print ('Alert Tone:\t\t\t%s') % human_alert_tones[self.alt]
		print ('Alert Tone Level:\t\t%s') % human_alert_tlevels[self.altl]
		print ('Reverse Channel Index:\t\t%s') % self.rev_index
		print ('Forward Channel Index:\t\t%s') % self.fwd_index
		print ('System Index:\t\t\t%s') % self.sys_index
		print ('Group Index:\t\t\t%s') % self.grp_index
		print ('Audio Type:\t\t\t%s') % self.audio_type
		print ('Number tag:\t\t\t%s') % self.number_tag
		print ('Alert Light color:\t\t%s') % self.alt_color
		print ('Alert Light Pattern:\t\t%s') % human_altp[self.alt_pattern]
		print ('Volume Offset:\t\t\t%s') % self.vol_offset

	def show_brief(self):

		"""Shows brief TGID data."""

		print ('\t\tIndex: %s\tName: %s\tTGID: %s\tLockout:%s') % (self.chn_index,self.name,self.tgid,human_lout[self.lout])

	def dump(self):

		"""Dumps group data to dictionary."""

		audiot='all'
		if self.audio_type: audiot=human_audiot[self.audio_type]
		lout=human_lout[self.lout]
		pri=human_onoff[self.pri]
		altp=human_altp[self.alt_pattern]
		vol=self.vol_offset

		d={'name':self.name, 'tgid':self.tgid, 'lockout':lout, 'priority':pri, 'alert_tone':self.alt,
			'alert_level':self.altl, 'audio_type':audiot, 'tag':self.number_tag, 
			'alert_color':self.alt_color, 'pattern':altp, 'vol_offset':vol}

		return d

	def load(self, name='NONAME', tgid='0', lockout='unlock', priority='off', alert_tone='off', 
			alert_level='auto', audio_type='all', tag='NONE', alert_color='off', 
			pattern='on', vol_offset='0'):

		"""Loads dictionary to group class."""

		self.name=name
		self.tgid=str(tgid)
		self.number_tag=str(tag)
		self.vol_offset=str(vol_offset)
		self.alt_color=alert_color.upper()

		try:
			self.lout=scanner_lout[lockout]
			self.pri=scanner_onoff[priority]
			self.alt=scanner_alert_tones[alert_tone]
			self.altl=scanner_alert_tlevels[alert_level]
			self.audio_type=scanner_audiot[audio_type]
			self.alt_pattern=scanner_altp[pattern]

		except KeyError:
			self.logger.error('load(): keyerror %s' % str(e))
			return 0

		return 1

class Search:

	"""Scanner Search class."""

	def __init__(self, scanner):

		self.logger = logging.getLogger('uniden_api.Search')

		self.scanner = scanner
		self.srch_close_call = {}
		self.bcast_screen_band = {}
		self.search_key = ()
		self.global_lout_frqs = ()
		self.close_call = {}
		self.service_search = {}
		self.custom_search = {}
		self.custom_search_group = ()
		self.cch_custom_search_mot_band_plan = {}
		self.band_scope_system = {}

	def get_data(self):

		"""Get Search/Close Call Settings.
	
                MOD             Modulation (AUTO/AM/FM/NFM/WFM/FMB)
                ATT             Attenuation (0:OFF / 1:ON)
                DLY             Delay Time (-10,-5,-2,0,1,2,5,10,30)
                CODE_SRCH       CTCSS/DCS/P25 NAC Search (0:OFF / 1: CTCSS/DCS / 2: P25 NAC Search)
                BSC             Broadcast Screen (16digit: ########・・#)
                (each # is 0 or 1)                         ||||||||・・+- Band10
                0 means OFF                                ||||||||       :
                1 means ON                                 |||||||+---- Band 2
                                                           ||||||+----- Band 1
                                                           |||||+------ Reserve
                                                           ||||+------- NOAA WX
                                                           |||+-------- VHF TV
                                                           ||+--------- UHF TV
                                                           |+---------- FM
                                                           +----------- Pager
                REP             Repeater Find (0:OFF / 1:ON)
		MAX_STORE	Max Auto Store (1-256)
                AGC_ANALOG      AGC Setting for Analog Audio (0:OFF / 1:ON)
                AGC_DIGITAL     AGC Setting for Digital Audio (0:OFF / 1:ON)
                P25WAITING      P25 Waiting time (0,100,200,300, .... , 900,1000) ms

		Get Search Key Settings

		SRCH_KEY_1 - SRCH_KEY_3		Search Range
		PublicSafety	Public Safety range		CUSTOM_1	Custom 1 range
		News		News range			CUSTOM_2	Custom 2 range
		HAM		HAM range			CUSTOM_3	Custom 3 range
		Marine		Marine range			CUSTOM_4	Custom 4 range
		Railroad	Railroad range			CUSTOM_5	Custom 5 range
		Air		Air range			CUSTOM_6	Custom 6 range
		CB		CB range			CUSTOM_7	Custom 7 range
		FRS/GMRS/MURS	FRS/GMRS/MURS range		CUSTOM_8	Custom 8 range
		Racing		Racing range			CUSTOM_9	Custom 9 range
		FM		FM range			CUSTOM_10	Custom 10 range
		Special		Special range			TONE_OUT	Tone Out mode
		Military	Military range			B_SCOPE		Band Scope

		Get Close Call Settings

		CC_MODE		Mode ( 0:OFF / 1:CC PRI / 2:CC DND)
		CC_OVERRIDE	Override (1:ON / 0:OFF)
		ALTB		Alert Beep (0:OFF / 1-9:Tone No)
		ALTL		Alert Tone Level (0:AUTO/ 1-15)
		ALTP		Close Call Pause 3,5,10,15,30,45,60,INF
		CC_BAND		Close Call Band (7digit ####### )
				(each # is 0 or 1)      ||||||+- 800MHz+
					0 means OFF     |||||+-- UHF
					1 means ON	||||+--- VHF HIGH2
							|||+---- VHF HIGH1
							||+----- AIR BAND
							|+------ VHF LOW2
							+------- VHF LOW1
		LOUT		Lockout for CC Hits with Scan (0:Unlocked / 1:Lockout)
		HLD		System Hold Time for CC Hits with Scan (0-255)
		QUICK_KEY	Quick Key for CC Hits with Scan ( 0 – 99 / .(dot) )
		NUMBER_TAG	Number tag (0-999 / NONE)
		ALT_COLOR	Alert Light color (OFF,BLUE,RED,MAGENTA,GREEN,CYAN,YELLOW,WHITE)
		ALT_PATTERN	Alert Light Pattern(0:ON / 1:SLow / 2:Fast)

		Get Custom Search Group

		########## (each # is 0 or 1) 	0 : valid/ 1 : invalid
		The Order of Range is as same as LCD Icon (1 – 10).

		Get Band Scope System Settings

		FRQ		Center Frequency
		STP		Search Step 5k, 6.25k, 7.5k, 8.33k, 10k, 12.5k, 15k, 20k, 25k, 50k, 100k
		SPN		Sweep Span 0.2M, 0.4M, 0.6M, 0.8M, 1M, 2M, 4M, 6M, 8M, 10M, 20M, 40M, 60M,
						80M, 100M, 120M, 140M, 160M, 180M, 200M, 250M, 300M, 350M,
						400M, 450M, 500M
		MAX_HOLD	Max Hold Display (0:OFF / 1:ON)

		Get Broadcast Screen Band Settings

		INDEX		Index (1-9,0 means 10)
		LIMIT_L		Lower Limit Frequency (00000000 –99999999)
		LIMIT_H		Upper Limit Frequency (00000000 –99999999)

		Get Band Plan Setting for MOT 800custom/VHF/UHFsite when trunking control
		channel in custom search.

		SRCH_INDEX		Index (1-9,0 means 10)
		MOT_TYPE		Band type for MOT(STD/ SPL/CUSTOM)
		LOWER n			Lower Frequency n
		UPPER n			Upper Frequency n
		STEP n			Step n 5, 6.25, 10, 12.5, 15, 18.75, 20, 25, 30, 31.25, 35, 37.5
						40, 43.75, 45, 50, 55, 56.25, 60, 62.5, 65, 68.75, 70, 75,
						80, 81.25, 85, 87.5, 90, 93.75, 87.5, 90, 93.75, 95, 100
		OFFSET n		Offset n (-1023 to 1023)

		In set command, if only "," parameters are send the Band Plan setting will not changed. The
		set command is aborted if any format error is detected.
		If [MOT_TYPE] is not CUSTOM, any other setting will be ignored.

		Get Custom Search Settings

		SRCH_INDEX		Index (1-9,0 means 10)
		NAME			Name	(max.16char)
		LIMIT_L			Lower Limit Frequency (250000-13000000)
		LIMIT_H			Upper Limit Frequency (250000-13000000)
		STP			Search Step AUTO, 5, 6.25, 7.5, 8.33, 10, 12.5, 15, 20, 25, 50, 100
		MOD			Modulation (AUTO / AM / FM / NFM / WFM / FMB)
		ATT			Attenuation (0:OFF / 1:ON)
		DLY			Delay Time (-10,-5,-2,0,1,2,5,10,30)
		HLD			System Hold Time (0-255)
		LOUT			Lockout (0:Unlocked / 1:Lockout)
		C-CH			Control Channel Only (0:OFF / 1:ON)
		QUICK_KEY 		Quick Key (0 – 99 / .(dot) )
		START_KEY 		Startup Configuration Key (0 - 9/ .(dot))
		NUMBER_TAG 		Number tag (0-999 / NONE)
		AGC_ANALOG 		AGC Setting for Analog Audio (0:OFF / 1:ON)
		AGC_DIGITAL 		AGC Setting for Digital Audio (0:OFF / 1:ON)
		P25WAITING 		P25 Waiting time (0,100,200,300, .... , 900,1000)
		
		Get Service Search Settings

		SRCH_INDEX		Service Search Range
					1 - Public Safety,	6 - Air,	12 - Special
					2 - News		7 - CB Radio,	15 - Military Air
					3 - HAM Radio		8 - FRS/GMRS/MURS
					4 - Marine		9 - Racing
					5 - Railroad		11 - FM Broadcast

		DLY			Delay Time (-10,-5,-2,0,1,2,5,10,30)
		ATT			Attenuation (0:OFF / 1:ON)
		HLD			System Hold Time (0-255)
		LOUT			Lockout (0:Unlocked / 1:Lockout)
		QUICK_KEY 		Quick Key (0 – 99 / .(dot) )
		START_KEY 		Startup Configuration Key (0 - 9/ .(dot))
		NUMBER_TAG 		Number tag (0-999 / NONE)
		AGC_ANALOG 		AGC Setting for Analog Audio (0:OFF / 1:ON)
		AGC_DIGITAL 		AGC Setting for Digital Audio (0:OFF / 1:ON)
		P25WAITING 		P25 Waiting time (0,100,200,300, .... , 900,1000)"""

		try:
			sco = self.scanner.raw('SCO')
			shk = self.scanner.raw('SHK')
			clc = self.scanner.raw('CLC')
			csg = self.scanner.raw('CSG')
			bsp = self.scanner.raw('BSP')
			
		except CommandError:
			self.logger.error('get_data(): %s' % cmd)
			return 0

		(sco,rsv1,mod,att,dly,rsv2,code_srch,bsc,rep,rsv3,rsv4,
			max_store,rsv5,agc_analog,agc_digital,p25waiting) = sco.split(',')
		self.srch_close_call = {'modulation':mod, 'attenuate':att, 'delay':dly, 'code_srch':code_srch,
				'bscreen':bsc, 'repeater':rep, 'max_store':max_store, 'agc_analog':agc_analog,
				'agc_digital':agc_digital, 'p25waiting':p25waiting }

		(shk,srch_key_1,srch_key_2,srch_key_3,rsv1,rsv2,rsv3) = shk.split(',')
		self.search_key = (0,srch_key_1,srch_key_2,srch_key_3)
		
		(clc,cc_mode,cc_override,rsv1,altb,altl,altp,cc_band,
			lout,hld,quick_key,number_tag,alt_color,alt_pattern) = clc.split(',')
		self.close_call = {'mode':cc_mode, 'override':cc_override, 'beep':altb,
				'level':altl, 'pause':altp, 'band':cc_band, 'lockout':lout,
				'hold':hld, 'quick_key':quick_key, 'number_tag':number_tag,
				'color':alt_color, 'pattern':alt_pattern}

		(csg,n) = csg.split(',')
		self.custom_search_group = tuple(n)

		(bsp,frq,stp,spn,max_hold) = bsp.split(',')
		
		self.band_scope_system = {'frequency':frq, 'step':stp, 'span':spn, 'max_hold':max_hold}		

		limits={}
		band_plan={}
		cust_srch={}

		for index in range(0,10):

			try:
				bbs = self.scanner.raw(','.join(['BBS',str(index)]))
				cbp = self.scanner.raw(','.join(['CBP',str(index)]))
				csp = self.scanner.raw(','.join(['CSP',str(index)]))
			
			except CommandError:
				self.logger.error('get_data(): %s' % cmd)
				return 0

			(bbs,limit_l,limit_h) = bbs.split(',')
			limits[index]={'limit_l':limit_l, 'limit_h':limit_h}

			(cbp,mot_type,lower1,upper1,step1,offset1,
				lower2,upper2,step2,offset2,lower3,upper3,step3,offset3,
				lower4,upper4,step4,offset4,lower5,upper5,step5,offset5,
				lower6,upper6,step6,offset6) = cbp.split(',')
			band_plan[index]={'mot_type':mot_type, 
				'lower': (0,lower1,lower2,lower3,lower4,lower5,lower6),
				'upper': (0,upper1,upper2,upper3,upper4,upper5,upper6),
				'step': (0,step1,step2,step3,step4,step5,step6),
				'offset': (0,offset1,offset2,offset3,offset4,offset5,offset6)}

			(csp,name,limit_l,limit_h,stp,mod,att,dly,rsv1,hld,lout,cch,
				rsv2,rsv3,quick_key,start_key,rsv4,number_tag,agc_analog,
				agc_digital,p25waiting) = csp.split(',')
			cust_srch[index]={'name':name, 'limit_l':limit_l, 'limit_h':limit_h,
					'step':stp, 'modulation':mod, 'attenuation':att, 'delay':dly, 'hold':hld,
					'lockout':lout, 'cch':cch, 'quick_key':quick_key,
					'start_key':start_key,'number_tag':number_tag,
					'agc_analog':agc_analog, 'agc_digital':agc_digital,
					'p25waiting':p25waiting}

		self.bcast_screen_band = limits
		self.cch_custom_search_mot_band_plan = band_plan
		self.custom_search = cust_srch

		indexes = (1,2,3,4,5,6,7,8,9,11,12,15)

		for index in indexes:

			try:
				ssp = self.scanner.raw(','.join(['SSP',str(index)]))
			
			except CommandError:
				self.logger.error('get_data(): %s' % cmd)
				return 0

			(ssp,srch_index,dly,att,hld,lout,quick_key,start_key,rsv1,
				number_tag,agc_analog,agc_digital,p25waiting) = ssp.split(',')

			self.service_search[index] = {'delay':dly, 'attenuation':att, 'hold':hld,
					'lockout':lout, 'quick_key':quick_key, 'start_key':start_key,
					'number_tag':number_tag, 'agc_analog':agc_analog,
					'agc_digital':agc_digital, 'p25waiting':p25waiting}

		self.get_global_lockout_frqs()

		return 1

	def set_data(self):

		"""Set scanner search data to device."""

		rsv = ''
		sco = ','.join(['SCO',rsv,self.srch_close_call['modulation'],str(self.srch_close_call['attenuate']),
				str(self.srch_close_call['delay']),rsv,str(self.srch_close_call['code_srch']),
				self.srch_close_call['bscreen'],str(self.srch_close_call['repeater']),rsv,rsv,
				str(self.srch_close_call['max_store']),rsv,str(self.srch_close_call['agc_analog']),
				str(self.srch_close_call['agc_digital']),str(self.srch_close_call['p25waiting'])])
		shk = ','.join(['SHK',self.search_key[1],self.search_key[2],self.search_key[3],rsv,rsv,rsv])
		clc = ','.join(['CLC',str(self.close_call['mode']),str(self.close_call['override']),rsv,
				str(self.close_call['beep']),str(self.close_call['level']),str(self.close_call['pause']),
				self.close_call['band'],str(self.close_call['lockout']),str(self.close_call['hold']),
				str(self.close_call['quick_key']),str(self.close_call['number_tag']),
				self.close_call['color'],str(self.close_call['pattern'])])
		csg = ','.join(['CSG',''.join(self.custom_search_group)])
		bsp = ','.join(['BSP',self.band_scope_system['frequency'],self.band_scope_system['step'],
					self.band_scope_system['span'],str(self.band_scope_system['max_hold'])])
	
		try:
			sco = self.scanner.raw(sco)
			shk = self.scanner.raw(shk)
			clc = self.scanner.raw(clc)
			csg = self.scanner.raw(csg)
			bsp = self.scanner.raw(bsp)
			
		except CommandError:
			self.logger.error('set_data(): some commands failed.')

		for index in range(0,10):

			bbs = ','.join(['BBS',str(index),str(self.bcast_screen_band[index]['limit_l']),
					str(self.bcast_screen_band[index]['limit_h'])])
			cbp0 = self.cch_custom_search_mot_band_plan[index]
			cbp = ','.join(['CBP',str(index),cbp0['mot_type']])
			for i in range(1,7):
				cbp = ','.join([cbp,cbp0['lower'][i],cbp0['upper'][i],
						str(cbp0['step'][i]),cbp0['offset'][i]])
			csp0 = self.custom_search[index]
			csp = ','.join(['CSP',str(index),csp0['name'],csp0['limit_l'],csp0['limit_h'],
					str(csp0['step']),csp0['modulation'],str(csp0['attenuation']),str(csp0['delay']),
					rsv,str(csp0['hold']),str(csp0['lockout']),str(csp0['cch']),rsv,rsv,
					str(csp0['quick_key']),str(csp0['start_key']),rsv,
					str(csp0['number_tag']),str(csp0['agc_analog']),
					str(csp0['agc_digital']),str(csp0['p25waiting'])])
			try:
				bbs = self.scanner.raw(bbs)
				cbp = self.scanner.raw(cbp)
				csp = self.scanner.raw(csp)
			
			except CommandError:
				self.logger.error('set_data(): some commands failed.')

		indexes = (1,2,3,4,5,6,7,8,9,11,12,15)

		for index in indexes:

			ssp0=self.service_search[index]
			ssp = ','.join(['SSP',str(index),str(ssp0['delay']),str(ssp0['attenuation']),str(ssp0['hold']),
					str(ssp0['lockout']),str(ssp0['quick_key']),str(ssp0['start_key']),rsv,
					str(ssp0['number_tag']),str(ssp0['agc_analog']),
					str(ssp0['agc_digital']),str(ssp0['p25waiting'])])
			try:
				ssp = self.scanner.raw(ssp)
			
			except CommandError:
				self.logger.error('set_data(): some commands failed.')

		return 1

	def get_global_lockout_frqs(self):

		"""This command is used to get Global L/O frequency list.
		You should call this command again and again to get all-global L/O frequency until the
		scanner returns "-1".
		"-1" means that no more L/O frequency exists.
		FRQ		Lockout Frequency (250000-13000000)"""

		frqs=[]
		frq=0

		while int(frq) <> -1:

			try:
				glf = self.scanner.raw('GLF')
			
			except CommandError:
				self.logger.error('get_global_lockout_frqs()')
				return 0

			(glf,frq) = glf.split(',')
			frqs.append(frq)

		self.global_lout_frqs = tuple(frqs)

	def unlock_global_frq(self, frq):

		"""This command unlocks a L/O frequency.
		The frequency is deleted from L/O list.

		FRQ		Lockout Frequency (250000-13000000)"""

		try:
			ulf = self.scanner.raw(','.join(['ULF',frq]))

		except CommandError:
			self.logger.error('unlock_global_frq(): %s' % frq)
			return 0

		self.global_lout_frqs = ()
		self.get_global_lockout_frqs()

		return 1

	def lock_global_frq(self, frq):

		"""This command locks out a frequency.
		The frequency is added to L/O list.

		FRQ		Lockout Frequency (250000-13000000)"""

		try:
			ulf = self.scanner.raw(','.join(['LOF',frq]))

		except CommandError:
			self.logger.error('lock_global_frq(): %s' % frq)
			return 0

		self.global_lout_frqs = ()
		self.get_global_lockout_frqs()

		return 1

	def dump(self):

		"""Dumps group data to dictionary."""

		scc=self.srch_close_call
		scc['agc_analog']=human_onoff[scc['agc_analog']]
		scc['agc_digital']=human_onoff[scc['agc_digital']]
		scc['attenuate']=human_onoff[scc['attenuate']]
		scc['repeater']=human_onoff[scc['repeater']]
		scc['code_srch']=human_ctcss_dcs[scc['code_srch']]

		cc=self.close_call
		cc['pattern']=human_altp[cc['pattern']]
		cc['beep']=human_alert_tones[cc['beep']]
		cc['level']=human_alert_tlevels[cc['level']]
		cc['override']=human_onoff[cc['override']]
		cc['lockout']=human_lout[cc['lockout']]
		cc['mode']=human_cc_modes[cc['mode']]
		
		bss=self.band_scope_system
		bss['frequency']=frq_from_scanner(bss['frequency'])
		bss['step']=str(float(bss['step'])/100)

		ss=self.service_search
		indexes = (1,2,3,4,5,6,7,8,9,11,12,15)
		for i in indexes:
			ss[i]['agc_analog']=human_onoff[ss[i]['agc_analog']]
			ss[i]['agc_digital']=human_onoff[ss[i]['agc_digital']]
			ss[i]['attenuation']=human_onoff[ss[i]['attenuation']]
			ss[i]['lockout']=human_lout[ss[i]['lockout']]

		bsb=self.bcast_screen_band
		cs=self.custom_search
		ccsmbp=self.cch_custom_search_mot_band_plan
		for i in range(0,10):
			bsb[i]['limit_l']=frq_from_scanner(bsb[i]['limit_l'])
			bsb[i]['limit_h']=frq_from_scanner(bsb[i]['limit_h'])
			cs[i]['agc_analog']=human_onoff[cs[i]['agc_analog']]
			cs[i]['agc_digital']=human_onoff[cs[i]['agc_digital']]
			cs[i]['attenuation']=human_onoff[cs[i]['attenuation']]
			cs[i]['cch']=human_onoff[cs[i]['cch']]
			cs[i]['limit_l']=frq_from_scanner(cs[i]['limit_l'])
			cs[i]['limit_h']=frq_from_scanner(cs[i]['limit_h'])
			cs[i]['lockout']=human_lout[cs[i]['lockout']]
			cs[i]['step']=str(float(cs[i]['step'])/100)
			ccsmbp[i]['lower']=list(ccsmbp[i]['lower'])
			ccsmbp[i]['upper']=list(ccsmbp[i]['upper'])
			ccsmbp[i]['step']=list(ccsmbp[i]['step'])
			ccsmbp[i]['offset']=list(ccsmbp[i]['offset'])
			for j in range(1,7):
				if ccsmbp[i]['lower'][j]!='':
					ccsmbp[i]['lower'][j]=frq_from_scanner(ccsmbp[i]['lower'][j])
				if ccsmbp[i]['upper'][j]!='':
					ccsmbp[i]['upper'][j]=frq_from_scanner(ccsmbp[i]['upper'][j])
				if ccsmbp[i]['step'][j]!='':
					ccsmbp[i]['step'][j]=str(float(ccsmbp[i]['step'][j])/100)
		
		sk=list(self.search_key)
		glf=list(self.global_lout_frqs)
		csg=list(self.custom_search_group)

		d={'srch_close_call':scc, 'bcast_screen_band':bsb, 'search_key':sk,
			'global_lout_frqs':glf, 'close_call':cc, 'service_search':ss,
			'custom_search':cs, 'custom_search_group':csg,
			'mot_band_plan':ccsmbp, 'band_scope_system':bss}

		return d

	def load(self,srch_close_call={},search_key=[],close_call={},custom_search_group=[],
			band_scope_system={}, bcast_screen_band={}, custom_search={},
			mot_band_plan={},global_lout_frqs=[],service_search={}):

		"""Loads dictionary to group class."""

		self.logger.debug('load(): srch_close_call dictionary '+str(srch_close_call))

		try:
			if 'agc_analog' not in srch_close_call: self.srch_close_call['agc_analog']=''
			else: self.srch_close_call['agc_analog']=scanner_onoff[srch_close_call['agc_analog']]
			if 'agc_digital' not in srch_close_call: self.srch_close_call['agc_digital']=''
			else: self.srch_close_call['agc_digital']=scanner_onoff[srch_close_call['agc_digital']]
			if 'attenuate' not in srch_close_call: self.srch_close_call['attenuate']=''
			else: self.srch_close_call['attenuate']=scanner_onoff[srch_close_call['attenuate']]
			if 'bscreen' not in srch_close_call: self.srch_close_call['bscreen']=''
			else: self.srch_close_call['bscreen']=srch_close_call['bscreen']
			if 'code_srch' not in srch_close_call: self.srch_close_call['code_srch']=''
			else: self.srch_close_call['code_srch']=scanner_ctcss_dcs[srch_close_call['code_srch']]
			if 'delay' not in srch_close_call: self.srch_close_call['delay']=''
			else: self.srch_close_call['delay']=srch_close_call['delay']
			if 'max_store' not in srch_close_call: self.srch_close_call['max_store']=''
			else: self.srch_close_call['max_store']=srch_close_call['max_store']
			if 'modulation' not in srch_close_call: self.srch_close_call['modulation']=''
			else: self.srch_close_call['modulation']=srch_close_call['modulation']
			if 'p25waiting' not in srch_close_call: self.srch_close_call['p25waiting']=''
			else: self.srch_close_call['p25waiting']=srch_close_call['p25waiting']
			if 'repeater' not in srch_close_call: self.srch_close_call['repeater']=''
			else: self.srch_close_call['repeater']=scanner_onoff[srch_close_call['repeater']]
		except Exception, e:
			self.logger.error('load(): srch_close_call error %s' % str(e))

		self.logger.debug('load(): close_call dictionary '+str(close_call))
		try:
			if 'band' not in close_call: self.close_call['band']=''
			else: self.close_call['band']=close_call['band']
			if 'beep' not in close_call: self.close_call['beep']=''
			else: self.close_call['beep']=scanner_alert_tones[close_call['beep']]
			if 'color' not in close_call: self.close_call['color']=''
			else: self.close_call['color']=close_call['color']
			if 'hold' not in close_call: self.close_call['hold']=''
			else: self.close_call['hold']=close_call['hold']
			if 'level' not in close_call: self.close_call['level']=''
			else: self.close_call['level']=scanner_alert_tlevels[close_call['level']]
			if 'lockout' not in close_call: self.close_call['lockout']=''
			else: self.close_call['lockout']=scanner_lout[close_call['lockout']]
			if 'mode' not in close_call: self.close_call['mode']=''
			else: self.close_call['mode']=scanner_cc_modes[close_call['mode']]
			if 'number_tag' not in close_call: self.close_call['number_tag']=''
			else: self.close_call['number_tag']=close_call['number_tag']
			if 'override' not in close_call: self.close_call['override']=''
			else: self.close_call['override']=scanner_onoff[close_call['override']]
			if 'pattern' not in close_call: self.close_call['pattern']=''
			else: self.close_call['pattern']=scanner_altp[close_call['pattern']]
			if 'pause' not in close_call: self.close_call['pause']=''
			else: self.close_call['pause']=close_call['pause']
			if 'quick_key' not in close_call: self.close_call['quick_key']=''
			else: self.close_call['quick_key']=close_call['quick_key']
		except Exception, e:
			self.logger.error('load(): close_call error %s' % str(e))

		self.logger.debug('load(): band_scope_system dictionary '+str(band_scope_system))
		try:
			if 'frequency' not in band_scope_system: self.band_scope_system['frequency']=''
			else: self.band_scope_system['frequency']=frq_to_scanner(band_scope_system['frequency'])
			if 'max_hold' not in band_scope_system: self.band_scope_system['max_hold']=''
			else: self.band_scope_system['max_hold']=band_scope_system['max_hold']
			if 'span' not in band_scope_system: self.band_scope_system['span']=''
			else: self.band_scope_system['span']=band_scope_system['span']
			if 'step' not in band_scope_system: self.band_scope_system['step']=''
			else: self.band_scope_system['step']=str(100*float(band_scope_system['step']))
		except Exception, e:
			self.logger.error('load(): band_scope_system error %s' % str(e))

		for i in range(0,10):
			try:
				if i not in bcast_screen_band:
					self.bcast_screen_band[i]={'limit_l':'', 'limit_h':''}
				else:
					self.logger.debug('load(): bcast_screen_band dictionary '+str(bcast_screen_band[i]))

					self.bcast_screen_band[i]={'limit_l':frq_to_scanner(bcast_screen_band[i]['limit_l']),
								'limit_h':frq_to_scanner(bcast_screen_band[i]['limit_h'])}
			except Exception, e:
				self.logger.error('load(): bcast_screen_band error %s' % str(e))

				self.logger.debug('load(): self.bcast_screen_band dictionary '+str(self.bcast_screen_band[i]))

			try:
				if i not in custom_search:
					self.custom_search[i]={'agc_analog':'','agc_digital':'','attenuation':'','cch':'',
								'delay':'','hold':'','limit_h':'','limit_l':'','lockout':'',
								'modulation':'','name':'','number_tag':'','p25waiting':'',
								'quick_key':'','start_key':'','step':''}
				else:
					self.logger.debug('load(): custom_search dictionary '+str(custom_search[i]))

					self.custom_search[i]={}
					if 'agc_analog' not in custom_search[i]: self.custom_search[i].update({'agc_analog':''})
					else: self.custom_search[i].update({'agc_analog':scanner_onoff[custom_search[i]['agc_analog']]})
					if 'agc_digital' not in custom_search[i]: self.custom_search[i].update({'agc_digital':''})
					else: self.custom_search[i].update({'agc_digital':scanner_onoff[custom_search[i]['agc_digital']]})
					if 'attenuation' not in custom_search[i]: self.custom_search[i].update({'attenuation':''})
					else: self.custom_search[i].update({'attenuation':scanner_onoff[custom_search[i]['attenuation']]})
					if 'cch' not in custom_search[i]: self.custom_search[i].update({'cch':''})
					else: self.custom_search[i].update({'cch':scanner_onoff[custom_search[i]['cch']]})
					if 'delay' not in custom_search[i]: self.custom_search[i].update({'delay':''})
					else: self.custom_search[i].update({'delay':custom_search[i]['delay']})
					if 'hold' not in custom_search[i]: self.custom_search[i].update({'hold':''})
					else: self.custom_search[i].update({'hold':custom_search[i]['hold']})
					if 'limit_l' not in custom_search[i]: self.custom_search[i].update({'limit_l':''})
					else: self.custom_search[i].update({'limit_l':frq_to_scanner(custom_search[i]['limit_l'])})
					if 'limit_h' not in custom_search[i]: self.custom_search[i].update({'limit_h':''})
					else: self.custom_search[i].update({'limit_h':frq_to_scanner(custom_search[i]['limit_h'])})
					if 'lockout' not in custom_search[i]: self.custom_search[i].update({'lockout':''})
					else: self.custom_search[i].update({'lockout':scanner_lout[custom_search[i]['lockout']]})
					if 'modulation' not in custom_search[i]: self.custom_search[i].update({'modulation':''})
					else: self.custom_search[i].update({'modulation':custom_search[i]['modulation']})
					if 'name' not in custom_search[i]: self.custom_search[i].update({'name':''})
					else: self.custom_search[i].update({'name':custom_search[i]['name']})
					if 'number_tag' not in custom_search[i]: self.custom_search[i].update({'number_tag':''})
					else: self.custom_search[i].update({'number_tag':custom_search[i]['number_tag']})
					if 'p25waiting' not in custom_search[i]: self.custom_search[i].update({'p25waiting':''})
					else: self.custom_search[i].update({'p25waiting':custom_search[i]['p25waiting']})
					if 'quick_key' not in custom_search[i]: self.custom_search[i].update({'quick_key':''})
					else: self.custom_search[i].update({'quick_key':custom_search[i]['quick_key']})
					if 'start_key' not in custom_search[i]: self.custom_search[i].update({'start_key':''})
					else: self.custom_search[i].update({'start_key':custom_search[i]['start_key']})
					if 'step' not in custom_search[i]: self.custom_search[i].update({'step':''})
					else: self.custom_search[i].update({'step':str(int(100*float(custom_search[i]['step'])))})
			except Exception, e:
				self.logger.error('load(): custom_search error %s' % str(e))

				self.logger.debug('load(): self.custom_search dictionary '+str(self.custom_search[i]))

			try:
				self.cch_custom_search_mot_band_plan[i]={}
				if i not in mot_band_plan:
					self.cch_custom_search_mot_band_plan[i].update({'lower':(0,'','','','','','')})
					self.cch_custom_search_mot_band_plan[i].update({'upper':(0,'','','','','','')})
					self.cch_custom_search_mot_band_plan[i].update({'step':(0,'','','','','','')})
					self.cch_custom_search_mot_band_plan[i].update({'offset':(0,'','','','','','')})
					self.cch_custom_search_mot_band_plan[i].update({'mot_type':''})
				else:
					self.logger.debug('load(): mot_band_plan dictionary '+str(mot_band_plan[i]))

					for j in range(1,7):
						if mot_band_plan[i]['step'][j]!='':
							mot_band_plan[i]['step'][j]=str(int(100*float(mot_band_plan[i]['step'][j])))
				
					self.cch_custom_search_mot_band_plan[i]={}	
					mot_band_plan[i].update({'lower':map(frq_to_scanner,mot_band_plan[i]['lower'])})
					mot_band_plan[i].update({'upper':map(frq_to_scanner,mot_band_plan[i]['upper'])})
					self.cch_custom_search_mot_band_plan[i].update({'mot_type':mot_band_plan[i]['mot_type']})
					self.cch_custom_search_mot_band_plan[i].update({'offset':tuple(mot_band_plan[i]['offset'])})
					self.cch_custom_search_mot_band_plan[i].update({'lower':tuple(mot_band_plan[i]['lower'])})
					self.cch_custom_search_mot_band_plan[i].update({'upper':tuple(mot_band_plan[i]['upper'])})
					self.cch_custom_search_mot_band_plan[i].update({'step':tuple(mot_band_plan[i]['step'])})
			except Exception, e:
				self.logger.error('load(): mot_band_plan %s' % str(e))


		indexes = (1,2,3,4,5,6,7,8,9,11,12,15)
		
		for i in indexes:
			try:
				if i not in service_search:
					self.service_search[i]={'agc_analog':'','agc_digital':'','attenuation':'',
								'delay':'','hold':'','lockout':'','number_tag':'',
								'p25waiting':'','quick_key':'','start_key':''}
				else:
					self.logger.debug('load(): service_search dictionary '+str(service_search))

					self.service_search[i]={}
					if 'agc_analog' not in service_search[i]: self.service_search[i].update({'agc_analog':''})
					else: self.service_search[i].update({'agc_analog':scanner_onoff[service_search[i]['agc_analog']]})
					if 'agc_digital' not in service_search[i]: self.service_search[i].update({'agc_digital':''})
                                        else: self.service_search[i].update({'agc_digital':scanner_onoff[service_search[i]['agc_digital']]})
                                        if 'attenuation' not in service_search[i]: self.service_search[i].update({'attenuation':''})
                                        else: self.service_search[i].update({'attenuation':scanner_onoff[service_search[i]['attenuation']]})
                                        if 'delay' not in service_search[i]: self.service_search[i].update({'delay':''})
                                        else: self.service_search[i].update({'delay':service_search[i]['delay']})
                                        if 'hold' not in service_search[i]: self.service_search[i].update({'hold':''})
                                        else: self.service_search[i].update({'hold':service_search[i]['hold']})
                                        if 'lockout' not in service_search[i]: self.service_search[i].update({'lockout':''})
                                        else: self.service_search[i].update({'lockout':scanner_lout[service_search[i]['lockout']]})
                                        if 'number_tag' not in service_search[i]: self.service_search[i].update({'number_tag':''})
                                        else: self.service_search[i].update({'number_tag':service_search[i]['number_tag']})
                                        if 'p25waiting' not in service_search[i]: self.service_search[i].update({'p25waiting':''})
                                        else: self.service_search[i].update({'p25waiting':service_search[i]['p25waiting']})
                                        if 'quick_key' not in service_search[i]: self.service_search[i].update({'quick_key':''})
                                        else: self.service_search[i].update({'quick_key':service_search[i]['quick_key']})
                                        if 'start_key' not in service_search[i]: self.service_search[i].update({'start_key':''})
                                        else: self.service_search[i].update({'start_key':service_search[i]['start_key']})

			except Exception, e:
				self.logger.error('load(), service search %s' % str(e))
				
		self.logger.debug('load(): self.service_search dictionary '+str(self.service_search[i]))
		
		if len(search_key) == 4: self.search_key=tuple(search_key)
		else: self.search_key=('','','','')
		if len(custom_search_group) == 10: self.custom_search_group=tuple(custom_search_group)
		else: self.custom_search_group=('','','','','','','','','','')
		if len(global_lout_frqs)>1: self.global_lout_frqs=tuple(global_lout_frqs)

if __name__ == "__main__":

	logger = logging.getLogger()
	logger.setLevel(logging.DEBUG)
	ch = logging.StreamHandler()
	ch.setLevel(logging.DEBUG)
	formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
	ch.setFormatter(formatter)
	logger.addHandler(ch)

	s=UnidenScanner("/dev/scanners/2110",57600)

	#s.get_system_settings()
	#print s.dump_system_settings()

	s.close()
