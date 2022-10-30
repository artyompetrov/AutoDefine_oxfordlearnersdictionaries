# AutoDefine Oxford Learner's Dictionaries Anki Add-on
# Auto-defines words using Oxford Learner's Dictionaries, optionally adding images.
# Copyright (c) Artem Petrov    apsapetrov@gmail.com
# https://github.com/artyompetrov/AutoDefine_oxfordlearnersdictionaries Licensed under GPL v2

# Initially was forked from
# Copyright (c) Robert Sanek    robertsanek.com    rsanek@gmail.com
# https://github.com/z1lc/AutoDefine                      Licensed under GPL v2
#
# Then was completely overwritten

import os
import re
from anki.hooks import addHook
from aqt import mw
from aqt.utils import tooltip
from aqt.utils import askUser
from bs4 import BeautifulSoup
import requests
import webbrowser
import importlib.util
import sys
from contextlib import contextmanager
import pathlib
from .oxford import Word, WordNotFound
from http import cookiejar

if getattr(mw.addonManager, "getConfig", None):
    CONFIG = mw.addonManager.getConfig(__name__)


def get_config_value(section_name, param_name, default):
    value = default
    if CONFIG is not None:
        if section_name in CONFIG:
            section = CONFIG[section_name]
            if param_name in section:
                value = section[param_name]
    return value


SOURCE_FIELD = get_config_value('1. params', " 1. SOURCE_FIELD", 0)
DEFINITION_FIELD = get_config_value('1. params', " 2. DEFINITION_FIELD", 1)
AUDIO = get_config_value('1. params', " 3. AUDIO", False)
AUDIO_FIELD = get_config_value('1. params', " 4. AUDIO_FIELD", 2)
PHONETICS = get_config_value('1. params', " 5. PHONETICS", False)
PHONETICS_FIELD = get_config_value('1. params', " 6. PHONETICS_FIELD", 3)
OPEN_IMAGES_IN_BROWSER = get_config_value('1. params', " 7. OPEN_IMAGES_IN_BROWSER", False)
SEARCH_APPEND = get_config_value('1. params', " 8. SEARCH_APPEND", "")
REPLACE_BY = get_config_value('1. params', " 9. REPLACE_BY", "____")
CLEAN_HTML_IN_SOURCE_FIELD = get_config_value('1. params', "10. CLEAN_HTML_IN_SOURCE_FIELD", False)
OPEN_IMAGES_IN_BROWSER_LINK = get_config_value('1. params', "11. OPEN_IMAGES_IN_BROWSER_LINK", "https://www.google.com/search?q=$&tbm=isch&safe=off&tbs&hl=en&sa=X")
CORPUS = get_config_value('1. params', "12. CORPUS", "American")
MAX_EXAMPLES_COUNT_PER_DEFINITION = get_config_value('1. params', "13. MAX_EXAMPLES_COUNT_PER_DEFINITION", 3)
MAX_DEFINITIONS_COUNT_PER_PART_OF_SPEECH = get_config_value('1. params', "14. MAX_DEFINITIONS_COUNT_PER_PART_OF_SPEECH", 3)

PRIMARY_SHORTCUT = get_config_value('2. shortcuts', " 1. PRIMARY_SHORTCUT", "ctrl+alt+e")

if CORPUS.lower() == 'british':
    CORPUS_TAG = 'BrE'
elif CORPUS.lower() == 'american':
    CORPUS_TAG = 'nAmE'
else:
    raise Exception("Unknown CORPUS " + CORPUS)


class BlockAll(cookiejar.CookiePolicy):
    """ policy to block cookies """
    return_ok = set_ok = domain_return_ok = path_return_ok = lambda self, *args, **kwargs: False
    netscape = True
    rfc2965 = hide_cookie2 = False


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
    word = re.sub(r"\s+", " ", word)

    if CLEAN_HTML_IN_SOURCE_FIELD:
        insert_into_field(editor, word, SOURCE_FIELD, overwrite=True)

    return word

def nltk_token_spans(txt):
    tokens = tokinize(txt)
    offset = 0
    for token in tokens:
        offset = txt.find(token, offset)
        next_offset = offset + len(token)
        yield token, offset, next_offset
        assert token == txt[offset:next_offset]
        offset = next_offset


def replace_word_in_sentence(words, sentence, highlight):
    words_to_replace = [unify(str.lower(word)) for word in tokinize(words)]

    result = str()
    spans = list(nltk_token_spans(sentence))

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

    if not replaced_anything and highlight:
        result = '<font color="blue">' + result + '</font>'

    return result


def get_data(editor):
    word = get_word(editor)
    if word == "":
        tooltip("AutoDefine: No text found in note fields.")
        return

    words_info = get_words_info(word)

    if len(words_info) == 0:
        tooltip(f"Word '{word}' not found.")
        return

    insert_into_field(editor, '', DEFINITION_FIELD, overwrite=True)

    definition_html = get_definition_html(words_info)
    insert_into_field(editor, definition_html, DEFINITION_FIELD, overwrite=False)

    if PHONETICS:
        phonetics = get_phonetics(words_info)
        insert_into_field(editor, phonetics, PHONETICS_FIELD, overwrite=True)

    if AUDIO:
        audio = get_audio(words_info)
        insert_into_field(editor, audio, AUDIO_FIELD, overwrite=True)

    found_word = get_word_name(words_info)
    if found_word != word:
        if askUser(f"Attention! found another word '{found_word}', replace source field?"):
            insert_into_field(editor, found_word, SOURCE_FIELD, overwrite=True)
            word = found_word

    if OPEN_IMAGES_IN_BROWSER:
        link = OPEN_IMAGES_IN_BROWSER_LINK.replace("$", word + SEARCH_APPEND)
        webbrowser.open(
            link,
            0, False)

    focus_zero_field(editor)


