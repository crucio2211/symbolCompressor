# -*- coding: utf-8 -*-
import config
import gui
from gui import guiHelper, NVDASettingsDialog
from gui.settingsDialogs import SettingsPanel
import wx
import globalPluginHandler
import speech
import json
import os
import globalVars

# Own JSON settings file (same style as smartSpeakKeys), stored in the NVDA
# user config folder so it persists across addon updates. This replaces the
# old nvda.ini [symbolCompressor] section, which proved unreliable.
SETTINGS_FILENAME = "symbolCompressor_settings.json"

DEFAULT_SETTINGS = {
	"compressSymbols": True,
	"minCountSymbols": 3,
	"compressEmojis": True,
	"minCountEmojis": 3,
}

_settingsCache = None


def _settingsFilePath():
	try:
		return os.path.join(globalVars.appArgs.configPath, SETTINGS_FILENAME)
	except Exception:
		return os.path.join(os.path.dirname(__file__), SETTINGS_FILENAME)


def _migrateFromIni():
	"""One-time migration of the old nvda.ini [symbolCompressor] values."""
	migrated = {}
	try:
		section = config.conf["symbolCompressor"]
	except Exception:
		return migrated
	try:
		if "compressSymbols" in section:
			migrated["compressSymbols"] = bool(section.get("compressSymbols", True))
		if "compressEmojis" in section:
			migrated["compressEmojis"] = bool(section.get("compressEmojis", True))
		for key in ("minCountSymbols", "minCountEmojis"):
			if key in section:
				try:
					number = int(section.get(key, 3))
				except (ValueError, TypeError):
					continue
				migrated[key] = max(2, min(5, number))
	except Exception:
		pass
	return migrated


def loadSettings(forceReload=False):
	"""Load settings from the JSON file, merged over defaults.

	Migrates old nvda.ini values on first run (when no JSON file exists yet).
	"""
	global _settingsCache
	if _settingsCache is not None and not forceReload:
		return _settingsCache
	settings = dict(DEFAULT_SETTINGS)
	path = _settingsFilePath()
	if os.path.exists(path):
		try:
			with open(path, "r", encoding="utf-8") as f:
				saved = json.load(f)
			if isinstance(saved, dict):
				settings.update(saved)
		except Exception:
			pass
	else:
		migrated = _migrateFromIni()
		if migrated:
			settings.update(migrated)
			saveSettings(settings)
	# Sanitize types in case the file was hand-edited.
	try:
		settings["compressSymbols"] = bool(settings.get("compressSymbols", True))
		settings["compressEmojis"] = bool(settings.get("compressEmojis", True))
		for key in ("minCountSymbols", "minCountEmojis"):
			try:
				settings[key] = max(2, min(5, int(settings.get(key, 3))))
			except (ValueError, TypeError):
				settings[key] = 3
	except Exception:
		pass
	_settingsCache = settings
	return settings


def saveSettings(settings):
	"""Save settings dict to the JSON file (and refresh the cache)."""
	global _settingsCache
	clean = {
		"compressSymbols": bool(settings.get("compressSymbols", True)),
		"compressEmojis": bool(settings.get("compressEmojis", True)),
		"minCountSymbols": settings.get("minCountSymbols", 3),
		"minCountEmojis": settings.get("minCountEmojis", 3),
	}
	for key in ("minCountSymbols", "minCountEmojis"):
		try:
			clean[key] = max(2, min(5, int(clean[key])))
		except (ValueError, TypeError):
			clean[key] = 3
	try:
		with open(_settingsFilePath(), "w", encoding="utf-8") as f:
			json.dump(clean, f, indent=2)
		_settingsCache = clean
		return True
	except Exception:
		return False

# Emoji 17.0 (Unicode 17.0, released Sept 2025) additions.
# These are provided as a fallback name table because unicodedata.name()
# may not yet recognize brand-new codepoints depending on the Python/Unicode
# database version bundled with the running NVDA install.
NEW_EMOJI_NAMES = {
	"\U0001FAEA": "distorted face",
	"\U0001FAEF": "fight cloud",
	"\U0001FAC8": "hairy creature",
	"\U0001FACD": "orca",
	"\U0001F6D8": "landslide",
	"\U0001FA8A": "trombone",
	"\U0001FA8E": "treasure chest",
}

