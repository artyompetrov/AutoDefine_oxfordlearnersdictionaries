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
from aqt import mw, gui_hooks
from aqt.utils import tooltip
from aqt.utils import askUser, askUserDialog
from bs4 import BeautifulSoup
import requests
import webbrowser
import importlib.util
import sys
from contextlib import contextmanager
import pathlib
from .oxford import Word, WordNotFound
from http import cookiejar
from aqt.addcards import AddCards
from aqt.editor import Editor
from aqt.qt import *
from typing import Optional

add_dialog: Optional[AddCards] = None

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

ERROR_TAG_NAME = "AutoDefine_Error"
#todo
WORD_NOT_REPLACED_TAG_NAME = "AutoDefine_WordNotReplaced"

AUDIO_FORMAT = "mp3"

section = '0. test mode'
TEST_MODE = get_config_value(section, "TEST_MODE", False)

section = '1. word'
SOURCE_FIELD = get_config_value(section, " 1. SOURCE_FIELD", 0)
CLEAN_HTML_IN_SOURCE_FIELD = get_config_value(section, " 2. CLEAN_HTML_IN_SOURCE_FIELD", False)

section = '2. definition'
DEFINITION = get_config_value(section, " 1. DEFINITION", True)
DEFINITION_FIELD = get_config_value(section, " 2. DEFINITION_FIELD", 1)
REPLACE_BY = get_config_value(section, " 3. REPLACE_BY", "#$#")
MAX_EXAMPLES_COUNT_PER_DEFINITION = get_config_value(section, " 4. MAX_EXAMPLES_COUNT_PER_DEFINITION", 2)
MAX_DEFINITIONS_COUNT_PER_PART_OF_SPEECH = get_config_value(section, " 5. MAX_DEFINITIONS_COUNT_PER_PART_OF_SPEECH", 3)

section = '3. audio and phonetics'
CORPUS = get_config_value(section, " 1. CORPUS", "American")
AUDIO = get_config_value(section, " 2. AUDIO", True)
AUDIO_FIELD = get_config_value(section, " 3. AUDIO_FIELD", 2)
PHONETICS = get_config_value(section, " 4. PHONETICS", True)
PHONETICS_FIELD = get_config_value(section, " 5. PHONETICS_FIELD", 3)

section = '4. image'
OPEN_IMAGES_IN_BROWSER = get_config_value(section, " 1. OPEN_IMAGES_IN_BROWSER", True)
SEARCH_APPEND = get_config_value(section, " 2. SEARCH_APPEND", " picture OR clipart OR illustration OR art")
OPEN_IMAGES_IN_BROWSER_LINK = get_config_value(section, " 3. OPEN_IMAGES_IN_BROWSER_LINK",
                                               "https://www.google.com/search?q=$&tbm=isch&safe=off&tbs&hl=en&sa=X")

section = '5. shortcuts'
PRIMARY_SHORTCUT = get_config_value(section, " 1. PRIMARY_SHORTCUT", "ctrl+alt+e")

if CORPUS.lower() == 'british':
    CORPUS_TAGS_PRIORITIZED = ['BrE', 'nAmE']
elif CORPUS.lower() == 'american':
    CORPUS_TAGS_PRIORITIZED = ['nAmE', 'BrE']
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
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/118.0.0.0 Safari/537.36'
}


def focus_zero_field(editor):
    if TEST_MODE:
        return
    # no idea why, but sometimes web seems to be unavailable
    if editor.web:
        editor.web.eval("focusField(%d);" % 0)


def get_word(note):
    word = note.fields[SOURCE_FIELD]

    word = clean_html(word).strip()
    word = re.sub(r"\s+", " ", word)
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
        result = '<font color="red">Word_not_replaced</font> ' + result

    return result