def get_words_info(request_word):
    words_info = []
    word_to_search = request_word.replace(" ", "-").lower()
    try:
        Word.get(word_to_search, HEADERS)

        word_info = Word.info()
        name = word_info["name"].strip()
        words_info.append(word_info)

        for i in range(2, 5):
            Word.get(word_to_search + "_" + str(i), HEADERS)
            word_info_2 = Word.info()
            if word_info_2["name"].strip() == name:
                words_info.append(word_info_2)

    except WordNotFound:
        pass
    return words_info


def get_word_name(word_infos):
    for word_info in word_infos:
        return word_info["name"]


def get_definition_html(word_infos):
    strings = []
    for word_info in word_infos:
        word = word_info["name"]
        wordform = word_info.get("wordform")
        if wordform is not None:
            strings.append('<i>' + wordform + '</i>')

        definitions_by_namespaces = word_info["definitions"]

        definitions = []
        for definition_by_namespace in definitions_by_namespaces:
            for definition in definition_by_namespace["definitions"]:
                definitions.append(definition)

        if MAX_DEFINITIONS_COUNT_PER_PART_OF_SPEECH is not False:
            definitions = definitions[0:MAX_DEFINITIONS_COUNT_PER_PART_OF_SPEECH]

        for definition in definitions:
            maybe_description = definition.get("description")
            if maybe_description is not None:
                description = replace_word_in_sentence(word, maybe_description, False)
                strings.append('<div><b>' + description + '</b></div>')

            examples = definition.get("examples", []) + definition.get("extra_example", [])

            if MAX_EXAMPLES_COUNT_PER_DEFINITION is not False:
                examples = examples[0:MAX_EXAMPLES_COUNT_PER_DEFINITION]

            if len(examples) > 0:
                strings.append('<ul>')
                for example in examples:
                    example_clean = replace_word_in_sentence(word, example, True)
                    strings.append('<li>' + example_clean + '</li>')
                strings.append('</ul>')

        strings.append('<hr/>')

    del strings[-1]

    return BeautifulSoup(''.join(strings), 'html.parser').prettify()


def get_phonetics(word_infos):
    phonetics_dict = {}
    for word_info in word_infos:
        wordform = word_info.get("wordform")
        if wordform is None:
            wordform = "none"
        pronunciations = word_info.get("pronunciations")
        for pronunciation in pronunciations:
            if CORPUS_TAG == pronunciation["prefix"]:
                phonetics = pronunciation["ipa"].replace('/', "")

                value = phonetics_dict.get(phonetics, None)
                if value is not None:
                    value.append(wordform)
                else:
                    phonetics_dict[phonetics] = [wordform]

    if len(phonetics_dict) == 0:
        return "No phonetics found"
    elif len(phonetics_dict) == 1:
        return '[' + next(iter(phonetics_dict)) + ']'
    else:
        return "<br/>".join(["[" + key + '] - ' + ", ".join(phonetics_dict[key]) for key in iter(phonetics_dict)])


def get_audio(word_infos):
    audio_dict = {}
    for word_info in word_infos:
        wordform = word_info.get("wordform")
        if wordform is None:
            wordform = "none"
        pronunciations = word_info.get("pronunciations")
        for pronunciation in pronunciations:
            if CORPUS_TAG == pronunciation["prefix"]:
                audio_url = pronunciation["url"]

                audio_name = audio_url.split('/')[-1]

                collection_path = pathlib.Path(mw.col.path).parent.absolute()
                media_path = os.path.join(collection_path, "collection.media")
                audio_path = os.path.join(media_path, audio_name)

                value = audio_dict.get(audio_name, None)
                if value is not None:
                    value['wordform'].append(wordform)
                else:
                    if not os.path.exists(audio_path):
                        req = requests.Session()
                        req.cookies.set_policy(BlockAll())
                        response = req.get(audio_url, timeout=5, headers={'User-agent': 'mother animal'})
                        with open(audio_path, 'wb') as f:
                            f.write(response.content)
                    audio_dict[audio_name] = {'wordform': [wordform], "audio_name": audio_name}

    if len(audio_dict) == 0:
        return "No audio found"
    elif len(audio_dict) == 1:
        return f'[sound:{audio_dict[next(iter(audio_dict))]["audio_name"]}]'
    else:
        return "<br/>".join(["[sound:" + audio_dict[key]['audio_name'] + '] - ' +
                             ", ".join(audio_dict[key]['wordform']) for key in iter(audio_dict)])


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


def get_data_with_exception_handling(editor):
    try:
        get_data(editor)
    except Exception as ex:
        raise Exception("\n\nATTENTION! Please copy this error massage and open an issue on \n"
                        "https://github.com/artyompetrov/AutoDefine_oxfordlearnersdictionaries/issues \n"
                        "so I could investigate the reason of error and fix it") from ex


def setup_buttons(buttons, editor):
    both_button = editor.addButton(icon=os.path.join(os.path.dirname(__file__), "images", "icon30.png"),
                                   cmd="AD",
                                   func=lambda ed: ed.saveNow(lambda: get_data_with_exception_handling(ed)),
                                   tip="AutoDefine Word (%s)" %
                                       ("no shortcut" if PRIMARY_SHORTCUT == "" else PRIMARY_SHORTCUT),
                                   toggleable=False,
                                   label="",
                                   keys=PRIMARY_SHORTCUT,
                                   disables=False)

    buttons.append(both_button)
    return buttons


addHook("setupEditorButtons", setup_buttons)