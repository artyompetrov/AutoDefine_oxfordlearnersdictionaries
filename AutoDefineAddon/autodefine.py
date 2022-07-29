# AutoDefine Oxford Learner's Dictionaries Anki Add-on
# Auto-defines words using Oxford Learner's Dictionaries, optionally adding images.
# Copyright (c) Artem Petrov    apsapetrov@gmail.com
# https://github.com/artyompetrov/AutoDefine_oxfordlearnersdictionaries Licensed under GPL v2
# forked from:
# Copyright (c) Robert Sanek    robertsanek.com    rsanek@gmail.com
# https://github.com/z1lc/AutoDefine                      Licensed under GPL v2

import os
import re
from anki.hooks import addHook
from aqt import mw
from aqt.utils import tooltip
from bs4 import BeautifulSoup
import requests
from .webbrowser import webbrowser
import importlib.util
import sys
from contextlib import contextmanager
import pathlib

@contextmanager
def add_to_path(p):
    import sys
    old_path = sys.path
    sys.path = sys.path[:]
    sys.path.insert(0, str(p))
    try:
        yield
    finally:
        sys.path = old_path

def path_import(name):
    absolute_path = os.path.join(pathlib.Path(__file__).parent, 'modules')
    init_file = os.path.join(absolute_path, name, '__init__.py')
    with add_to_path(absolute_path):
        spec = importlib.util.spec_from_file_location(name, init_file)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

nltk = path_import('nltk')

SOURCE_FIELD = 0

DEFINITION_FIELD = 1

PRONUNCIATION_FIELD = 2

CORPUS = 'american_english'

OPEN_IMAGES_IN_BROWSER = True

GOOGLESEARCH_APPEND = " definition"

PRIMARY_SHORTCUT = "ctrl+alt+e"

REPLACE_BY = '____'

DEBUG = False

#from nltk.stem.wordnet import WordNetLemmatizer
#lem = WordNetLemmatizer()
from nltk.stem import PorterStemmer
ps = PorterStemmer()
tokinize = nltk.wordpunct_tokenize
unify = ps.stem

HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36' }


def get_definition(editor):
    try:
        editor.saveNow(lambda: _get_definition(editor))
    except Exception as ex:
        raise Exception("Error occurred. Please copy this error massage and open an issue on "
                        "https://github.com/artyompetrov/AutoDefine_oxfordlearnersdictionaries/issues "
                        "so I could investigate the reason of error and fix it") from ex


def validate_settings():
    pass


def focus_zero_field(editor):
    # no idea why, but sometimes web seems to be unavailable
    if editor.web:
        editor.web.eval("focusField(%d);" % 0)


def get_word(editor):
    word = ""
    maybe_web = editor.web
    if maybe_web:
        word = maybe_web.selectedText()

    if word is None or word == "":
        maybe_note = editor.note
        if maybe_note:
            word = maybe_note.fields[SOURCE_FIELD]

    word = clean_html(word).strip()
    return word


def _get_definition(editor):
    validate_settings()
    word = get_word(editor)
    if word == "":
        tooltip("AutoDefine: No text found in note fields.")
        return

    articles_list = get_articles_list(word)

    insert_into_field(editor, '', DEFINITION_FIELD, overwrite=True)
    if DEBUG:
        for article in articles_list:
            insert_into_field(editor, '<a href="' + article['link'] + '">' + article['link'] + '</a><br/>', DEFINITION_FIELD, overwrite=False)

    to_return = get_article(articles_list)

    insert_into_field(editor, to_return, DEFINITION_FIELD, overwrite=False)

    if OPEN_IMAGES_IN_BROWSER:
        webbrowser.open("https://www.google.com/search?q= " + word + GOOGLESEARCH_APPEND + "&safe=off&tbm=isch&tbs=isz:lt,islt:xga", 0, False)

    focus_zero_field(editor)


def nltk_token_spans(txt):
    tokens = tokinize(txt)
    offset = 0
    for token in tokens:
        offset = txt.find(token, offset)
        next_offset = offset+len(token)
        yield token, offset, next_offset
        assert token == txt[offset:next_offset]
        offset = next_offset