def get_data(note, is_bulk):
    try:
        word = get_word(note)
        if word == "":
            raise AutoDefineError("There is no word in SOURCE_FIELD")

        if CLEAN_HTML_IN_SOURCE_FIELD:
            insert_into_field(note, word, SOURCE_FIELD, overwrite=True)

        words_info = get_words_info(word)

        if len(words_info) == 0:
            raise AutoDefineError(f"Word not found in dictionary")

        found_word = get_word_name(words_info)
        if found_word != word:
            if TEST_MODE or is_bulk:
                raise AutoDefineError(f"Found definition for word '{found_word}' instead'")
            else:
                if askUser(f"Attention! found another word '{found_word}', replace source field?"):
                    insert_into_field(note, found_word, SOURCE_FIELD, overwrite=True)
                    word = found_word

        if DEFINITION:
            insert_into_field(note, '', DEFINITION_FIELD, overwrite=True)
            definition_html = get_definition_html(words_info)
            insert_into_field(note, definition_html, DEFINITION_FIELD, overwrite=False)

        if PHONETICS:
            phonetics = get_phonetics(words_info)
            insert_into_field(note, phonetics, PHONETICS_FIELD, overwrite=True)

        if AUDIO:
            audio = get_audio(words_info)
            insert_into_field(note, audio, AUDIO_FIELD, overwrite=True)

        if OPEN_IMAGES_IN_BROWSER and not is_bulk:
            link = OPEN_IMAGES_IN_BROWSER_LINK.replace("$", word + SEARCH_APPEND)
            webbrowser.open(
                link,
                0, False)

        if ERROR_TAG_NAME in note.tags:
            note.tags.remove(ERROR_TAG_NAME)

    except Exception as error:
        if ERROR_TAG_NAME not in note.tags:
            note.tags.append(ERROR_TAG_NAME)
        raise error


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
        definitions_by_namespaces = word_info["definitions"]

        definitions = []
        for definition_by_namespace in definitions_by_namespaces:
            for definition in definition_by_namespace["definitions"]:
                definitions.append(definition)

        if len(definitions) == 0:
            continue

        word = word_info["name"]
        wordform = word_info.get("wordform")
        if wordform is not None:
            strings.append('<i>' + wordform + '</i>')

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
        fill_phonetics_dict_prioritized(phonetics_dict, pronunciations, wordform)

    if len(phonetics_dict) == 0:
        return "<span class=\"do_not_show\">No phonetics found</span>"
    elif len(phonetics_dict) == 1:
        return '[' + next(iter(phonetics_dict)) + ']'
    else:
        return "<br/>".join(["[" + key + '] - ' + ", ".join(phonetics_dict[key]) for key in iter(phonetics_dict)])


def fill_phonetics_dict_prioritized(phonetics_dict, pronunciations, wordform):
    for corpus_tag in CORPUS_TAGS_PRIORITIZED:
        for pronunciation in pronunciations:
            if corpus_tag == pronunciation["prefix"]:
                phonetics = pronunciation["ipa"].replace('/', "")

                value = phonetics_dict.get(phonetics, None)
                if value is not None:
                    value.append(wordform)
                else:
                    phonetics_dict[phonetics] = [wordform]
                return


def get_audio(word_infos):
    audio_dict = {}
    for word_info in word_infos:
        wordform = word_info.get("wordform")
        if wordform is None:
            wordform = "none"
        pronunciations = word_info.get("pronunciations")
        fill_audio_dict_prioritized(audio_dict, pronunciations, wordform)

    if len(audio_dict) == 0:
        return "<span class=\"do_not_show\">No audio found</span>"
    elif len(audio_dict) == 1:
        return f'[sound:{audio_dict[next(iter(audio_dict))]["audio_name"]}]'
    else:
        return "<br/>".join(["[sound:" + audio_dict[key]['audio_name'] + '] - ' +
                             ", ".join(audio_dict[key]['wordform']) for key in iter(audio_dict)])


