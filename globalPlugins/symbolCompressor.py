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

confspec = {
	"minCountSymbols": "integer(default=3, min=2, max=5)",
	"minCountEmojis": "integer(default=3, min=2, max=5)",
	"compressSymbols": "boolean(default=True)",
	"compressEmojis": "boolean(default=True)",
}
config.conf.spec["symbolCompressor"] = confspec


def _migrateJsonToIni():
	"""One-time migration of symbolCompressor_settings.json back into nvda.ini.

	Runs at import time; removes the JSON file after a successful migration.
	"""
	filename = "symbolCompressor_settings.json"
	candidates = []
	try:
		import globalVars
		candidates.append(os.path.join(globalVars.appArgs.configPath, filename))
	except Exception:
		pass
	try:
		candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename))
	except Exception:
		pass
	path = next((p for p in candidates if p and os.path.exists(p)), None)
	if not path:
		return
	try:
		with open(path, "r", encoding="utf-8") as f:
			saved = json.load(f)
		if not isinstance(saved, dict):
			return
		section = config.conf["symbolCompressor"]
		if "compressSymbols" in saved:
			section["compressSymbols"] = bool(saved["compressSymbols"])
		if "compressEmojis" in saved:
			section["compressEmojis"] = bool(saved["compressEmojis"])
		for key in ("minCountSymbols", "minCountEmojis"):
			if key in saved:
				try:
					section[key] = max(2, min(5, int(saved[key])))
				except (ValueError, TypeError):
					pass
	except Exception:
		return
	try:
		os.remove(path)
	except Exception:
		pass


_migrateJsonToIni()

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

MIN_COUNT_CHOICES = ["Off", "2", "3", "4", "5"]
MIN_COUNT_DEFAULT = 3


def valueToDropdownIndex(enabled, value):
	# Migrates old configs: disabled -> Off, out-of-range counts clamped.
	if not enabled:
		return 0
	try:
		number = int(value)
	except (ValueError, TypeError):
		number = MIN_COUNT_DEFAULT
	number = max(2, min(5, number))
	return MIN_COUNT_CHOICES.index(str(number))


def dropdownIndexToValue(index):
	# Returns (enabled, minCount). Off -> (False, default).
	if 0 < index < len(MIN_COUNT_CHOICES):
		return True, int(MIN_COUNT_CHOICES[index])
	return False, MIN_COUNT_DEFAULT


class SymbolCompressorSettingsPanel(SettingsPanel):
	title = "Symbol Compressor"

	def makeSettings(self, settingsSizer):
		sHelper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)

		self.symbolsChoice = sHelper.addLabeledControl(
			"Compress repeated symbols:", wx.Choice, choices=MIN_COUNT_CHOICES
		)
		self.symbolsChoice.SetSelection(valueToDropdownIndex(
			config.conf["symbolCompressor"]["compressSymbols"],
			config.conf["symbolCompressor"]["minCountSymbols"],
		))

		self.emojisChoice = sHelper.addLabeledControl(
			"Compress repeated emojis:", wx.Choice, choices=MIN_COUNT_CHOICES
		)
		self.emojisChoice.SetSelection(valueToDropdownIndex(
			config.conf["symbolCompressor"]["compressEmojis"],
			config.conf["symbolCompressor"]["minCountEmojis"],
		))

	def onSave(self):
		symbolsEnabled, minSymbols = dropdownIndexToValue(self.symbolsChoice.GetSelection())
		emojisEnabled, minEmojis = dropdownIndexToValue(self.emojisChoice.GetSelection())
		config.conf["symbolCompressor"]["compressSymbols"] = symbolsEnabled
		config.conf["symbolCompressor"]["minCountSymbols"] = minSymbols
		config.conf["symbolCompressor"]["compressEmojis"] = emojisEnabled
		config.conf["symbolCompressor"]["minCountEmojis"] = minEmojis

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	def __init__(self):
		super(GlobalPlugin, self).__init__()
		NVDASettingsDialog.categoryClasses.append(SymbolCompressorSettingsPanel)
		self._originalSpeak = speech.speech.speak
		speech.speech.speak = self._compressingSpeak

	def terminate(self):
		try:
			speech.speech.speak = self._originalSpeak
		except Exception:
			pass
		try:
			NVDASettingsDialog.categoryClasses.remove(SymbolCompressorSettingsPanel)
		except Exception:
			pass
		super(GlobalPlugin, self).terminate()
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
		section = config.conf["symbolCompressor"]
		if not shouldProcessSymbols and not section["compressEmojis"]:
			return sequence
		
		minCountSymbols = section["minCountSymbols"]
		minCountEmojis = section["minCountEmojis"]
		compressSymbolsEnabled = section["compressSymbols"]
		compressEmojisEnabled = section["compressEmojis"]
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
