# AutoDefine Oxford Learner's Dictionaries Anki Add-on
# Auto-defines words using Oxford Learner's Dictionaries, optionally adding images.
# Copyright (c) Artem Petrov    apsapetrov@gmail.com
# https://github.com/artyompetrov/AutoDefine_oxfordlearnersdictionaries Licensed under GPL v2
# forked from:
# Copyright (c) Robert Sanek    robertsanek.com    rsanek@gmail.com
# https://github.com/z1lc/AutoDefine                      Licensed under GPL v2

import os
from collections import namedtuple

import platform
import re
import traceback
import urllib.error
import urllib.parse
import urllib.request
from anki import version
from anki.hooks import addHook
from aqt import mw
from aqt.utils import showInfo, tooltip
from http.client import RemoteDisconnected
from urllib.error import URLError
from xml.etree import ElementTree as ET
from bs4 import BeautifulSoup
import json
import requests

from .libs import webbrowser

# --------------------------------- SETTINGS ---------------------------------

# Index of field to insert definitions into (use -1 to turn off)
DEFINITION_FIELD = 1

CORPUS = 'american_english'

# Open a browser tab with an image search for the same word?
OPEN_IMAGES_IN_BROWSER = False

OPEN_ARTICLE_IN_BROWSER = True

PRIMARY_SHORTCUT = "ctrl+alt+e"

PART_OF_SPEECH_ABBREVIATION = {"verb": "v.", "noun": "n.", "adverb": "adv.", "adjective": "adj."}

HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}


def get_definition(editor):
    editor.saveNow(lambda: _get_definition(editor))


def validate_settings():
    pass




def _focus_zero_field(editor):
    # no idea why, but sometimes web seems to be unavailable
    if editor.web:
        editor.web.eval("focusField(%d);" % 0)


def _get_word(editor):
    word = ""
    maybe_web = editor.web
    if maybe_web:
        word = maybe_web.selectedText()

    if word is None or word == "":
        maybe_note = editor.note
        if maybe_note:
            word = maybe_note.fields[0]

    word = clean_html(word).strip()
    return word


def _get_definition(editor):
    validate_settings()
    word = _get_word(editor)
    if word == "":
        tooltip("AutoDefine: No text found in note fields.")
        return

    articles_list = get_articles_list(word)

    selected_article = articles_list[0]

    to_return = get_article(selected_article["link"])

    insert_into_field(editor, to_return, DEFINITION_FIELD, overwrite=True)

    if OPEN_IMAGES_IN_BROWSER:
        webbrowser.open("https://www.google.com/search?q= " + word + "&safe=off&tbm=isch&tbs=isz:lt,islt:xga", 0, False)

    _focus_zero_field(editor)


def get_articles_list(word):
    word.replace(' ', '-')
    url = f'https://www.oxfordlearnersdictionaries.com/search/{CORPUS}/?q={word}'
    response = requests.get(url, headers=HEADERS)
    data = response.content
    soup = BeautifulSoup(data, 'html.parser')
    result_link = response.url
    results = set()

    if soup.find_all('span', {"class": "def"}):
        header = soup.find('div', {"class": "webtop-g"})
        word = header.find('h2', {"class": "h"}).get_text()
        word_type = header.find('span', {"class": "pos"}).get_text()
        results.add(json.dumps({'word': word, 'word_type': word_type, 'link': result_link}))

    #related_entries = soup.find('div', {"id": "relatedentries"})
    #if related_entries:
    #    for a in related_entries.find_all('a'):
    #        if a.has_attr('href'):
    #            link = a['href']
    #            word_type = a.find('pos')
    #            if word_type is not None:
    #                word_type = word_type.get_text()
    #                word = a.get_text().replace(word_type, '').strip()
    #                results.add(json.dumps({'word': word, 'word_type': word_type, 'link': link}))

    results = [json.loads(result) for result in results]
    return results