def fill_audio_dict_prioritized(audio_dict, pronunciations, wordform):
    for corpus_tag in CORPUS_TAGS_PRIORITIZED:
        for pronunciation in pronunciations:
            if corpus_tag == pronunciation["prefix"]:
                audio_url = pronunciation["mp3"] if AUDIO_FORMAT.lower() == "mp3" else pronunciation["ogg"]

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
                        response = req.get(audio_url, timeout=5, headers=HEADERS)
                        with open(audio_path, 'wb') as f:
                            f.write(response.content)
                    audio_dict[audio_name] = {'wordform': [wordform], "audio_name": audio_name}
                return


def insert_into_field(note, text, field_id, overwrite=False):
    if len(note.fields) <= field_id:
        raise AutoDefineError(
            "AutoDefine: Tried to insert '%s' into user-configured field number %d (0-indexed), but note type only "
            "has %d fields. Use a different note type with %d or more fields, or change the index in the "
            "Add-on configuration." % (text, field_id, len(note.fields), field_id + 1))

    if overwrite:
        note.fields[field_id] = text
    else:
        note.fields[field_id] += text


def clean_html(raw_html):
    return re.sub(re.compile('<.*?>'), '', raw_html).replace("&nbsp;", " ")


def new_add_cards(addcards: AddCards):
    global add_dialog
    add_dialog = addcards


def switch_model(name):
    try:
        notetype = mw.col.models.by_name(name)
        if notetype:
            id = notetype["id"]
            add_dialog.notetype_chooser.selected_notetype_id = id
            tooltip(name)
        else:
            tooltip("No note type with name: " + name)
    except:  # triggered when not in Add Cards window
        pass


def addCustomModel(col):
    name = "AutoDefineOxfordLearnersDictionary"
    mm = col.models

    model = mm.byName(name)

    if not model:
        model = mm.new(name)
        mm.add(model)

    # add fields
    addField(mm, model, {"Word", "DefinitionAndExamples", "Audio", "Phonetics", "Image"})

    model['css'] = """
.card {
  font-family: arial;
  font-size: 20px;
  color: black;
  background-color: white;
  text-align: left;
}

.front {
  text-align: center;
}

.do_not_show {
  display: none;
}

.img {
  text-align: center;
}

img {
  padding-left: 5px;
  padding-right: 5px;
}

b {
  color: black;
}

i {
  color: grey;
}

.nightMode b {
  color: #8ab4f8;
}

.nightMode i {
  color: silver;
}

.nightMode a {
  color: #8ab4f8;
}
"""

    # front
    t = getTemplate(mm, model, 'Normal')
    t['qfmt'] = """<div class="front">{{Word}} {{Audio}}</div>"""
    t['afmt'] = """
<div class="front">{{Word}} {{Audio}}</div>
<hr id=answer>
<div class="img">{{Image}}</div>
<hr>
<div id="to_replace">
{{DefinitionAndExamples}}
</div>
<script>
    document.getElementById('to_replace').innerHTML =
     document.getElementById('to_replace').innerHTML.replace(/[#]([^#]+)[#]/ig, "<b>$1</b>");
</script>
"""

    # back
    t = getTemplate(mm, model, "Reverse")
    t['qfmt'] = """
<script>
    var hintString = '{{Word}}';
    var position = 0;
    function hint() {
    position += 1;
    if (hintString.length <= position) 
    {
        document.getElementById('hint_link').style.display='none'}
        return hintString.substring(0, position);
    }
</script>

<div class="front">
    {{type:Word}}
    <br id="hint_br">
    <a id="hint_link" class=hint href="#"onclick="document.getElementById('hint_div').style.display='inline-block';document.getElementById('hint_div').innerHTML=hint();return false;">Show hint</a>
    <div id="hint_div" class=hint style="display: none"></div>
</div>
<hr id=answer>
<div class="img">{{Image}}</div>
<hr>
<div id="to_replace">
{{DefinitionAndExamples}}
</div>

<script>
    document.getElementById('to_replace').innerHTML =
     document.getElementById('to_replace').innerHTML
     .replace(/[#]([^#]+)[#]/ig, "<span class='word'><b>$1</b></span><span class='replacement'>____</span>");
     
    for (let el of document.querySelectorAll('.word')) el.style.display = 'none';
    for (let el of document.querySelectorAll('.replacement')) el.style.display = 'inline';
</script>
"""
    t['afmt'] = """
<div class="front">{{Audio}}</div>
    {{FrontSide}}
<script>
    document.getElementById('hint_link').style.display='none';
    document.getElementById('hint_br').style.display='none';
    for (let el of document.querySelectorAll('.word')) el.style.display = 'inline';
    for (let el of document.querySelectorAll('.replacement')) el.style.display = 'none';
</script>
    """

    return model


