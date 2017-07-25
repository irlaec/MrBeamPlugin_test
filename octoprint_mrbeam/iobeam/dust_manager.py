import time
import threading
import numbers
from octoprint.events import Events as OctoPrintEvents
from octoprint_mrbeam.iobeam.iobeam_handler import IoBeamEvents
from octoprint_mrbeam.mrb_logger import mrb_logger

# singleton
_instance = None

def dustManager():
	global _instance
	if _instance is None:
		_instance = DustManager()
	return _instance

class DustManager(object):

	DEFAULT_DUST_TIMER_INTERVAL = 3
	DEFAUL_DUST_MAX_AGE = 10  # seconds

	def __init__(self):
		self._logger = mrb_logger("octoprint.plugins.mrbeam.iobeam.dustmanager")

		self._dust = None
		self._dust_ts = time.time()

		self._shutting_down = False
		self._trail_extraction = None
		self._dust_timer = None
		self._dust_timer_interval = self.DEFAULT_DUST_TIMER_INTERVAL
		self._auto_timer = None

		self._subscribe()
		self._start_dust_timer()
		self._stop_dust_extraction()

		self.extraction_limit = _mrbeam_plugin_implementation.laserCutterProfileManager.get_current_or_default()['dust']['extraction_limit']
		self.auto_mode_time = _mrbeam_plugin_implementation.laserCutterProfileManager.get_current_or_default()['dust']['auto_mode_time']

		self._logger.debug("initialized!")

	def _subscribe(self):
		_mrbeam_plugin_implementation._event_bus.subscribe(IoBeamEvents.DUST_VALUE, self.onEvent)
		_mrbeam_plugin_implementation._event_bus.subscribe(OctoPrintEvents.PRINT_STARTED, self.onEvent)
		_mrbeam_plugin_implementation._event_bus.subscribe(OctoPrintEvents.PRINT_DONE, self.onEvent)
		_mrbeam_plugin_implementation._event_bus.subscribe(OctoPrintEvents.PRINT_FAILED, self.onEvent)
		_mrbeam_plugin_implementation._event_bus.subscribe(OctoPrintEvents.PRINT_CANCELLED, self.onEvent)
		_mrbeam_plugin_implementation._event_bus.subscribe(OctoPrintEvents.SHUTDOWN, self.onEvent)

	def onEvent(self, event, payload):
		if event == IoBeamEvents.DUST_VALUE:
			self._handle_dust(payload)
		elif event == OctoPrintEvents.PRINT_STARTED:
			self._start_dust_extraction()
		elif event in (OctoPrintEvents.PRINT_DONE, OctoPrintEvents.PRINT_FAILED, OctoPrintEvents.PRINT_CANCELLED):
			self._stop_dust_extraction_when_below(self.extraction_limit)
		elif event == OctoPrintEvents.SHUTDOWN:
			self.shutdown()

	def shutdown(self):
		self._shutting_down = True

	def _handle_dust(self, payload):
		self._dust = payload['val'] if 'val' in payload else None
		self._dust_ts = time.time()
		self.check_dust_value()
		self.send_status_to_frontend(self._dust)

	def _start_dust_extraction(self, value=None):
		if self._auto_timer is not None:
			self._auto_timer.cancel()
			self._auto_timer = None
		if value is None:
			if not self._send_fan_command('auto', wait=0.2):
				self._logger.warning("Could not start auto mode!")
		else:
			if value > 100:
				value = 100
			elif value < 0:
				value = 0
			if not self._send_fan_command('on:{}'.format(int(value)), wait=0.2):
				self._logger.warning("Could not start fixed mode!")

	def _stop_dust_extraction(self):
		if not self._send_fan_command('off'):
			self._logger.warning("Could not turn off dust extraction!")

	def _stop_dust_extraction_when_below(self, value):
		if self._trail_extraction is None:
			self._trail_extraction = threading.Thread(target=self._wait_until, args=(value,))
			self._trail_extraction.daemon = True
			self._trail_extraction.start()

	def _wait_until(self, value):
		self._logger.debug("starting trial dust extraction (value={}).".format(value))
		dust_start = self._dust
		dust_start_ts = self._dust_ts
		self._dust_timer_interval = 1
		self._start_dust_extraction(100)
		while self._dust > value:
			time.sleep(self._dust_timer_interval)
		dust_end = self._dust
		dust_end_ts = self._dust_ts
		self._dust_timer_interval = 3
		self._write_analytics(dust_start, dust_start_ts, dust_end, dust_end_ts)
		self._activate_timed_auto_mode(self.auto_mode_time)
		self._trail_extraction = None

	def _activate_timed_auto_mode(self, value):
		self._logger.debug("starting timed auto mode (value={}).".format(value))
		self._start_dust_extraction()
		self._auto_timer = threading.Timer(value, self._auto_timer_callback)
		self._auto_timer.daemon = True
		self._auto_timer.start()

	def _auto_timer_callback(self):
		self._logger.debug("auto mode stopped!")
		self._stop_dust_extraction()
		self._auto_timer = None

	def _send_fan_command(self, command, wait=1.0, max_retries=5):
		retries = 0
		while True:
			if _mrbeam_plugin_implementation._ioBeam.send_command("fan:{}".format(command)):
				return True
			else:
				retries += 1
				if retries >= max_retries:
					return False
				time.sleep(wait)

	def _write_analytics(self, dust_start, dust_start_ts, dust_end, dust_end_ts):
		self._logger.debug("dust extraction time {} from {} to {} (gradient: {})".format(dust_end_ts - dust_start_ts, dust_start, dust_end, (dust_start - dust_end) / (dust_end_ts - dust_start_ts)))
		data = dict(
			dust_start=dust_start,
			dust_end=dust_end,
			dust_start_ts=dust_start_ts,
			dust_end_ts=dust_end_ts
		)
		_mrbeam_plugin_implementation._analytics_handler.add_dust_log(data)

	def check_dust_value(self):
		pass

	def _check_dust_is_current(self):
		if time.time() - self._dust_ts > self.DEFAUL_DUST_MAX_AGE:
			self._logger.error("Can't read dust value.")
			# TODO fire some Error pause (together with andy)

	def request_dust(self):
		return True if self._send_fan_command("dust") else False

	def _dust_timer_callback(self):
		try:
			self.request_dust()
			self._check_dust_is_current()
			self._start_dust_timer()
		except:
			self._logger.exception("Exception in _dust_timer_callback(): ")
			self._start_dust_timer()

	def _start_dust_timer(self):
		if not self._shutting_down:
			self._dust_timer = threading.Timer(self._dust_timer_interval, self._dust_timer_callback)
			self._dust_timer.daemon = True
			self._dust_timer.start()
		else:
			self._logger.debug("Shutting down.")

	def send_status_to_frontend(self, dust):
		_mrbeam_plugin_implementation._plugin_manager.send_plugin_message("mrbeam", dict(status=dict(dust_value=dust)))