# Emoji 18.0 (Unicode 18.0, released Sept 16 2026) additions.
# 9 new codepoints, 19 sequences with skin tones.
# Source: https://www.unicode.org/emoji/charts-18.0/emoji-released.html
# CLDR short names lowercased to match unicodedata.name().lower() style.
EMOJI_18_0_NAMES = {
	"\U0001FAEB": "cracking face",
	"\U0001FAF9": "leftwards thumb sign",
	"\U0001FAFA": "rightwards thumb sign",
	"\U0001FACC": "monarch butterfly",
	"\U0001FADD": "pickle",
	"\U0001F6D9": "lighthouse",
	"\U0001FA8B": "meteor",
	"\U0001FA8C": "eraser",
	"\U0001FA8D": "net with handle",
}

# Skin tone modifiers, used to build readable names for ZWJ sequences
SKIN_TONE_NAMES = {
	"\U0001F3FB": "light skin tone",
	"\U0001F3FC": "medium-light skin tone",
	"\U0001F3FD": "medium skin tone",
	"\U0001F3FE": "medium-dark skin tone",
	"\U0001F3FF": "dark skin tone",
}

# Ballet dancer: person (U+1F9D1) + optional skin tone + ZWJ + ballet shoes (U+1FA70)
BALLET_DANCER_BASE = "\U0001F9D1"
BALLET_DANCER_SUFFIX = "\U0000200D\U0001FA70"

