#!/usr/bin/env python3
import re as re
from collections import Counter, defaultdict, namedtuple
#from ansicolor import red
import os.path
import json
import itertools
import random
from toolz.dicttoolz import merge
from AutoTranslateCommon import *
from googletrans import Translator

import requests

class CompositeAutoTranslator(object):
    """
    Utility that calls tries all autoindexers until one is able to translate
    the string.
    """
    def __init__(self, *args):
        self.children = list(filter(lambda arg: arg is not None, args))

    def translate(self, engl):
        for child in self.children:
            result = child.translate(engl)
            if result is not None:  # Could translate
                return result
        return None

class RuleAutotranslator(object):
    """
    Auto-translates based on regex rules.
    Will mostly auto-translate formula-only etc
    """
    def __init__(self):
        # Formulas:
        #   $...$
        #    **$...$
        self._is_formula = re.compile(r"^(>|#)*[\s\*]*(\$[^\$]+\$(\s|\\n|\*)*)+$");
        # contains a \text{ clause except specific text clauses:
        #   \text{ cm}
        #   \text{ m}
        #   \text{ g}
        self._contains_text = get_text_regex()
        # URLs:
        #   ![](web+graphie://ka-perseus-graphie.s3.amazonaws.com/...)
        #   web+graphie://ka-perseus-graphie.s3.amazonaws.com/...
        #   https://ka-perseus-graphie.s3.amazonaws.com/...png
        self._is_perseus_img_url = re.compile(r"^(!\[\]\()?\s*(http|https|web\+graphie):\/\/ka-perseus-(images|graphie)\.s3\.amazonaws\.com\/[0-9a-f]+(\.(svg|png|jpg|jpeg))?\)?\s*$")

        self._is_formula_plus_img = re.compile(r"^>?[\s\*]*(\$[^\$]+\$(\s|\\n|\*)*)+(!\[\]\()?\s*(http|https|web\+graphie):\/\/ka-perseus-(images|graphie)\.s3\.amazonaws\.com\/[0-9a-f]+(\.(svg|png|jpg))?\)?\s*$")
        self._is_input = re.compile(r"^\[\[\s*☃\s*[a-z-]+\s*\d*\s*\]\](\s|\\n)*$", re.UNICODE)
        self._is_formula_plus_input = re.compile(r"^(>|#)*[\s\*]*(\$[^\$]+\$(\s|\\n|\*)*)+=?\s*\[\[\s*☃\s*[a-z-]+\s*\d*\s*\]\](\s|\\n)*$", re.UNICODE);
        self._is_simple_coordinate = re.compile(r"^[\[\(]-?\d+,-?\d+[\]\)]$")

    def translate(self, engl):
        is_formula = self._is_formula.match(engl) is not None
        contains_text = self._contains_text.search(engl) is not None
        is_perseus_img_url = self._is_perseus_img_url.match(engl) is not None
        is_formula_plus_img = self._is_formula_plus_img.match(engl) is not None
        is_formula_plus_input = self._is_formula_plus_input.match(engl) is not None
        is_input = self._is_input.match(engl) is not None
        is_simple_coordinate = self._is_simple_coordinate.match(engl) is not None

        if is_perseus_img_url or is_formula_plus_img or is_input or is_formula_plus_input or is_simple_coordinate:
            return engl
        if is_formula and not contains_text:
            return engl