def getTemplate(mm, model, templateName):
    for ankiTemplate in model['tmpls']:
        if ankiTemplate['name'] == templateName:
            return ankiTemplate
    t = mm.newTemplate(templateName)
    mm.addTemplate(model, t)
    return t


def addField(mm, model, fieldsToCreate: list):
    existingFieldsMap = mm.field_map(model)

    existingFields = list(existingFieldsMap.keys())

    toCreate = fieldsToCreate - existingFields
    toDelete = existingFields - fieldsToCreate

    for field in toCreate:
        mm.addField(model, mm.newField(field))

    for field in toDelete:
        mm.remove_field(model, existingFieldsMap[field][1])
    # todo порядок полей починить


def bulkDefine(browser):
    ids = browser.selectedNotes()
    if not ids:
        tooltip("No cards selected.")
        return
    mw.checkpoint("AutoDefine")
    mw.progress.start(immediate=True, max=len(ids))
    browser.model.beginReset()

    errors = []

    def process(nids, mw):
        count = 0
        max = len(nids)
        for nid in nids:
            count += 1
            note = mw.col.getNote(nid)
            word = None
            try:
                word = get_word(note)
                mw.taskman.run_on_main(
                    lambda c=count, w=word, m=max: mw.progress.update(value=c, label=w, process=False, max=m)
                )
                get_data(note, is_bulk=True)

            except AutoDefineError as error:
                save_error(count, error.message, word, errors)
            except Exception as ex:
                save_error(count, "Exception", word, errors)
            note.flush()

    def onFinish(future):
        browser.model.endReset()
        mw.requireReset()
        mw.progress.finish()
        mw.reset()
        if len(errors) > 0:
            askUserDialog("\n".join(errors), ['OK'], title='Bulk operation finished with some errors', parent=browser) \
                .run()

    mw.taskman.run_in_background(process, onFinish, args={"nids": ids, "mw": mw})

def save_error(count, error_text, word, errors):
    if word is not None and word != "":
        errors.append(f"{word}: {error_text}")
    else:
        errors.append(f"Word number {count}: {error_text}")

def get_data_with_exception_handling(editor: Editor):
    try:
        # addCustomModel(mw.col)
        # switch_model("AutoDefineOxfordLearnersDictionary")

        note = editor.note
        try:
            get_data(note, is_bulk=False)
        except AutoDefineError as error:
            tooltip(error.message, period=10000)

        flush_note(note)
        mw.requireReset()
        mw.reset()
        editor.loadNote()
        focus_zero_field(editor)
    except Exception as ex:
        raise Exception("\n\nATTENTION! Please copy this error massage and open an issue on \n"
                        "https://github.com/artyompetrov/AutoDefine_oxfordlearnersdictionaries/issues \n"
                        "so I could investigate the reason of error and fix it") from ex


def flush_note(note):
    try:
        note.flush()
    except Exception:
        pass


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


def setupMenu(browser):
    menu = browser.form.menuEdit
    menu.addSeparator()
    a = menu.addAction('Auto define in bulk...')
    a.setShortcut(QKeySequence("ctrl+alt+e"))
    a.triggered.connect(lambda _, b=browser: bulkDefine(b))


addHook("browser.setupMenus", setupMenu)

addHook("setupEditorButtons", setup_buttons)
gui_hooks.add_cards_did_init.append(new_add_cards)


class AutoDefineError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)