def get_article(url):
    if OPEN_ARTICLE_IN_BROWSER:
        webbrowser.open(url, 0, False)
    result = ""
    chosen_response = requests.get(url, headers=HEADERS)
    chosen_data = chosen_response.content
    chosen_soup = BeautifulSoup(chosen_data, 'html.parser')

    header = chosen_soup.find('div', {"class": "webtop-g"})
    word = header.find('h2', {"class": "h"}).get_text()
    word_type = header.find('span', {"class": "pos"}).get_text()

    entry = chosen_soup.find('div', {"class": "entry"})
    ol = entry.find('ol', {"class": "h-g"})
    if ol:
        shcut_gs = ol.find_all('span', {"class": "shcut-g"})
        if len(shcut_gs) > 0:
            for shcut_gs in shcut_gs:
                #shcut = shcut_gs.find('span', {"class": "shcut"})
                #if shcut:
                #    result += '<i>'+shcut.get_text()+'</i><br>'
                for li in shcut_gs.find_all('li', {"class": "sn-g"}):
                    for deff in li.find_all('span', {"class": "def"}):
                        result += '<b>'+deff.get_text()+'</b>' + "<br>"
                    examples = li.find_all('span', {"class": "x"})
                    if len(examples) > 0:
                        result += "Ex:<br>"
                        for ex in examples:
                            result += '* ' + ex.get_text() + "<br>"
                    result += "<br>"
                result += "<hr>"
        else:
            for li in ol.find_all('li', {"class": "sn-g"}):
                for deff in li.find_all('span', {"class": "def"}):
                    result += '<b>'+deff.get_text()+'</b>' + "<br>"
                examples = li.find_all('span', {"class": "x"})
                if len(examples) > 0:
                    result += "Ex:<br>"
                    for ex in examples:
                        result += '* ' + ex.get_text() + "<br>"
                result += "<br>"
    else:
        deff = entry.find('span', {"class": "def"})
        if deff:
            result += '<b>'+deff.get_text()+'</b>' + "<br>"
            examples = entry.find_all('span', {"class": "x"})
            if len(examples) > 0:
                result += "Ex:<br>"
                for ex in examples:
                    result += '* ' + ex.get_text() + "<br>"
    result = re.sub('(<br>)+', '<br>', result)
    result = result.replace('<br><hr>', '<hr>')
    result = re.sub('(<br>)*(<hr>)*$', '', result)
    return result

def _abbreviate_part_of_speech(part_of_speech):
    if part_of_speech in PART_OF_SPEECH_ABBREVIATION.keys():
        part_of_speech = PART_OF_SPEECH_ABBREVIATION[part_of_speech]

    return part_of_speech


def insert_into_field(editor, text, field_id, overwrite=False):
    if len(editor.note.fields) <= field_id:
        tooltip("AutoDefine: Tried to insert '%s' into user-configured field number %d (0-indexed), but note type only "
                "has %d fields. Use a different note type with %d or more fields, or change the index in the "
                "Add-on configuration." % (text, field_id, len(editor.note.fields), field_id + 1), period=10000)
        return
    if overwrite:
        editor.note.fields[field_id] = text
    else:
        editor.note.fields[field_id] += text
    editor.loadNote()


# via https://stackoverflow.com/a/12982689
def clean_html(raw_html):
    return re.sub(re.compile('<.*?>'), '', raw_html).replace("&nbsp;", " ")


def setup_buttons(buttons, editor):
    both_button = editor.addButton(icon=os.path.join(os.path.dirname(__file__), "images", "icon16.png"),
                                   cmd="AD",
                                   func=get_definition,
                                   tip="AutoDefine Word (%s)" %
                                       ("no shortcut" if PRIMARY_SHORTCUT == "" else PRIMARY_SHORTCUT),
                                   toggleable=False,
                                   label="",
                                   keys=PRIMARY_SHORTCUT,
                                   disables=False)

    buttons.append(both_button)
    return buttons

addHook("setupEditorButtons", setup_buttons)

if getattr(mw.addonManager, "getConfig", None):
    config = mw.addonManager.getConfig(__name__)

    if '1 params' in config:
        extra = config['1 params']
        if 'DEFINITION_FIELD' in extra:
            DEFINITION_FIELD = extra['DEFINITION_FIELD']
        if 'OPEN_IMAGES_IN_BROWSER' in extra:
            OPEN_IMAGES_IN_BROWSER = extra['OPEN_IMAGES_IN_BROWSER']

    if '2 shortcuts' in config:
        shortcuts = config['2 shortcuts']
        if '1 PRIMARY_SHORTCUT' in shortcuts:
            PRIMARY_SHORTCUT = shortcuts['1 PRIMARY_SHORTCUT']