class IFPatternAutotranslator(object):
    """
    Ignore Formula pattern autotranslator
    """
    def __init__(self, lang):
        self.lang = lang
        # Read patterns index
        self.ifpatterns = read_ifpattern_index(lang)
        self.texttags = read_texttag_index(lang)
        # Compile regexes
        self._formula_re = re.compile(r"\$[^\$]+\$")
        self._img_re = get_image_regex()
        self._text = get_text_content_regex()

    def translate(self, engl):
        # Normalize and filter out formulae with translatable text
        normalized = self._formula_re.sub("§formula§", engl)
        normalized = self._img_re.sub("§image§", normalized)
        # Mathrm is a rare alternative to \\text which is unhanled at the moment
        if "mathrm" in engl:
            return None
        # If there are any texts, check if we know how to translate
        texttag_replace = {} # texttags: engl full tag to translated full tag 
        for text_hit in self._text.finditer(engl):
            content = text_hit.group(2).strip()
            if content in self.texttags:
                # Assemble the correct replacement string
                translated = text_hit.group(1) + self.texttags[content] + text_hit.group(3)
                texttag_replace[text_hit.group(0)] = translated
            else: # Untranslatable tag
                return None # Cant fully translate this string
        # Check if it matches
        if normalized not in self.ifpatterns:
            return None # Do not have pattern
        transl = self.ifpatterns[normalized]
        # Find formulae in english text
        #
        # Replace one-by-one
        #
        src_formulae = self._formula_re.findall(engl)
        while "§formula§" in transl:
            next_formula = src_formulae.pop(0) # Next "source formula"
            transl = transl.replace("§formula§", next_formula, 1)
        
        src_images = self._img_re.findall(engl)
        while "§image§" in transl:
            next_image = src_images.pop(0)[0] # Next "source image"
            transl = transl.replace("§image§", next_image, 1)
        # Translate text-tags, if any
        for src, repl in texttag_replace.items():
            # Safety: If there is nothing to replace, fail instead of
            # failing to translate a text tag
            if src not in transl:
                #print(red("Text-tag translation: Can't find '{}' in '{}'".format(
                print("Text-tag translation: Can't find '{}' in '{}'".format(
                    src, transl), bold=True)
                return None
            transl = transl.replace(src, repl)
        return transl