def replace_word_in_example(words, example):
    words_to_replace = [unify(str.lower(word)) for word in tokinize(words)]

    result = str()
    spans = list(nltk_token_spans(example))

    replaced_anything = False
    position = 0
    offset = 0
    while position < len(spans):
        all_match = True
        cur_posititon = position
        for word_to_replace in words_to_replace:
            token, start, stop = spans[cur_posititon]
            if all_match:
                if unify(str.lower(token)) != word_to_replace:
                    all_match = False
                    break
                else:
                    cur_posititon += 1
                    if cur_posititon >= len(spans):
                        break
        if all_match:
            for i in range(len(words_to_replace)):
                token, start, stop = spans[position + i]
                replacement = REPLACE_BY.replace("$", token)
                spaces_to_add = start - len(result) - offset
                offset += len(token) - len(replacement)
                if spaces_to_add < 0:
                    raise Exception("Incorrect spaces_to_add value")
                result += ' ' * spaces_to_add
                result += replacement

            position += len(words_to_replace)
            replaced_anything = True
        else:
            token, start, stop = spans[position]
            spaces_to_add = start - len(result) - offset
            if spaces_to_add < 0:
                raise Exception("Incorrect spaces_to_add value")
            result += ' ' * spaces_to_add
            result += token
            position += 1

    if not replaced_anything:
        result = '<font color="#0000ff" class="clean_ignore">' + result + '</font>'

    return result


def get_articles_list(request_word):
    request_word = request_word.replace(' ', '-')
    url = f'https://www.oxfordlearnersdictionaries.com/search/{CORPUS}/?q={request_word}'
    response = requests.get(url, headers=HEADERS)
    data = response.content
    result_link = response.url
    results = list()
    if 'spellcheck' in result_link:
        raise Exception("spellcheck error url: " + url)
    else:
        result_link = result_link.split("?")[0].split("#")[0]
        results.append({'word': request_word, 'link': result_link, 'data': data})
        pattern = r"_(\d+)$"
        if re.search(pattern, result_link):
            max_attempts = 5
            try_count = 1
            while try_count < max_attempts:
                try_count += 1
                maybe_result_link = re.sub(pattern, "_" + str(try_count), result_link)
                response = requests.get(maybe_result_link, headers=HEADERS)
                data = response.content
                if 'Word not found in the dictionary' in str(data):
                    break
                else:
                    results.append({'word': request_word, 'link': maybe_result_link, 'data': data})
    return results


