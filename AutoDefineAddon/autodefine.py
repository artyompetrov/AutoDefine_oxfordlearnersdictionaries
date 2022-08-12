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
from aqt.utils import askUser
from bs4 import BeautifulSoup
import requests
from .webbrowser import webbrowser
import importlib.util
import sys
from contextlib import contextmanager
import pathlib


SOURCE_FIELD = 0

DEFINITION_FIELD = 1

PRONUNCIATION_FIELD = 2

AUDIO_FIELD = 3

OPEN_IMAGES_IN_BROWSER = True

GOOGLESEARCH_APPEND = ""

PRIMARY_SHORTCUT = "ctrl+alt+e"

REPLACE_BY = '____'

DEBUG = False

PHONETICS = True

AUDIO = True


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
ps = nltk.stem.PorterStemmer()

tokinize = nltk.wordpunct_tokenize
unify = ps.stem

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/39.0.2171.95 Safari/537.36'
}


def get_data(editor):
    try:
        editor.saveNow(lambda: _get_data(editor))
    except Exception as ex:
        raise Exception("Error occurred. Please copy this error massage and open an issue on "
                        "https://github.com/artyompetrov/AutoDefine_oxfordlearnersdictionaries/issues "
                        "so I could investigate the reason of error and fix it") from ex


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


def _get_data(editor):
    word = get_word(editor)
    if word == "":
        tooltip("AutoDefine: No text found in note fields.")
        return

    is_successful, found_word, articles = get_links_to_articles(word)

    if not is_successful:
        tooltip(f"Word '{word}' not found.")
        return

    insert_into_field(editor, '', DEFINITION_FIELD, overwrite=True)
    if DEBUG:
        for article in articles:
            insert_into_field(editor, '<a href="' + article['link'] + '">' + article['link'] + '</a><br/>',
                              DEFINITION_FIELD, overwrite=False)

    definition_html = get_definition_html(articles)

    insert_into_field(editor, definition_html, DEFINITION_FIELD, overwrite=False)

    if PHONETICS:
        phonetics = get_phonetics(articles)
        insert_into_field(editor, phonetics, PHONETICS_FIELD, overwrite=True)

    if found_word != word:
        if askUser(f"Attention! found another word '{found_word}', replace source field?"):
            insert_into_field(editor, found_word, SOURCE_FIELD, overwrite=True)
            word = found_word

    if AUDIO:
        audio = get_audio(articles)
        insert_into_field(editor, audio, AUDIO_FIELD, overwrite=True)

    if OPEN_IMAGES_IN_BROWSER:
        webbrowser.open(
            "https://www.google.com/search?q= " + word + GOOGLESEARCH_APPEND + "&safe=off&tbm=isch&tbs=isz:lt,islt:xga",
            0, False)

    focus_zero_field(editor)


def nltk_token_spans(txt):
    tokens = tokinize(txt)
    offset = 0
    for token in tokens:
        offset = txt.find(token, offset)
        next_offset = offset + len(token)
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
        cur_position = position
        for word_to_replace in words_to_replace:
            token, start, stop = spans[cur_position]
            if all_match:
                if unify(str.lower(token)) != word_to_replace:
                    all_match = False
                    break
                else:
                    cur_position += 1
                    if cur_position >= len(spans):
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


def get_links_to_articles(request_word):
    request_word = request_word.replace(' ', '-')
    url = f'https://www.oxfordlearnersdictionaries.com/search/american_english/?q={request_word}'
    response = requests.get(url, headers=HEADERS)
    data = response.content
    result_link = response.url
    results = list()
    if 'spellcheck' in result_link:
        return False, None, None
    else:
        result_link = result_link.split("?")[0].split("#")[0]
        found_word = result_link.split('/')[-1].split('_')[0]
        results.append({'link': result_link, 'data': data})
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
                    results.append({'link': maybe_result_link, 'data': data})

        return True, found_word, results