class SymbolCompressorSettingsPanel(SettingsPanel):
	title = "Symbol Compressor"

	# Single dropdown per category: Off disables compression, otherwise the
	# number is the minimum repeat count. wx.Choice is used (not SpinCtrl) so
	# users can only pick a valid value (no typing), which also guarantees
	# onSave() can never fail on config validation and skip other settings.
	MIN_COUNT_CHOICES = ["Off", "2", "3", "4", "5"]
	MIN_COUNT_DEFAULT = 3

	def _setDropdown(self, dropdown, enabled, value):
		# Migrates old configs: disabled -> Off, out-of-range counts clamped.
		if not enabled:
			dropdown.SetSelection(0)
			return
		try:
			number = int(value)
		except (ValueError, TypeError):
			number = self.MIN_COUNT_DEFAULT
		number = max(2, min(5, number))
		dropdown.SetSelection(self.MIN_COUNT_CHOICES.index(str(number)))

	def _getDropdown(self, dropdown):
		# Returns (enabled, minCount). Off -> (False, default).
		index = dropdown.GetSelection()
		if 0 < index < len(self.MIN_COUNT_CHOICES):
			return True, int(self.MIN_COUNT_CHOICES[index])
		return False, self.MIN_COUNT_DEFAULT

	def makeSettings(self, settingsSizer):
		sHelper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		settings = loadSettings()

		# Compress symbols dropdown: Off, 2, 3, 4, 5
		self.compressSymbolsChoice = sHelper.addLabeledControl("Compress repeated symbols:", wx.Choice, choices=self.MIN_COUNT_CHOICES)
		self._setDropdown(
			self.compressSymbolsChoice,
			settings["compressSymbols"],
			settings["minCountSymbols"],
		)

		# Compress emojis dropdown: Off, 2, 3, 4, 5
		self.compressEmojisChoice = sHelper.addLabeledControl("Compress repeated emojis:", wx.Choice, choices=self.MIN_COUNT_CHOICES)
		self._setDropdown(
			self.compressEmojisChoice,
			settings["compressEmojis"],
			settings["minCountEmojis"],
		)

	def onSave(self):
		symbolsEnabled, minSymbols = self._getDropdown(self.compressSymbolsChoice)
		emojisEnabled, minEmojis = self._getDropdown(self.compressEmojisChoice)
		saveSettings({
			"compressSymbols": symbolsEnabled,
			"minCountSymbols": minSymbols,
			"compressEmojis": emojisEnabled,
			"minCountEmojis": minEmojis,
		})

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	def __init__(self):
		super(GlobalPlugin, self).__init__()
		NVDASettingsDialog.categoryClasses.append(SymbolCompressorSettingsPanel)
		self._originalSpeak = speech.speech.speak
		speech.speech.speak = self._compressingSpeak
	
	def terminate(self):
		speech.speech.speak = self._originalSpeak
		try:
			NVDASettingsDialog.categoryClasses.remove(SymbolCompressorSettingsPanel)
		except:
			pass
		super(GlobalPlugin, self).terminate()
	
	def _compressingSpeak(self, speechSequence, *args, **kwargs):
		compressed = self._compressSequence(speechSequence)
		self._originalSpeak(compressed, *args, **kwargs)
	
	def _compressSequence(self, sequence):
		# Check current symbol level
		# Symbol levels: 0=NONE, 100=SOME, 200=MOST, 300=ALL
		# Only compress when symbol level is NOT NONE (user wants to hear symbols)
		shouldProcessSymbols = True
		try:
			symbolLevel = config.conf["speech"]["symbolLevel"]
			# If symbol level is NONE (0), user doesn't want to hear symbols at all
			# So don't compress them either (respect NVDA's decision to not speak them)
			if symbolLevel == 0:
				shouldProcessSymbols = False
		except:
			pass
		
		# If symbol compression is disabled and we shouldn't process, return as-is
		settings = loadSettings()
		if not shouldProcessSymbols and not settings["compressEmojis"]:
			return sequence
		
		minCountSymbols = settings["minCountSymbols"]
		minCountEmojis = settings["minCountEmojis"]
		compressSymbolsEnabled = settings["compressSymbols"]
		compressEmojisEnabled = settings["compressEmojis"]
		newSeq = []
		for item in sequence:
			if isinstance(item, str):
				newSeq.append(self._compressString(item, minCountSymbols, minCountEmojis, shouldProcessSymbols, compressSymbolsEnabled, compressEmojisEnabled))
			else:
				newSeq.append(item)
		return newSeq
	
	def _compressString(self, text, minCountSymbols, minCountEmojis, shouldProcessSymbols, compressSymbolsEnabled=True, compressEmojisEnabled=True):
		if not text:
			return text
		
		result = []
		i = 0
		while i < len(text):
			# Get emoji sequence (may include variation selectors, skin tones, ZWJ sequences)
			emojiSeq, emojiLen = self._getEmojiSequence(text, i)
			
			if emojiSeq and compressEmojisEnabled:
				# Normalize for comparison (removes variation selectors)
				normalizedEmoji = self._normalizeEmoji(emojiSeq)
				
				# Count consecutive occurrences of this emoji (normalized comparison)
				count = 1
				j = i + emojiLen
				while j < len(text):
					nextSeq, nextLen = self._getEmojiSequence(text, j)
					if nextSeq and self._normalizeEmoji(nextSeq) == normalizedEmoji:
						count += 1
						j += nextLen
					else:
						break
				
				# Use minCountEmojis for emojis
				if count >= minCountEmojis:
					name = self._getName(normalizedEmoji)
					if name:
						result.append(f"{count} {name}")
					else:
						result.append(emojiSeq * count)
					i = j
					continue
			
			# Handle single character symbols - only if shouldProcessSymbols is True
			char = text[i]
			if shouldProcessSymbols and compressSymbolsEnabled and char in ".,!?;:-_=+*/<>@#$%^&()[]{}|\\\"'`~":
				count = 1
				j = i + 1
				while j < len(text) and text[j] == char:
					count += 1
					j += 1
				# Use minCountSymbols for symbols
				if count >= minCountSymbols:
					name = self._getName(char)
					if name:
						result.append(f"{count} {name}")
					else:
						result.append(char * count)
					i = j
					continue
			
			# Not compressed, add as-is
			if emojiSeq:
				result.append(emojiSeq)
				i += emojiLen
			else:
				result.append(char)
				i += 1
		
		return "".join(result)
	
	def _getEmojiSequence(self, text, pos):
		"""
		Get emoji sequence starting at position, including variation selectors,
		skin tone modifiers, and ZWJ sequences. Returns (emoji_string, length) or (None, 0)
		"""
		if pos >= len(text):
			return None, 0
		
		char = text[pos]
		if not self._isEmojiBase(char):
			return None, 0
		
		# Start with base emoji
		seq = char
		length = 1
		i = pos + 1
		
		# Add variation selectors and modifiers
		while i < len(text):
			nextChar = text[i]
			cp = ord(nextChar)
			
			# Variation selectors (FE00-FE0F, FE20-FE2F)
			if (0xFE00 <= cp <= 0xFE0F) or (0xFE20 <= cp <= 0xFE2F):
				seq += nextChar
				length += 1
				i += 1
			# Skin tone modifiers (1F3FB-1F3FF)
			elif 0x1F3FB <= cp <= 0x1F3FF:
				seq += nextChar
				length += 1
				i += 1
			# Zero-width joiner for combined emojis
			elif cp == 0x200D:
				seq += nextChar
				length += 1
				i += 1
				# Add the next emoji in sequence
				if i < len(text) and self._isEmojiBase(text[i]):
					seq += text[i]
					length += 1
					i += 1
			else:
				break
		
		return seq, length
	
	def _normalizeEmoji(self, emoji):
		"""
		Normalize emoji by removing variation selectors for comparison
		"""
		if not emoji:
			return emoji
		# Remove variation selectors (FE00-FE0F, FE20-FE2F)
		normalized = ""
		for char in emoji:
			cp = ord(char)
			if not ((0xFE00 <= cp <= 0xFE0F) or (0xFE20 <= cp <= 0xFE2F)):
				normalized += char
		return normalized
	
	def _isEmojiBase(self, c):
		"""
		Check if character is a base emoji (not a modifier/selector)
		"""
		cp = ord(c)
		return (
			# Emoticons
			0x1F600 <= cp <= 0x1F64F or
			# Misc Symbols and Pictographs
			0x1F300 <= cp <= 0x1F5FF or
			# Transport and Map
			0x1F680 <= cp <= 0x1F6FF or
			# Flags
			0x1F1E0 <= cp <= 0x1F1FF or
			# Supplemental Symbols
			0x1F900 <= cp <= 0x1F9FF or
			# Extended Pictographs
			0x1FA70 <= cp <= 0x1FAFF or
			# Misc symbols (includes ❤ U+2764, ⭐ U+2B50, etc.)
			0x2600 <= cp <= 0x27BF or
			# Dingbats
			0x2700 <= cp <= 0x27BF or
			# Regional indicators (for flag emojis)
			0x1F1E6 <= cp <= 0x1F1FF
		)
	
	def _isEmoji(self, c):
		return self._isEmojiBase(c)
	
	def _getName(self, c):
		names = {'.': 'dot', ',': 'comma', '!': 'exclamation', '?': 'question', ';': 'semicolon', ':': 'colon', '-': 'dash', '_': 'underscore', '=': 'equals', '+': 'plus', '*': 'asterisk', '/': 'slash', '\\': 'backslash', '<': 'less', '>': 'greater', '@': 'at', '#': 'hash', '$': 'dollar', '%': 'percent', '^': 'caret', '&': 'ampersand', '(': 'left paren', ')': 'right paren', '[': 'left bracket', ']': 'right bracket', '{': 'left brace', '}': 'right brace', '|': 'pipe', '"': 'quote', "'": 'apostrophe', '`': 'backtick', '~': 'tilde'}
		if c in names:
			return names[c]

		# Emoji 17.0 fallback: brand-new single-codepoint emojis that older
		# unicodedata databases may not know yet
		if c in NEW_EMOJI_NAMES:
			return NEW_EMOJI_NAMES[c]

		# Emoji 18.0 fallback: same reason, Unicode 18.0 released Sept 2026
		if c in EMOJI_18_0_NAMES:
			return EMOJI_18_0_NAMES[c]

		# Emoji 17.0 ballet dancer ZWJ sequence (with or without skin tone)
		balletName = self._getBalletDancerName(c)
		if balletName:
			return balletName

		if len(c) == 1:
			try:
				import unicodedata
				return unicodedata.name(c, '').lower()
			except:
				pass
			return None

		# Generic multi-codepoint (ZWJ) sequence fallback: unicodedata.name()
		# only accepts single characters, so build a best-effort name from
		# each component instead of failing silently
		try:
			import unicodedata
			parts = []
			for ch in c:
				if ch == "\U0000200D":
					continue
				if ch in SKIN_TONE_NAMES:
					parts.append(SKIN_TONE_NAMES[ch])
					continue
				if ch in NEW_EMOJI_NAMES:
					parts.append(NEW_EMOJI_NAMES[ch])
					continue
				if ch in EMOJI_18_0_NAMES:
					parts.append(EMOJI_18_0_NAMES[ch])
					continue
				n = unicodedata.name(ch, '')
				if n:
					parts.append(n.lower())
			if parts:
				return ", ".join(parts)
		except:
			pass
		return None

	def _getBalletDancerName(self, seq):
		"""
		Recognize the Emoji 17.0 'ballet dancer' ZWJ sequence:
		person (+ optional skin tone) + ZWJ + ballet shoes
		"""
		if not seq.startswith(BALLET_DANCER_BASE) or not seq.endswith(BALLET_DANCER_SUFFIX):
			return None
		middle = seq[len(BALLET_DANCER_BASE):-len(BALLET_DANCER_SUFFIX)]
		if middle == "":
			return "ballet dancer"
		if middle in SKIN_TONE_NAMES:
			return f"ballet dancer, {SKIN_TONE_NAMES[middle]}"
		return None