def get_article(articles_list):
    need_part_of_speech = len(articles_list) > 1
    result = list()
    for article in articles_list:
        data = article['data']

        chosen_soup = BeautifulSoup(data, 'html.parser')

        entry = chosen_soup.find('div', {"class": "entry"})

        header = entry.find('div', {"class": "top-container"})
        word = header.find('h2', {"class": "h"}).get_text()
        word_type = header.find('span', {"class": "pos"}).get_text()
        header.decompose()

        # tags to delete
        ring_links_box_tags = entry.find_all('div', {"id": "ring-links-box"})
        for ring_links_box_tag in ring_links_box_tags:
            ring_links_box_tag.decompose()

        dictlinks_tags = entry.find_all('span', {"class": "dictlinks"})
        for dictlinks_tags in dictlinks_tags:
            dictlinks_tags.decompose()

        pron_link_tags = entry.find_all('div', {"class": "pron-link"})
        for pron_link_tag in pron_link_tags:
            pron_link_tag.decompose()

        xr_gs_tags = entry.find_all('span', {"class": "xr-gs"})
        for xr_gs_tag in xr_gs_tags:
            xr_gs_tag.decompose()

        dr_gs_tags = entry.find_all('span', {"class": "dr-gs"})
        for dr_gs_tag in dr_gs_tags:
            dr_gs_tag.decompose()

        collapse_tags = entry.find_all('span', {"class": "collapse"})
        for collapse_tag in collapse_tags:
            collapse_tag.decompose()

        gram_g_tags = entry.find_all('span', {"class": "gram-g"})
        for gram_g_tag in gram_g_tags:
            gram_g_tag.decompose()

        num_tags = entry.find_all('span', {"class": "num"})
        for num_tag in num_tags:
            num_tag.decompose()

        script_tags = entry.find_all('script')
        for script_tag in script_tags:
            script_tag.decompose()

        idm_gs_tags = entry.find_all('span', {"class": "idm-gs"})
        for idm_gs_tag in idm_gs_tags:
            idm_gs_tag.decompose()

        ox_enlarge_tags = entry.find_all('div', {"id": "ox-enlarge"})
        for ox_enlarge_tag in ox_enlarge_tags:
            ox_enlarge_tag.decompose()

        pron_g_tags = entry.find_all('span', {"class": "pron-g"})
        for pron_g_tag in pron_g_tags:
            pron_g_tag.decompose()

        sn_g_tags = entry.find_all('li', {"class": "sn-g"})
        for sn_g_tag in sn_g_tags:
            cfs = sn_g_tag.find_all('span', {"class": "cf"}, recursive=False)
            for cf in cfs:
                new_param = BeautifulSoup('<i>' + replace_word_in_example(word, cf.get_text()) + '</i><br/>', 'html.parser')
                cf.replaceWith(new_param)

        # examples
        x_g_tags = entry.find_all('span', {"class": "x-g"})
        for x_g in x_g_tags:
            cfs = x_g.find_all('span', {"class": "cf"})
            for cf in cfs:
                cf.decompose()
            new_param = BeautifulSoup('<li>' + replace_word_in_example(word, x_g.get_text()) + '</li>', 'html.parser')
            x_g.replaceWith(new_param)

        x_gs_tags = entry.find_all('span', {"class": "x-gs"})
        for x_g in x_gs_tags:
            new_param = BeautifulSoup('<ul>' + x_g.decode_contents() + '</ul>', 'html.parser')
            x_g.replaceWith(new_param)

        # hr
        shcut_tags = entry.find_all('span', {"class": "shcut"})
        for shcut_tag in shcut_tags[:1]:
            new_param = BeautifulSoup('<i>' + shcut_tag.get_text() + '</i>', 'html.parser')
            shcut_tag.replaceWith(new_param)
        for shcut_tag in shcut_tags[1:]:
            new_param = BeautifulSoup('<hr/><i>' + shcut_tag.get_text() + '</i>', 'html.parser')
            shcut_tag.replaceWith(new_param)

        # unwrap
        for match in entry.find_all('span'):
            match.unwrap()

        for match in entry.find_all('div'):
            match.unwrap()

        for match in entry.find_all('strong'):
            match.unwrap()

        entry = clean_soup(entry).decode_contents()

        entry = re.sub("\(\s+", "(", entry)
        entry = re.sub("\s+\)", ")", entry)

        if need_part_of_speech:
            entry = '<i>' + word_type + '</i>' + entry

        entry = BeautifulSoup(entry, 'html.parser').prettify()

        result.append(entry)

    return "<hr>".join(result)


def clean_soup(content):
    for attr in list(content.attrs):
        del content.attrs[attr]
    for tags in content.find_all():
        if tags.has_attr('class') and 'clean_ignore' in tags['class']:
            continue

        for val in list(tags.attrs):
            del tags.attrs[val]
    return content


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
    both_button = editor.addButton(icon=os.path.join(os.path.dirname(__file__), "images", "icon30.png"),
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
        if 'DEBUG' in extra:
            DEBUG = extra['DEBUG']
        if 'SOURCE_FIELD' in extra:
            SOURCE_FIELD = extra['SOURCE_FIELD']
        if 'DEFINITION_FIELD' in extra:
            DEFINITION_FIELD = extra['DEFINITION_FIELD']
        if 'OPEN_IMAGES_IN_BROWSER' in extra:
            OPEN_IMAGES_IN_BROWSER = extra['OPEN_IMAGES_IN_BROWSER']
        if 'REPLACE_BY' in extra:
            REPLACE_BY = extra['REPLACE_BY']
        if 'GOOGLESEARCH_APPEND' in extra:
            GOOGLESEARCH_APPEND = extra['GOOGLESEARCH_APPEND']


    if '2 shortcuts' in config:
        shortcuts = config['2 shortcuts']
        if 'PRIMARY_SHORTCUT' in shortcuts:
            PRIMARY_SHORTCUT = shortcuts['PRIMARY_SHORTCUT']