def get_definition_html(articles_list):
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
            prefix = xr_gs_tag.find('span', {"class": "prefix"})
            if prefix is not None and prefix.get_text() == 'see':
                xr_gs_tag.decompose()
            else:
                new_param = BeautifulSoup('<br>' + xr_gs_tag.decode_contents(), 'html.parser')
                xr_gs_tag.replaceWith(new_param)

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

        pv_gs_tags = entry.find_all('span', {"class": "pv-gs"})
        for pv_gs_tag in pv_gs_tags:
            pv_gs_tag.decompose()

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
                new_param = BeautifulSoup('<i>' + replace_word_in_example(word, cf.get_text()) + '</i><br/>',
                                          'html.parser')
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

        for ol in entry.find_all('ol'):
            new_param = BeautifulSoup('<ul>' + ol.decode_contents() + '</ul>', 'html.parser')
            ol.replaceWith(new_param)

        entry = clean_soup(entry).decode_contents()

        entry = re.sub(r"\(\s+", "(", entry)
        entry = re.sub(r"\s+\)", ")", entry)

        if need_part_of_speech:
            entry = '<i>' + word_type + '</i><br/>' + entry

        entry = BeautifulSoup(entry, 'html.parser').prettify()

        result.append(entry)

    return "<hr>".join(result)


def get_audio(articles):
    audio_dict = {}
    for article in articles:
        data = article['data']

        chosen_soup = BeautifulSoup(data, 'html.parser')
        entry = chosen_soup.find('div', {"class": "entry"})
        header = entry.find('div', {"class": "top-container"})
        word_type = header.find('span', {"class": "pos"}).get_text()

        audio_button = header.find('div', {"class": "sound audio_play_button pron-usonly icon-audio"})
        audio_link = audio_button.attrs["data-src-mp3"]
        audio_name = audio_link.split('/')[-1]

        collection_path = pathlib.Path(mw.col.path).parent.absolute()
        media_path = os.path.join(collection_path, "collection.media")
        audio_path = os.path.join(media_path, audio_name)

        value = audio_dict.get(audio_name, None)
        if value is not None:
            value['word_types'].append(word_type)
        else:
            if not os.path.exists(audio_path):
                response = requests.get(audio_link, headers=HEADERS)
                with open(audio_path, 'wb') as f:
                    f.write(response.content)
            audio_dict[audio_name] = {'word_types': [word_type], "audio_name": audio_name}

    if len(audio_dict) == 0:
        return "No audio found"
    elif len(audio_dict) == 1:
        return f'[sound:{audio_dict[next(iter(audio_dict))]["audio_name"]}]'
    else:
        return "<br/>".join(["[sound:" + audio_dict[key]['audio_name'] + '] - ' +
                             ", ".join(audio_dict[key]['word_types']) for key in iter(audio_dict)])


def get_phonetics(articles):
    phonetics_dict = {}
    for article in articles:
        data = article['data']
        chosen_soup = BeautifulSoup(data, 'html.parser')
        entry = chosen_soup.find('div', {"class": "entry"})
        header = entry.find('div', {"class": "top-container"})
        word_type = header.find('span', {"class": "pos"}).get_text()
        phonetics = header.find('span', {"class": "phon"})

        name_tags = phonetics.find_all('span', {"class": "name"})
        for name_tag in name_tags:
            name_tag.decompose()

        separator_tags = phonetics.find_all('span', {"class": "separator"})
        for separator_tag in separator_tags:
            separator_tag.decompose()

        wrap_tags = phonetics.find_all('span', {"class": "wrap"})
        for wrap_tag in wrap_tags:
            wrap_tag.decompose()

        phonetics = phonetics.get_text()

        value = phonetics_dict.get(phonetics, None)
        if value is not None:
            value.append(word_type)
        else:
            phonetics_dict[phonetics] = [word_type]

    if len(phonetics_dict) == 0:
        return "No phonetics found"
    elif len(phonetics_dict) == 1:
        return '[' + next(iter(phonetics_dict)) + ']'
    else:
        return "<br/>".join(["[" + key + '] - ' + ", ".join(phonetics_dict[key]) for key in iter(phonetics_dict)])


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


def clean_html(raw_html):
    return re.sub(re.compile('<.*?>'), '', raw_html).replace("&nbsp;", " ")


def setup_buttons(buttons, editor):
    both_button = editor.addButton(icon=os.path.join(os.path.dirname(__file__), "images", "icon30.png"),
                                   cmd="AD",
                                   func=get_data,
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
        if 'PHONETICS' in extra:
            PHONETICS = extra['PHONETICS']
        if 'AUDIO' in extra:
            AUDIO = extra['AUDIO']
        if 'SOURCE_FIELD' in extra:
            SOURCE_FIELD = extra['SOURCE_FIELD']
        if 'DEFINITION_FIELD' in extra:
            DEFINITION_FIELD = extra['DEFINITION_FIELD']
        if 'PHONETICS_FIELD' in extra:
            PHONETICS_FIELD = extra['PHONETICS_FIELD']
        if 'AUDIO_FIELD' in extra:
            AUDIO_FIELD = extra['AUDIO_FIELD']
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