class NameAutotranslator(object):
    """
    Auto-translates based on regex rules.
    Will mostly auto-translate formula-only etc
    """
    def __init__(self, lang):
        self.lang = lang
        self._re1 = re.compile(r"^\s*Only\s+([A-Z][a-z]+)((\.|\s+|\\n)*)$")
        self._re2 = re.compile(r"^\s*Neither\s+([A-Z][a-z]+)\s+nor\s+([A-Z][a-z]+)((\.|\s+|\\n)*)$")
        self._re3 = re.compile(r"^\s*Either\s+([A-Z][a-z]+)\s+or\s+([A-Z][a-z]+)((\.|\s+|\\n)*)$")
        self._re4 = re.compile(r"^\s*Both\s+([A-Z][a-z]+)\s+and\s+([A-Z][a-z]+)((\.|\s+|\\n)*)$")
        self._re5 = re.compile(r"^\s*Neither\s+([A-Z][a-z]+)\s+nor\s+([A-Z][a-z]+)\s+are\s+correct((\.|\s+|\\n)*)$")
        self._re6 = re.compile(r"^\s*Both\s+([A-Z][a-z]+)\s+and\s+([A-Z][a-z]+)\s+are\s+correct((\.|\s+|\\n)*)$")
        self._re7 = re.compile(r"^\s*Yes,\s+([A-Z][a-z]+)\s+is\s+correct\s+but\s+([A-Z][a-z]+)\s+is\s+not((\.|\s+|\\n)*)$")
        self._re8 = re.compile(r"^\s*In conclusion,\s*([A-Z][a-z]+)\s+is\s+correct((\.|\s+|\\n)*)$")
        self._re9 = re.compile(r"^\s*Only\s*([A-Z][a-z]+)\s+is\s+correct((\.|\s+|\\n)*)$")
        self._re10 = re.compile(r"^\s*([A-Z][a-z]+)'s\s+work\s+is\s+correct((\.|\s+|\\n)*)$")
        # Translation patterns in this order:
        #   1. Only <name1>
        #   2. Neither <name1> nor <name2>
        #   3. Either <name1> or <name2>
        #   4. Both <name1> and <name2>
        #   5. Neither <name1> nor <name2> are correct
        #   6. Both <name1> and <name2> are correct
        #   7. Yes, <name1> is correct but <name2> is not
        #   8. In conclusion, <name1> is correct
        #   9. Only <name1> is correct
        #   10.<name1>'s work is correct
        transmap = {
            "sv-SE": [
                "Endast <name1>",
                "Varken <name1> eller <name2>",
                "Antingen <name1> eller <name2>",
                "Både <name1> och <name2>",
                "Varken <name1> eller <name2> har rätt",
                "Både <name1> och <name2> har rätt",
                "Ja, <name1> har rätt men inte <name2>",
                "Avslutningsvis, så har <name1> rätt",
                "Endast <name1> har rätt",
                "<name1>s lösning är rätt"

            ], "lol": [
                "Only <name1>",
                "Neither <name1> norz <name2>",
                "Either <name1> or <name2>",
                "Both <name1> and <name2>",
                "Neither <name1> nor <name2> are correct",
                "Both <name1> and <name2> are correct"
            ], "de": [
                "Nur <name1>",
                "Weder <name1> noch <name2>",
                "Entweder <name1> oder <name2>",
                "Sowohl <name1> als auch <name2>",
                "Weder <name1> noch <name2> liegen richtig",
                "Sowohl <name1> als auch <name2> liegt richig",
                "Ja, <name1> liegt richtig, aber <name2> liegt falsch",
                "Zusammenfassend liegt <name1> richtig",
                "Nur <name1> liegt richtig",
                "Die Lösung von <name1> ist korrekt"
            ], "hu": [
                "Csak <name1>",
                "Sem <name1> sem <name2>",
                "<name1> is vagy <name2> is",
                "<name1> is és <name2> is",
                "Sem <name1> sem <name2> nem helyes",
                "<name1> és <name2> is helyes",
                "Igen, <name1> helyes, de <name2> nem helyes",
                "Tehát <name1> helyes",
                "Csak <name1> helyes",
                "<name1> megoldása helyes"
            ]
        }
        if lang not in transmap:
            raise "Please create name translation mapping for {}".format(lang)
        self.transmap = transmap[lang]

    def replace_name(self, lang, name):
        """
        Get the localized replacement name
        """
        # TODO not implemented
        return name

    def _translate_match_two_names(self, m, transmap_entry):
        name1 = m.group(1)
        name2 = m.group(2)
        rest = m.group(3)
        return transmap_entry.replace("<name1>", name1).replace("<name2>", name2) + rest

    def _translate_match_one_name(self, m, transmap_entry):
        if transmap_entry is None: # Unknown translation
            return None # Cant translate
        name1 = m.group(1)
        rest = m.group(2)
        return transmap_entry.replace("<name1>", name1) + rest

    def translate(self, engl):
        m1 = self._re1.match(engl)
        m2 = self._re2.match(engl)
        m3 = self._re3.match(engl)
        m4 = self._re4.match(engl)
        m5 = self._re5.match(engl)
        m6 = self._re6.match(engl)
        m7 = self._re7.match(engl)
        m8 = self._re8.match(engl)
        m9 = self._re9.match(engl)
        m10 = self._re10.match(engl)
        if m1:
            return self._translate_match_one_name(m1, self.transmap[0])
        elif m2:
            return self._translate_match_two_names(m2, self.transmap[1])
        elif m3:
            return self._translate_match_two_names(m3, self.transmap[2])
        elif m4:
            return self._translate_match_two_names(m4, self.transmap[3])
        elif m5:
            return self._translate_match_two_names(m5, self.transmap[4])
        elif m6:
            return self._translate_match_two_names(m6, self.transmap[5])
        elif m7:
            return self._translate_match_two_names(m7, self.transmap[6])
        elif m8:
            return self._translate_match_one_name(m8, self.transmap[7])
        elif m9:
            return self._translate_match_one_name(m9, self.transmap[8])
        elif m10:
            return self._translate_match_one_name(m10, self.transmap[9])

PlaceholderInfo = namedtuple("PlaceholderInfo", [
    "nPlaceholders", "replaceMap", "nAsterisks", "nNewlines", "nHashs", "nUnderscores"])

class FullAutoTranslator(object):
    """
    Google translate based full auto translator
    """
    def __init__(self, lang, limit=25):
        self.lang = lang if lang != "lol" else "de" # LOL => translate to DE
        # Generate nonce to fix some bad translations
        self.nonce1 = random.randint(1000000, 9999999)
        self.nonce2 = random.randint(1000, 9999)
        #
        # Pattern regexes
        #
        # <g id="continue">%1$s</g> or <g id="get_help_link">%2$s</g> misrecognized as 
        self._formula_re = re.compile(r"\s*(?<!\%[\dA-Za-z])\$(\\\$|[^\$])+\$\s*")
        self._asterisk_re = re.compile(r"\s*\*+\s*")
        self._underscore_re = re.compile(r"\s*_+\s*")
        self._special_chars_re = re.compile(r"\s*[θ𝘹𝘺ƒ𝘢𝘣𝘶𝘯𝘥𝘬𝘍𝑥𝑦𝑚𝑏𝑒𝑟𝑔𝑡𝜇—≠ⁿˣ⋅􀀀]+\s*") # translate will fail for these
        self._hash_re = re.compile(r"\s*#+\s*")
        self._table_empty_re = re.compile(r"\s*:-:\s*")
        self._newline_re = re.compile(r"\s*(\\n)+\s*")
        self._index_placeholder_re = re.compile(r"\s*§(image|formula)§\s*")
        self._input_re = re.compile(r"\s*\[\[☃\s+[a-z-]+\s*\d*\]\]\s*")
        self._image_re = re.compile(r"\s*!\[([^\]]*)\]\(\s*(http|https|web\+graphie):\/\/ka-perseus-(images|graphie)\.s3\.amazonaws\.com\/[0-9a-f]+(\.(svg|png|jpg|jpeg))?\)\s*")
        self._tag_re = re.compile(r"\s*</?\s*[a-z-]+\s*([a-z-]+=\"[^\"]+\"\s*)*\s*/?>\s*")
        self._suburl_re = re.compile(r"\s*\[\**([^\]\*]+)\**\]\s*\(\s*[^\)]+\s*\)\s*")
        self._code_re = re.compile(r"\s*```[^`]+```\s*")
        self._entity_re = re.compile(r"\s*&[#0-9a-z]+;\s*")
        self._kaplaceholder_re = re.compile(r"\s*\%\([^\)]+\)[a-zA-Z]\s*")
        self._mobile_placeholder_re = re.compile(r"\s*\%[\dA-Za-z](\$[\dA-Za-z])?\s*")
        #
        # Blacklist regexes
        #
        self._text_re = re.compile(r"\\(text|mathrm|textit)\s*\{([^\}]+)\}")
        self._start_whitespace_re = re.compile(r"^\s*")
        self._end_whitespace_re = re.compile(r"\s*")

        self.limit = limit
        self.count = 0
        self.dbgout = open("fullauto-dbg.txt", "w")
        # Blacklisted (actually used in some strings): △☐☺▫
        self.uchars = "■□▢▣▤▥▦▧▨▩▪▬▭▮▯▰▱▲▴▵▶▷▸▹►▻▼▽▾▿◀◁◂◃◄◅◆◇◈◉◊○◌◍◎●◐◑◒◓◔◕◖◗◘◙◚◛◜◝◞◟◠◡◢◣◤◥◧◨◩◪◫◬◭◮◯◰◱◲◳◴◵◶◷◸◹◺◻◼◽◿◾─━│┃┄┅┆┇┈┉┊┋┌┍┎┏┐┑┒┓└┕┖┗┘┙┚┛├┝┞┟┠┡┢┣┤┥┦┧┨┩┪┫┬┭┮┯┰┱┲┳┴┵┶┷┸┹┺┻┼┽┾┿╀╁╂╃╄╅╆╇╈╉╊╋╌╍╎╏═║╒╓╔╕╖╗╘╙╚╛╜╝╞╟╠╡╢╣╤╥╦╧╨╩╪╫╬╭╮╯╰╱╲╳╴╵╶╷╸╹╺╻╼╽╾╿▀▁▂▃▄▅▆▇█▉▊▋▌▍▎▏▐░▒▓▔▕▖▗▘▙▚▛▜▝▞▟☀☁☂☄★☆☇☈☉☊☋☌☍☎☏☑☒☓☔☕☖☗☘☙☚☛☜☝☞☟☠☡☢☣☤☥☦☧☨☩☪☫☬☭☮☯☰☱☲☳☴☵☶☷☸☹☻☼☽☾☿♀♁♂♃♄♅♆♇♈♉♊♋♌♍♎♏♐♑♒♓♔♕♖♗♘♙♚♛♜♝♞♟"
        assert(" " not in self.uchars)
        assert(len(set(list(self.uchars))) == len(self.uchars))
        # Create map between placeholders. This is required for nested patterns.
        self.protoPlaceholderToNumericPlaceholder = {
            c: self.placeholder(i)
            for i, c in enumerate(self.uchars)
        }

    def __del__(self):
        self.dbgout.close()

    def proto_placeholder(self, n):
        return self.uchars[n]

    def placeholder(self, n):
        #return self.uchars[n]
        return "{}{}{}".format(self.nonce1, n, self.nonce2)

    def placeholder_replace(self, s, n, regex, subtrans_groupno=None):
        repmap = {}
        while True:
            match = regex.search(s)
            if match is None: # No more formulas
                break
            formula = match.group(0)
            current_placeholder = self.proto_placeholder(n)
            # Subtranslate
            if subtrans_groupno is not None:
                subgroup = match.group(subtrans_groupno)
                # Extract whitespace before and after
                ws_before = self._start_whitespace_re.match(subgroup).group(0)
                ws_after = self._end_whitespace_re.match(subgroup).group(0)
                # Subtranslate. Strip whitespaces to re-insert the correct amount later
                trans = self.google_translate(subgroup).strip()
                trans2 = self.yandex_translate(subgroup).strip()

                trans = "{}{}{}".format(ws_before, trans, ws_after)
                trans2 = "{}{}{}".format(ws_before, trans2, ws_after)
                formula = formula.replace(subgroup, trans)
                #print("Subgroup translation: {} --> {}".format(match.group(0), formula))
            # Add into map
            repmap[current_placeholder] = formula
            # Add spaces before and after placeholder to separate from other elements of text
            s = regex.sub(current_placeholder, s, count=1)
            n += 1
        return s, repmap, n

    def final_replace(self, s, n):
        """
        Replace proto placeholders by final placeholders
        """
        for i in range(n):
            s = s.replace(self.proto_placeholder(i), " {} ".format(self.placeholder(i)))
        return s


    def first_stage_backreplace(self, s, repmap):
        """
        Replace proto placeholders by final placeholders
        """
        for protoPlaceholder, _ in repmap:
            # Get numeric placeholder
            placeholder = self.protoPlaceholderToNumericPlaceholder[protoPlaceholder]
            # Check if it got mis-translated...
            if placeholder not in s:

                # Special case for nested patterns:
                # Nested patterns will not be replaced by 2nd stage (numeric) placeholders
                is_nested = False
                for _, val in repmap:
                    if protoPlaceholder in val: # Its nested in SOME pattern
                        is_nested = True
                        break

                if is_nested:
                    continue # no need to replace numeric by proto pattern
                else: # not nested, fail!
                    #print(red("{} not found in '{}'".format(placeholder, s), bold=True))
                    print("{} not found in '{}'".format(placeholder, s), bold=True)
                    return None
            if s.count(placeholder) > 1:
                #print(red("Placeholder {} was duplicated in '{}'".format(placeholder, s), bold=True))
                print("Placeholder {} was duplicated in '{}'".format(placeholder, s), bold=True)
                return None
            # Replace by proto-placeholder which is a unicode char
            s = re.sub(r"\s*" + placeholder + r"\s*",
                protoPlaceholder, s, flags=re.UNICODE)
        return s

    def check_no_placeholders_present(self, s):
        for c in self.uchars:
            if c in s:
                #print(red("Found placeholder {} in '{}'".format(c, s), bold=True))
                print("Found placeholder {} in '{}'".format(c, s), bold=True)
                return False
        return True

    def combo_count(self, s, char):
        return [s.count(char * n) for n in range(1, 10)]

    def back_replace(self, s, repmap):
        """
        Like simple_replace, but replaces
        """
        for placeholder, rep in repmap:
            s = s.replace(placeholder, rep)
        return s

    def preproc(self, s, subtranslate=True):
        """
        Forward-replace first with proto-placeholders to avoid impacting

        As proto-placeholders are unicode chars and will often be touched by the translator,
        we then replace them by final numeric code placeholders with whitespace
        added before and after which are not touched.
        """
        n = 0

        # \\n or might be directly followed by a word character and might be screwed up
        # We count their number of newline combos now to check restoration later.
        nAsterisks = self.combo_count(s, "*")
        nNewlines = self.combo_count(s, "\\n")
        nHashs = self.combo_count(s, "#")
        nUnderscores = self.combo_count(s, "_")

        s, indexPlaceholderMap, n = self.placeholder_replace(s, n, self._index_placeholder_re)
        # Subtranslate URL title
        s, sublurlMap, n = self.placeholder_replace(s, n, self._suburl_re,
            subtrans_groupno=1 if subtranslate else None)
        s, textMap, n = self.placeholder_replace(s, n, self._text_re,
            subtrans_groupno=2 if subtranslate else None)

        # Whitespace before and after is relevant for \\text{...}.
        s, specialCharsMap, n = self.placeholder_replace(s, n, self._special_chars_re)
        s, kaPlaceholderMap, n = self.placeholder_replace(s, n, self._kaplaceholder_re)
        s, entityMap, n = self.placeholder_replace(s, n, self._entity_re)
        s, tableEmptyMap, n = self.placeholder_replace(s, n, self._table_empty_re)
        s, mobilePlaceholderMap, n = self.placeholder_replace(s, n, self._mobile_placeholder_re)
        s, formulaMap, n = self.placeholder_replace(s, n, self._formula_re)
        s, asteriskMap, n = self.placeholder_replace(s, n, self._asterisk_re)
        s, underscoreMap, n = self.placeholder_replace(s, n, self._underscore_re)
        s, hashMap, n = self.placeholder_replace(s, n, self._hash_re)
        s, newlineMap, n = self.placeholder_replace(s, n, self._newline_re)
        s, inputMap, n = self.placeholder_replace(s, n, self._input_re)
        s, imgMap, n = self.placeholder_replace(s, n, self._image_re)
        # Code before tag as code might contain tag
        s, codeMap, n = self.placeholder_replace(s, n, self._code_re)
        s, tagMap, n = self.placeholder_replace(s, n, self._tag_re)

        repmap = list(itertools.chain(*[
            specialCharsMap.items(),
            indexPlaceholderMap.items(),
            sublurlMap.items(),
            textMap.items(),
            underscoreMap.items(),
            tableEmptyMap.items(),
            kaPlaceholderMap.items(),
            entityMap.items(),
            mobilePlaceholderMap.items(),
            formulaMap.items(),
            asteriskMap.items(),
            hashMap.items(),
            newlineMap.items(),
            inputMap.items(),
            imgMap.items(),
            codeMap.items(),
            tagMap.items()
        ]))[::-1]

        # Final placeholder replacement
        s = self.final_replace(s, n)

        return s, PlaceholderInfo(n, repmap, nAsterisks, nNewlines, nHashs, nUnderscores)

    def postproc(self, engl, s, info):
        """
        Back-replace placeholders
        """
        # Replace numeric placeholders by unicode placeholders
        # This prevents spaces between placeholders cross-affecting each other
        s = self.first_stage_backreplace(s, info.replaceMap)
        if s is None:  # Placeholder missing or changed
            return None

        # Replace unicode placeholders by their original value
        s = self.back_replace(s, info.replaceMap)

        # Now no placeholders should be left
        if not self.check_no_placeholders_present(s):
            return None

        #
        # Check if combinations match
        #
        nAsterisksNew = self.combo_count(s, "*")
        if nAsterisksNew != info.nAsterisks:
            #print(red("* not reconstructed in '{}' engl '{}'".format(s, engl), bold=True))
            print("* not reconstructed in '{}' engl '{}'".format(s, engl), bold=True)
            return None

        nNewlinesNew = self.combo_count(s, "\\n")
        if nNewlinesNew != info.nNewlines:
            #print(red("\\n not reconstructed in '{}' engl '{}'".format(s, engl), bold=True))
            print("\\n not reconstructed in '{}' engl '{}'".format(s, engl), bold=True)
            return None

        nUnderscoresNew = self.combo_count(s, "_")
        if nUnderscoresNew != info.nUnderscores:
            #print(red("_ not reconstructed in '{}' engl '{}'".format(s, engl), bold=True))
            print("_ not reconstructed in '{}' engl '{}'".format(s, engl), bold=True)
            return None

        return s


    def yandex_translate(self, txt):
        host = "https://translate.yandex.net/api/v1.5/tr.json/translate"
        key = 'trnsl.1.1.20171202T133038Z.284a1f7f3c4c7f0f.3bc14c3826e10105dbf20850e33e1c84136d66e7'
        yandexResult = requests.get(host, params={'key': key,'lang':'en-sv','text':txt})
        yandexOutput = yandexResult.text[yandexResult.text.index('[')+2:yandexResult.text.index(']')-1]

        return yandexOutput


    def google_translate(self, txt):
        translator = Translator()
        googleResult = translator.translate(txt, src="en", dest=self.lang.partition("-")[0])
        
        return googleResult.text

    def check_regex_equal(self, regex, s1, s2, desc):
        m1 = [m.group(0).strip() for m in regex.finditer(s1)]
        m2 = [m.group(0).strip() for m in regex.finditer(s2)]
        if m1 != m2:
            #print(red("Syntax comparison failed for {} regex:\n\t{}\n\t{}".format(
            print("Syntax comparison failed for {} regex:\n\t{}\n\t{}".format(
                desc, str(m1), str(m2)), bold=True)
            #print(red("Original: {}".format(s1), bold=True))
            print("Original: {}".format(s1), bold=True)
            #print(red("Translated: {}".format(s2), bold=True))
            print("Translated: {}".format(s2), bold=True)
            return False
        return True


    def handle_translations(self,engl,info,engl_proc,translated):

        # Back-replace placeholders
        txt2 = self.postproc(engl, translated, info)
        # Emit debug data
        print("{", file=self.dbgout)
        print("\tEngl:",engl, file=self.dbgout)
        print("\tMap:",info.replaceMap, file=self.dbgout)
        print("\tPreproc:", engl_proc, file=self.dbgout)
        print("\tTranslated:", translated, file=self.dbgout)
        print("\tResult:", txt2, file=self.dbgout)
        print("}", file=self.dbgout)
        # Syntax equivalence check.
        # Ignores whitespace as it will happen for various languages due to grammatics
        if txt2 is None:
            return None
        # disabled as it fails for text subtrans
        #if not self.check_regex_equal(self._formula_re, engl, txt2, "formula"):
        #    return None
        if not self.check_regex_equal(self._asterisk_re, engl, txt2, "asterisk"):
            return None
        if not self.check_regex_equal(self._entity_re, engl, txt2, "enttiy"):
            return None
        if not self.check_regex_equal(self._newline_re, engl, txt2, "newline"):
            return None
        if not self.check_regex_equal(self._input_re, engl, txt2, "input"):
            return None
        # disabled as URL subtrans will cause it to fail
        #if not self.check_regex_equal(self._image_re, engl, txt2, "image"):
        #    return None
        if not self.check_regex_equal(self._tag_re, engl, txt2, "tag"):
            return None
        if not self.check_regex_equal(self._code_re, engl, txt2, "code"):
            return None
        if not self.check_regex_equal(self._kaplaceholder_re, engl, txt2, "KA placeholder"):
            return None
        if not self.check_regex_equal(self._mobile_placeholder_re, engl, txt2, "KA mobile placeholder"):
            return None
        # Reduce limit only after successful translation
        self.limit -= 1
        self.count += 1
        if self.count % 100 == 0:
            print("Beastified {} strings".format(self.count))
        return txt2


    def translate(self, engl):
        if engl is None:
            return None
        # Use limit on how much to translate at once
        if self.limit <= 0:
            return None # dont translate
        # Check if there are any placeholder-type characters in the string
        if not self.check_no_placeholders_present(engl):
            return None
        # Replace formulas etc. by placeholders.
        # Subtranslation will fail back verification so we'll do it later
        engl_proc, info = self.preproc(engl, subtranslate=False)
        # Check validity of placeholders (should yield original string)
        test_postproc = self.postproc(engl, engl_proc, info)

        if test_postproc != engl:
            #print(red("Validation reproduction failed: '{}' instead of '{}'".format(test_postproc, engl)))
            print("Validation reproduction failed: '{}' instead of '{}'".format(test_postproc, engl))
            return None
        # Do actual preprocessing with possible subtranslation
        engl_proc, info = self.preproc(engl, subtranslate=True)
        # Perform translation
        googleTranslated = self.handle_translations(engl,info,engl_proc,self.google_translate(engl_proc))
        yandexTranslated = self.handle_translations(engl,info,engl_proc,self.yandex_translate(engl_proc))
                                
        translated = {'Google:': googleTranslated,'Yandex:': yandexTranslated}
        return translated
        
        
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('string', help='The string to translate')
    parser.add_argument('-l', '--lang', default="sv", help='The language to translate to')
    args = parser.parse_args()

    fa = FullAutoTranslator(args.lang)
    results = fa.translate(args.string)
    print('\n')
    for line in results:
        print(line,'\n',results[line],'\n\n')

    print('\n')
        
